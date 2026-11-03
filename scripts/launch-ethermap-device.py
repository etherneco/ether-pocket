"""Open EtherMAP through the real EtherShell launcher and verify foreground identity."""
from pathlib import Path
import io,json,runpy,subprocess,tarfile
ROOT=Path(__file__).resolve().parents[1]
SSH=runpy.run_path(str(ROOT/'scripts/deploy-ethermobile.py'))['SSH']
SOURCE=r'''
import json,os,pathlib,re,socket,subprocess,sys,tarfile,time
shells=subprocess.check_output(['pgrep','-u','1000','-x','ethershell'],text=True).split();assert len(shells)==1
proc=pathlib.Path('/proc')/shells[0]
env=dict(x.split('=',1) for x in (proc/'environ').read_bytes().decode().split('\0') if '=' in x)
user=['runuser','-u','mobian','--','env','LANG=C.UTF-8','DISPLAY='+env['DISPLAY'],'XAUTHORITY='+env['XAUTHORITY'],'XDG_RUNTIME_DIR=/run/user/1000','DBUS_SESSION_BUS_ADDRESS=unix:path=/run/user/1000/bus']
endpoint='/run/user/1000/ethershell-control-experience-'+env['DISPLAY'].replace(':','').replace('.','-')
def request(row):
 with socket.socket(socket.AF_UNIX,socket.SOCK_STREAM) as client:
  client.settimeout(10);client.connect(endpoint);client.sendall(json.dumps(row).encode()+b'\n');return client.recv(8192).decode().strip()
existing=subprocess.run(['pgrep','-u','1000','-x','ethermap'],capture_output=True,text=True)
if existing.returncode:assert request(dict(command='launch',id='ethermap.desktop'))=='ok'
for _ in range(50):
 p=subprocess.run(['pgrep','-u','1000','-x','ethermap'],capture_output=True,text=True)
 if p.returncode==0:break
 time.sleep(.2)
pids=p.stdout.split();assert len(pids)==1,p.stdout
pid=pids[0];time.sleep(4)
windows=subprocess.check_output(user+['wmctrl','-lp'],text=True)
matches=[line for line in windows.splitlines() if re.match(r'^\S+\s+\S+\s+'+pid+r'\s',line)]
assert matches,windows
wid=matches[0].split()[0]
subprocess.run(user+['wmctrl','-ia',wid],check=True);time.sleep(1)
sys.path.insert(0,'/usr/share/etherlocation')
from identity import application
identity=application(int(pid));assert identity=='ethermap'
workers=[]
for path in pathlib.Path('/proc').iterdir():
 if path.name.isdigit():
  try:
   if b'/usr/share/ethermap/backend.py' in (path/'cmdline').read_bytes():workers.append(dict(pid=path.name,identity=application(int(path.name))))
  except (FileNotFoundError,PermissionError,ProcessLookupError):pass
assert len(workers)==1 and workers[0]['identity']=='ethermap',workers
state=json.loads(subprocess.check_output(user+['etherlocation','state'],text=True));assert not state['active']
folder=pathlib.Path('/var/tmp/ethermap-live-acceptance');folder.mkdir(exist_ok=True);os.chown(folder,1000,1000)
preview=folder/'live-map.png'
subprocess.run(user+['scrot','-u','-o',str(preview)],check=True,capture_output=True)
assert preview.exists()
result=dict(shellPid=shells[0],shellBinary=str((proc/'exe').resolve()),pid=pid,window=wid,identity=identity,workers=workers,windows=matches,state=state,
 locationHistoryCreated=pathlib.Path('/home/mobian/.local/share/etherlocation/history.sqlite').exists(),trackDatabaseCreated=pathlib.Path('/home/mobian/.local/share/ethermap/tracks.sqlite').exists(),
 services=subprocess.check_output(['systemctl','is-active','ssh','NetworkManager','etherhardware','etherpower','ModemManager'],text=True).splitlines())
assert not result['trackDatabaseCreated']
(folder/'result.json').write_text(json.dumps(result,indent=2)+'\n')
with tarfile.open(fileobj=sys.stdout.buffer,mode='w|gz') as tar:
 tar.add(folder/'result.json',arcname='result.json');tar.add(preview,arcname='live-map.png')
'''
if __name__=='__main__':
 p=subprocess.run(SSH+['python3 -'],input=SOURCE.encode(),capture_output=True,timeout=45)
 if p.returncode:raise RuntimeError(p.stderr.decode(errors='replace')[-4000:])
 target=ROOT/'evidence/ethermap-live';target.mkdir(exist_ok=True)
 with tarfile.open(fileobj=io.BytesIO(p.stdout),mode='r:gz') as tar:tar.extractall(target,filter='data')
 result=json.loads((target/'result.json').read_text());print(json.dumps({k:result[k] for k in ['pid','window','identity','workers','trackDatabaseCreated','services']},indent=2))
