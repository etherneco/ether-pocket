"""Reversible session-service acceptance, no radio/call/audio commands."""
from pathlib import Path
import json,runpy
ROOT=Path(__file__).resolve().parent.parent
remote=runpy.run_path(str(ROOT/'scripts/check-etherphone-device.py'))['remote']
SOURCE=r'''
import hashlib,json,pathlib,subprocess,time
user=['runuser','-u','mobian','--','env','XDG_RUNTIME_DIR=/run/user/1000','DBUS_SESSION_BUS_ADDRESS=unix:path=/run/user/1000/bus']
def run(args):return subprocess.check_output(args,text=True,timeout=15).strip()
def state():return json.loads(run(user+['etherphone-control','state']))
def configure(data):
 for _ in range(30):
  p=subprocess.run(user+['etherphone-control','command','--operation','configure','--data',json.dumps(data)],capture_output=True,text=True,timeout=10)
  if p.returncode==0:return
  if 'Busy' not in p.stderr:raise RuntimeError('Configuration request failed')
  time.sleep(.1)
 raise RuntimeError('Service busy')
def ready():
 for _ in range(50):
  s=state()
  if s.get('ready'):return s
  time.sleep(.1)
 raise RuntimeError('Service did not become ready')
before=ready();assert not before['calls']
original=before['config'];changed=dict(original,missedNotifications=not original['missedNotifications'])
try:
 configure(changed)
 subprocess.run(user+['systemctl','--user','restart','etherphone'],check=True)
 current=ready();assert current['config']==changed
finally:configure(original)
assert ready()['config']==original
report={'settingsPersistedAcrossRestart':True,'settingsRestored':True,'contacts':len(before['contacts']),'historyEntries':len(before['history']),
 'privateFiles':{str(p):oct(p.stat().st_mode&0o777) for p in [pathlib.Path('/home/mobian/.local/share/ethercontacts/contacts.sqlite'),pathlib.Path('/home/mobian/.local/share/etherphone/history.sqlite'),pathlib.Path('/home/mobian/.config/etherphone/settings.json')]},
 'coreHashes':{name:hashlib.sha256(pathlib.Path('/usr/share/etherphone',name).read_bytes()).hexdigest() for name in ['core.py','service.py','provider.py','cli.py']},
 'service':run(user+['systemctl','--user','show','etherphone','-p','MainPID','-p','NRestarts']),
 'wifiHTTPS':run(['curl','--interface','wlan0','--max-time','15','-sS','-o','/dev/null','-w','%{http_code}','https://deb.debian.org']),
 'audioPids':{u:run(user+['systemctl','--user','show',u,'-p','MainPID','--value']) for u in ['pipewire','pipewire-pulse','wireplumber','etheraudio']}}
pid=int(run(user+['systemctl','--user','show','etherphone','-p','MainPID','--value']))
report['processBaseline']={'pid':pid,'timestamp':time.time(),'stat':pathlib.Path('/proc',str(pid),'stat').read_text(),'rss':run(['ps','-p',str(pid),'-o','rss='])}
print(json.dumps(report,indent=2))
'''
if __name__=='__main__':
    result=json.loads(remote(SOURCE,timeout=70))
    (ROOT/'evidence/etherphone-device-verification.json').write_text(json.dumps(result,indent=2)+'\n',encoding='utf-8')
    print(json.dumps(result,indent=2))
