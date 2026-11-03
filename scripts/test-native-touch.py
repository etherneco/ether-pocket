"""Phone-only integration check: real XI2 touch -> Firefox page scroll.

Uses a temporary browser profile and a temporary uinput touchscreen. Does not
open or modify the user's browser profile. Run as root in the X11 session.
"""
import http.server
import json
import os
from pathlib import Path
import pwd
import subprocess
import tempfile
import threading
import time

from evdev import AbsInfo, UInput, ecodes as e

reports = []
PAGE = b'''<!doctype html><meta name="viewport" content="width=device-width">
<style>body{margin:0;background:#eef4ff;font:40px sans-serif}div{height:9000px}
</style><div>EtherPocket: test przewijania dotykiem</div><script>
let touches=0, pointers=[];
addEventListener('touchstart',()=>touches++,{passive:true});
addEventListener('pointerdown',e=>pointers.push(e.pointerType),{passive:true});
setInterval(()=>fetch('/report',{method:'POST',body:JSON.stringify({
scrollY,touches,pointers,maxTouchPoints:navigator.maxTouchPoints})}),500);
</script>'''


class Handler(http.server.BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.end_headers()
        self.wfile.write(PAGE)

    def do_POST(self):
        reports.append(json.loads(self.rfile.read(int(self.headers['Content-Length']))))
        self.send_response(204)
        self.end_headers()

    def log_message(self, *args):
        pass


def touch_device():
    caps = {e.EV_KEY: [e.BTN_TOUCH], e.EV_ABS: [
        (e.ABS_X, AbsInfo(0, 0, 1439, 0, 0, 0)),
        (e.ABS_Y, AbsInfo(0, 0, 3119, 0, 0, 0)),
        (e.ABS_MT_SLOT, AbsInfo(0, 0, 9, 0, 0, 0)),
        (e.ABS_MT_TRACKING_ID, AbsInfo(0, 0, 65535, 0, 0, 0)),
        (e.ABS_MT_POSITION_X, AbsInfo(0, 0, 1439, 0, 0, 0)),
        (e.ABS_MT_POSITION_Y, AbsInfo(0, 0, 3119, 0, 0, 0))]}
    return UInput(caps, name='EtherPocket native touch test', input_props=[e.INPUT_PROP_DIRECT])


def swipe(ui, start_y=2200):
    ui.write(e.EV_KEY, e.BTN_TOUCH, 1)
    ui.write(e.EV_ABS, e.ABS_MT_SLOT, 0)
    ui.write(e.EV_ABS, e.ABS_MT_TRACKING_ID, 1)
    for n in range(41):
        y = start_y - n * 30
        for code, value in [(e.ABS_X, 700), (e.ABS_Y, y),
                            (e.ABS_MT_POSITION_X, 700), (e.ABS_MT_POSITION_Y, y)]:
            ui.write(e.EV_ABS, code, value)
        ui.syn()
        time.sleep(.02)
    ui.write(e.EV_ABS, e.ABS_MT_TRACKING_ID, -1)
    ui.write(e.EV_KEY, e.BTN_TOUCH, 0)
    ui.syn()


if __name__ == '__main__':
    user = pwd.getpwnam('mobian')
    env = dict(os.environ, DISPLAY=':0', XAUTHORITY='/home/mobian/.Xauthority',
               HOME='/home/mobian', XDG_RUNTIME_DIR='/run/user/1000',
               DBUS_SESSION_BUS_ADDRESS='unix:path=/run/user/1000/bus')
    server = http.server.ThreadingHTTPServer(('127.0.0.1', 0), Handler)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    results = {}
    with touch_device() as ui:
        time.sleep(2)
        for mode in ['baseline', 'native']:
            reports.clear()
            with tempfile.TemporaryDirectory(prefix='etherpocket-touch-') as profile:
                os.chown(profile, user.pw_uid, user.pw_gid)
                prefs = Path(profile) / 'user.js'
                prefs.write_text('user_pref("browser.shell.checkDefaultBrowser", false);\n'
                                 'user_pref("browser.aboutwelcome.enabled", false);\n'
                                 'user_pref("browser.startup.homepage_override.mstone", "ignore");\n'
                                 'user_pref("datareporting.policy.dataSubmissionPolicyBypassNotification", true);\n'
                                 + ('user_pref("dom.w3c_touch_events.enabled", 1);\n' if mode == 'native' else ''))
                os.chown(prefs, user.pw_uid, user.pw_gid)
                current_env = dict(env)
                if mode == 'native':
                    current_env['MOZ_USE_XINPUT2'] = '1'
                else:
                    current_env.pop('MOZ_USE_XINPUT2', None)
                with open('/tmp/etherpocket-touch-firefox-' + mode + '.log', 'w') as log:
                    proc = subprocess.Popen(['runuser', '-u', 'mobian', '--',
                        'firefox-esr', '--no-remote', '--profile', profile, '--kiosk',
                        f'http://127.0.0.1:{server.server_port}/'], env=current_env,
                        stdout=log, stderr=log)
                    try:
                        deadline = time.monotonic() + 35
                        while not reports and time.monotonic() < deadline:
                            time.sleep(.5)
                        if not reports:
                            raise RuntimeError('Browser did not load test page: ' + mode)
                        time.sleep(2)
                        swipe(ui)
                        time.sleep(3)
                        results[mode] = reports[-1]
                        print(json.dumps({mode: results[mode]}), flush=True)
                    finally:
                        proc.terminate()
                        try:
                            proc.wait(timeout=12)
                        except subprocess.TimeoutExpired:
                            proc.kill()
                            proc.wait()
    server.shutdown()
    assert results['native']['scrollY'] > 100, results
    assert results['native']['touches'] > 0, results
    assert 'touch' in results['native']['pointers'], results
