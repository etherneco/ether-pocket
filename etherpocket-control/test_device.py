"""Explicit real-device acceptance using a temporary xev input-test window."""
import io
import json
from pathlib import Path
import subprocess
import threading
import time

from PIL import Image
from transport import frames, install_agent, ssh_command

ROOT = Path(__file__).resolve().parent.parent


def main():
    ssh = ssh_command('10.77.0.2', ROOT/'build/etherpocket_ed25519', ROOT/'build/mobian-known-hosts')
    install_agent(ssh, (ROOT/'etherpocket-control/agent.py').read_bytes())
    def remote(source):
        result = subprocess.run(ssh+['python3 -'], input=source.encode(), capture_output=True, timeout=15)
        result.check_returncode()
        return result.stdout.decode()
    setup = r'''
import os,pathlib,subprocess,json
env=dict(os.environ,DISPLAY=':0',XAUTHORITY='/home/mobian/.Xauthority')
user=['runuser','-u','mobian','--','env','DISPLAY=:0','XAUTHORITY=/home/mobian/.Xauthority']
focus=subprocess.check_output(user+['xdotool','getwindowfocus'],text=True).strip()
output=open('/var/tmp/etherpocket-control-input-test.log','w')
p=subprocess.Popen(user+['stdbuf','-oL','xev','-name','EtherPocket Control Input Test','-geometry','400x200+50+50'],stdout=output,stderr=subprocess.DEVNULL,start_new_session=True)
print(json.dumps({'pid':p.pid,'focus':focus}))
'''
    state = json.loads(remote(setup))
    process = None
    report = {}
    try:
        time.sleep(.6)
        geometry = remote("import subprocess,time;u=['runuser','-u','mobian','--','env','DISPLAY=:0','XAUTHORITY=/home/mobian/.Xauthority'];w=subprocess.check_output(u+['xdotool','search','--name','^EtherPocket Control Input Test$'],text=True).splitlines()[-1];subprocess.run(u+['xdotool','windowfocus','--sync',w],check=True);time.sleep(.4);print(subprocess.check_output(u+['xdotool','getwindowgeometry','--shell',w],text=True))")
        position = dict(line.split('=', 1) for line in geometry.splitlines() if '=' in line)
        process = subprocess.Popen(ssh+['exec runuser -u mobian -- env DISPLAY=:0 XAUTHORITY=/home/mobian/.Xauthority python3 /usr/local/lib/etherpocket-control/agent.py 5'],
            stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        report['metadata'] = json.loads(process.stdout.readline())
        received = []
        def consume():
            for jpeg in frames(process.stdout):
                if len(received) < 3:
                    image = Image.open(io.BytesIO(jpeg)); image.load(); received.append(image)
        reader = threading.Thread(target=consume, daemon=True); reader.start()
        def send(event):
            process.stdin.write((json.dumps(event)+'\n').encode()); process.stdin.flush()
        send(dict(type='text', text='a\u0105'))
        send(dict(type='key', key='Shift_L', down=True)); send(dict(type='release'))
        time.sleep(1)
        log = remote("from pathlib import Path;print(Path('/var/tmp/etherpocket-control-input-test.log').read_text())")
        report.update(keyboard_text='keysym 0x61, a' in log,
                      unicode_text='aogonek' in log or 'U0105' in log, modifier='Shift_L' in log)
        query = r'''
import ctypes,json,os
os.environ['XAUTHORITY']='/home/mobian/.Xauthority'
x=ctypes.CDLL('libX11.so.6');x.XOpenDisplay.argtypes=[ctypes.c_char_p];x.XOpenDisplay.restype=ctypes.c_void_p
d=x.XOpenDisplay(b':0');assert d;x.XDefaultRootWindow.argtypes=[ctypes.c_void_p];x.XDefaultRootWindow.restype=ctypes.c_ulong
x.XQueryPointer.argtypes=[ctypes.c_void_p,ctypes.c_ulong,ctypes.POINTER(ctypes.c_ulong),ctypes.POINTER(ctypes.c_ulong),ctypes.POINTER(ctypes.c_int),ctypes.POINTER(ctypes.c_int),ctypes.POINTER(ctypes.c_int),ctypes.POINTER(ctypes.c_int),ctypes.POINTER(ctypes.c_uint)]
r=ctypes.c_ulong();c=ctypes.c_ulong();a=ctypes.c_int();b=ctypes.c_int();e=ctypes.c_int();f=ctypes.c_int();m=ctypes.c_uint()
x.XQueryPointer(d,x.XDefaultRootWindow(d),ctypes.byref(r),ctypes.byref(c),ctypes.byref(a),ctypes.byref(b),ctypes.byref(e),ctypes.byref(f),ctypes.byref(m))
print(json.dumps({'x':a.value,'y':b.value,'mask':m.value}))
'''
        send(dict(type='move', x=1000, y=80));send(dict(type='button',button=1,down=True));time.sleep(.2)
        down=json.loads(remote(query));report['mouse_press']=bool(down['mask'] & 256)
        report['pointer_verified']=(down['x'],down['y'])==(1000,80)
        send(dict(type='release'));time.sleep(.2)
        report['mouse_release']=not (json.loads(remote(query))['mask'] & 256)
        deadline = time.monotonic()+10
        while len(received)<3 and time.monotonic()<deadline: time.sleep(.1)
        assert received, 'No video frames'
        report['frame_size'] = received[0].size
        received[0].save(ROOT/'evidence/etherpocket-control-device.png')
        send(dict(type='stop')); process.stdin.close(); process.wait(timeout=8); reader.join(timeout=3)
        report['clean_stop'] = process.returncode in (0, 255)
        assert all(report[k] for k in ['mouse_press','mouse_release','keyboard_text','unicode_text','modifier','clean_stop']), report
    finally:
        if process and process.poll() is None: process.kill()
        remote("import os,signal,subprocess;os.killpg("+str(state['pid'])+",signal.SIGTERM);subprocess.run(['runuser','-u','mobian','--','env','DISPLAY=:0','XAUTHORITY=/home/mobian/.Xauthority','xdotool','windowactivate',"+repr(state['focus'])+"])")
        (ROOT/'evidence/etherpocket-control-device.json').write_text(json.dumps(report, indent=2)+'\n')
    print(json.dumps(report, indent=2))


if __name__ == '__main__':
    main()
