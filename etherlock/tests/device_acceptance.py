"""Root harness, disposable account/display only. Never tests live session locks."""
import json
import os
import pathlib
import pwd
import secrets
import select
import signal
import subprocess
import tempfile
import time


def main(output, ui_only=False):
    assert os.geteuid() == 0
    out = pathlib.Path(output); out.mkdir(parents=True, exist_ok=True)
    assert not pathlib.Path('/tmp/.X11-unix/X94').exists(), 'Private display occupied'
    name = 'elqa' + secrets.token_hex(4)
    secret = secrets.token_urlsafe(24)
    subprocess.run(['useradd', '--create-home', '--shell', '/bin/sh', name], check=True)
    server = locker = None
    tests = {}
    try:
        user = pwd.getpwnam(name)
        subprocess.run(['chpasswd'], input=(name + ':' + secret + '\n').encode(), check=True)
        base = ['runuser', '-u', name, '--']

        def auth(value):
            p = subprocess.run(base + ['/usr/lib/etherlock/etherlock-pam'],
                input=(json.dumps({'response': value}) + '\n').encode(), capture_output=True, timeout=12)
            rows = [json.loads(line) for line in p.stdout.splitlines()]
            return p.returncode == 0 and rows[-1] == {'event': 'result', 'success': True}

        def reset(): subprocess.run(['faillock', '--user', name, '--reset'], check=True, capture_output=True)

        if not ui_only:
            tests['correct_password'] = auth(secret)
            tests['wrong_password'] = not auth('wrong-fixture-credential')
            tests['empty_refused'] = not auth('')
            reset()
            subprocess.run(['chage', '-E', '0', name], check=True)
            tests['expired_account_refused_after_correct_password'] = not auth(secret)
            subprocess.run(['chage', '-E', '-1', name], check=True)
            reset()
            tests['five_failures'] = all(not auth('wrong-fixture-credential') for _ in range(5))
            tests['new_helper_correct_password_locked_out'] = not auth(secret)
            start = time.monotonic()
            # Actual PAM expiry, not a UI-only timer or test-time policy replacement.
            time.sleep(122)
            tests['lockout_expiration'] = auth(secret)
            tests['lockout_wait_seconds'] = time.monotonic() - start >= 120
            (out/'pam-acceptance.json').write_text(json.dumps(tests, indent=2))
        reset()
        with tempfile.TemporaryDirectory(prefix='etherlock-qa-', dir='/var/tmp') as temp:
            folder = pathlib.Path(temp); os.chown(folder, user.pw_uid, user.pw_gid)
            authority = folder/'Xauthority'; authority.touch(mode=0o600); os.chown(authority, user.pw_uid, user.pw_gid)
            subprocess.run(base + ['xauth', '-f', str(authority), 'add', ':94', 'MIT-MAGIC-COOKIE-1', secrets.token_hex(16)], check=True)
            env = dict(os.environ, DISPLAY=':94', XAUTHORITY=str(authority), HOME=user.pw_dir,
                       LANG='C.UTF-8', QT_QUICK_BACKEND='software', XSECURELOCK_AUTH='/usr/lib/etherlock/auth_etherlock',
                       XSECURELOCK_BLANK_TIMEOUT='-1', XSECURELOCK_SHOW_DATETIME='1')
            for key in ('DBUS_SESSION_BUS_ADDRESS', 'SESSION_MANAGER', 'XDG_RUNTIME_DIR'): env.pop(key, None)
            log = (out/'x11.log').open('wb')
            server = subprocess.Popen(base + ['Xvfb', ':94', '-screen', '0', '360x900x24', '-nolisten', 'tcp', '-auth', str(authority)], env=env, stdout=log, stderr=log)
            for _ in range(50):
                if subprocess.run(base + ['xdpyinfo'], env=env, capture_output=True).returncode == 0: break
                time.sleep(.1)
            else: raise RuntimeError('Private X11 failed')
            locker = subprocess.Popen(base + ['/usr/bin/xsecurelock', '--', '/usr/bin/printf', 'READY\\n'],
                env=env, stdout=subprocess.PIPE, stderr=log, start_new_session=True)
            ready, _, _ = select.select([locker.stdout], [], [], 8)
            tests['post_grab_ready'] = bool(ready) and locker.stdout.readline(128) == b'READY\n' and locker.poll() is None
            def key(*args): subprocess.run(base+['xdotool']+list(args), env=env, check=True, capture_output=True)
            key('key', 'a'); key('key', 'ctrl+u'); time.sleep(2)
            # Capture the auth drawable directly for QA, never the real session.
            capture = subprocess.run(base+['xwininfo', '-root', '-tree'], env=env, capture_output=True, text=True)
            (out/'window-tree.txt').write_text(capture.stdout)
            auth_pids = subprocess.check_output(['pgrep', '-u', str(user.pw_uid), '-x', 'auth_etherlock'], text=True).split()
            for pid in auth_pids:
                proc_env = dict(x.split('=', 1) for x in pathlib.Path('/proc', pid, 'environ').read_bytes().decode().split('\0') if '=' in x)
                parent = int(proc_env['XSCREENSAVER_WINDOW'], 0)
                tree = subprocess.run(base+['xwininfo','-id',hex(parent),'-tree'],env=env,capture_output=True,text=True).stdout
                (out/'auth-window.txt').write_text(tree)
                import re
                window = int(re.search(r'(0x[0-9a-f]+) "auth_etherlock":', tree).group(1),16)
                import ctypes as c
                from PIL import Image
                class XImage(c.Structure):
                    _fields_=[('width',c.c_int),('height',c.c_int),('offset',c.c_int),('format',c.c_int),('data',c.c_void_p),
                              ('order',c.c_int),('unit',c.c_int),('bit_order',c.c_int),('pad',c.c_int),('depth',c.c_int),('stride',c.c_int),('bpp',c.c_int)]
                x=c.CDLL('libX11.so.6');x.XOpenDisplay.argtypes=[c.c_char_p];x.XOpenDisplay.restype=c.c_void_p
                error_handler=c.CFUNCTYPE(c.c_int,c.c_void_p,c.c_void_p)(lambda *_:0)
                x.XSetErrorHandler(error_handler)
                x.XGetImage.argtypes=[c.c_void_p,c.c_ulong,c.c_int,c.c_int,c.c_uint,c.c_uint,c.c_ulong,c.c_int];x.XGetImage.restype=c.POINTER(XImage)
                x.XDestroyImage.argtypes=[c.POINTER(XImage)];x.XCloseDisplay.argtypes=[c.c_void_p]
                os.environ['XAUTHORITY']=str(authority);display=x.XOpenDisplay(b':94')
                image=x.XGetImage(display,window,0,0,360,900,c.c_ulong(-1),2)
                assert image and image.contents.bpp==32 and image.contents.order==0
                raw=c.string_at(image.contents.data,image.contents.stride*900)
                shot=Image.frombytes('RGB',(360,900),raw,'raw','BGRX',image.contents.stride)
                shot.save(out/'auth-drawable-360.png');tests['auth_drawable_painted']=len(shot.getcolors(1000000))>20
                x.XDestroyImage(image)
                key('mousemove','75','350');key('click','1');time.sleep(.25)
                image=x.XGetImage(display,window,0,0,360,900,c.c_ulong(-1),2)
                assert image
                raw=c.string_at(image.contents.data,image.contents.stride*900)
                clicked=Image.frombytes('RGB',(360,900),raw,'raw','BGRX',image.contents.stride)
                clicked.save(out/'keypad-click-360.png')
                tests['pointer_key_enters_masked_input']=shot.crop((25,245,335,285)).tobytes()!=clicked.crop((25,245,335,285)).tobytes()
                x.XDestroyImage(image);x.XCloseDisplay(display)
                key('key','ctrl+u')
            try:
                from PIL import ImageGrab
                os.environ['XAUTHORITY'] = str(authority)
                ImageGrab.grab(xdisplay=':94').save(out/'lock-360.png')
            except ImportError: pass
            key('type', '--clearmodifiers', 'wrong-fixture-credential'); key('key', 'Return'); time.sleep(4)
            tests['wrong_password_keeps_locker_alive'] = locker.poll() is None
            # Crash only the auth child; enforcing parent must survive.
            pids = subprocess.check_output(['pgrep', '-u', str(user.pw_uid), '-x', 'auth_etherlock'], text=True).split()
            tests['auth_child_present'] = len(pids) == 1
            for pid in pids: os.kill(int(pid), signal.SIGKILL)
            time.sleep(1); tests['auth_child_crash_keeps_locker_alive'] = locker.poll() is None
            key('key', 'Shift_L'); time.sleep(2)
            key('type', '--clearmodifiers', secret); key('key', 'Return')
            try: tests['correct_password_unlocks'] = locker.wait(timeout=10) == 0
            except subprocess.TimeoutExpired: tests['correct_password_unlocks'] = False
            tests['no_qml_errors'] = not any(s in (out/'x11.log').read_text(errors='replace') for s in ['qrc:/Lock.qml:', 'failed to load'])
    finally:
        if locker and locker.poll() is None: os.killpg(locker.pid, signal.SIGTERM); locker.wait(timeout=5)
        if server and server.poll() is None: server.terminate(); server.wait(timeout=5)
        # Account was created by this invocation; no preexisting user's data is removed.
        subprocess.run(['userdel', '--remove', name], capture_output=True)
    (out/'acceptance.json').write_text(json.dumps(tests, indent=2))
    print(json.dumps(tests, indent=2), flush=True)
    assert all(tests.values()), 'Acceptance failed'


if __name__ == '__main__':
    import sys
    main(sys.argv[1], '--ui-only' in sys.argv[2:])
