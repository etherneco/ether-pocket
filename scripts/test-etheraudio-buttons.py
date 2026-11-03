"""Exercise the existing X11 key owner without playing or recording audio."""
from pathlib import Path
import json,runpy,shlex,subprocess
ROOT=Path(__file__).resolve().parent.parent
SSH=runpy.run_path(str(ROOT/'scripts/deploy-ethermobile.py'))['SSH']
SOURCE=r'''
import json,pathlib,socket,subprocess,time
user=['runuser','-u','mobian','--','env','XDG_RUNTIME_DIR=/run/user/1000','DBUS_SESSION_BUS_ADDRESS=unix:path=/run/user/1000/bus']
def state():return json.loads(subprocess.check_output(user+['etheraudio','state'],text=True,timeout=10))
initial=state();assert not initial['sink-inputs'] and not initial['source-outputs'],'Do not interrupt active audio'
pids=subprocess.check_output(['pgrep','-u','1000','-x','ethershell'],text=True).split();assert len(pids)==1
env=dict(row.split('=',1) for row in (pathlib.Path('/proc')/pids[0]/'environ').read_bytes().decode().split('\0') if '=' in row)
endpoint='/run/user/1000/ethershell-control-experience-'+env['DISPLAY'].replace(':','').replace('.','-')
def request(data):
 with socket.socket(socket.AF_UNIX,socket.SOCK_STREAM) as s:
  s.settimeout(5);s.connect(endpoint);s.sendall(json.dumps(data).encode()+b'\n');reply=s.recv(8192).decode().strip()
  assert reply!='locked','Do not bypass the locked session'
  return reply
sink=next(s for s in initial['sinks'] if s['name']==initial['default-sink']);original=sink['percent'];assert 5<=original<=95
def level():return next(s['percent'] for s in state()['sinks'] if s['name']==sink['name'])
try:
 display=json.loads(request({'command':'power-display','action':'on'}));assert not display['blank']
 assert request({'command':'key','symbol':'XF86AudioLowerVolume'})=='ok';time.sleep(2);down=level();assert down==original-5,(original,down)
 assert request({'command':'key','symbol':'XF86AudioRaiseVolume'})=='ok';time.sleep(2);up=level();assert up==original,(original,up)
 assert request({'command':'ui','quick':True})=='ok';time.sleep(.5)
 assert request({'command':'settings-screenshot'})=='ok'
 pathlib.Path('/run/etheraudio-quick.png').write_bytes(pathlib.Path('/home/mobian/.config/ethershell/validation/settings2-screen.png').read_bytes())
 assert request({'command':'ui','quick':False})=='ok'
 assert request({'command':'settings-page','route':'sound'})=='ok';time.sleep(.5)
 assert request({'command':'settings-screenshot'})=='ok'
 print(json.dumps({'originalPercent':original,'afterDownPercent':down,'afterUpPercent':up,'oneStepVerified':True,
 'scope':'Synthetic X11 key events through the existing shell listener; not a human physical-button acceptance test','recordingStarted':False},indent=2))
finally:
 subprocess.run(user+['pactl','set-sink-volume',sink['name'],str(original)+'%'],check=True,timeout=10)
'''
if __name__=='__main__':
    p=subprocess.run(SSH+['python3 -c '+shlex.quote(SOURCE)],capture_output=True,timeout=35)
    if p.returncode:raise RuntimeError(p.stderr.decode(errors='replace')[-5000:])
    data=json.loads(p.stdout)
    (ROOT/'evidence/etheraudio-button-tests.json').write_text(json.dumps(data,indent=2)+'\n',encoding='utf-8')
    for remote,local in [('/run/etheraudio-quick.png','etheraudio-quick.png'),('/home/mobian/.config/ethershell/validation/settings2-screen.png','etheraudio-live.png')]:
        payload=subprocess.check_output(SSH+['cat '+remote],timeout=15)
        assert payload.startswith(b'\x89PNG');(ROOT/'evidence'/local).write_bytes(payload)
    print(json.dumps(data,indent=2))
