"""Read-only audio audit. Never opens playback/capture PCMs or restarts servers."""
from pathlib import Path
import json, runpy, shlex, subprocess
ROOT = Path(__file__).resolve().parent.parent
SSH = runpy.run_path(str(ROOT/'scripts/deploy-ethermobile.py'))['SSH']
SOURCE = r'''
import datetime,json,pathlib,shutil,subprocess
def read(path):
 try:return pathlib.Path(path).read_text().replace('\0','').strip()
 except OSError:return None
def run(args,user=False):
 if not shutil.which(args[0]):return {'available':False}
 if user:args=['runuser','-u','mobian','--','env','XDG_RUNTIME_DIR=/run/user/1000','DBUS_SESSION_BUS_ADDRESS=unix:path=/run/user/1000/bus']+args
 try:
  p=subprocess.run(args,capture_output=True,text=True,timeout=12)
  return {'exit':p.returncode,'stdout':p.stdout[:100000],'stderr':p.stderr[:2000]}
 except subprocess.TimeoutExpired:return {'error':'bounded audit timed out'}
data={'timestamp':datetime.datetime.now(datetime.timezone.utc).isoformat(),'kernel':read('/proc/sys/kernel/osrelease'),
 'cards':read('/proc/asound/cards'),'devices':read('/proc/asound/devices'),'pcm':read('/proc/asound/pcm'),
 'alsa':{str(p):{'id':read(p/'id'),'driver':str((p/'device/driver').resolve())} for p in pathlib.Path('/sys/class/sound').glob('card*')},
 'commands':{name:run(args) for name,args in {'playback':['aplay','-l'],'capture':['arecord','-l'],'ucm':['alsaucm','listcards']}.items()},
 'stack':{kind:run(['pactl','--format=json','list',kind],True) for kind in ['sinks','sources','sink-inputs','source-outputs','cards']},
 'server':run(['pactl','info'],True),'userServices':run(['systemctl','--user','is-active','pipewire','pipewire-pulse','wireplumber','pulseaudio'],True),
 'systemServices':run(['systemctl','is-active','etherpocket-audio','etherhardware','etherpower','ssh','bluetooth','NetworkManager','ModemManager']),
 'modules':run(['lsmod']),'ucmFiles':{str(p):read(p) for p in pathlib.Path('/usr/share/alsa/ucm2').glob('**/*tavil*') if p.is_file()},
 'scope':'Read-only: no recording, playback, hardware routing, USB role change, call, suspend or server restart'}
for card in pathlib.Path('/sys/class/sound').glob('card*'):
 ident=read(card/'id')
 if ident and 'tavil' in ident.lower():
  data['mixer']=run(['amixer','-c',ident,'contents'])
print(json.dumps(data,indent=2))
'''
if __name__ == '__main__':
    p = subprocess.run(SSH+['python3 -c '+shlex.quote(SOURCE)], capture_output=True, check=True, timeout=100)
    data = json.loads(p.stdout)
    (ROOT/'evidence/etheraudio-audit-2026-10-20.json').write_text(json.dumps(data,indent=2)+'\n',encoding='utf-8')
    print(json.dumps({k:data[k] for k in ['cards','alsa','server','userServices','systemServices']},indent=2))
