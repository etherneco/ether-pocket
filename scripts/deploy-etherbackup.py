"""Provision tested native backup coordinator and required EtherUpdate hook."""
from pathlib import Path
import hashlib,io,json,runpy,tarfile
ROOT=Path(__file__).resolve().parent.parent
remote=runpy.run_path(str(ROOT/'scripts/verify-etherupdate-device.py'))['remote']
if __name__=='__main__':
 tests=json.loads((ROOT/'evidence/etherbackup-device-tests.json').read_text())
 assert tests['servicesUnchanged'] and all(v['exit']==0 for v in tests['tests'].values())
 files={n:ROOT/'build'/n for n in ('etherbackup_0.1.0_arm64.deb','etherupdate_0.1.0_arm64.deb')}
 hashes={n:hashlib.sha256(p.read_bytes()).hexdigest() for n,p in files.items()}
 payload=io.BytesIO()
 with tarfile.open(fileobj=payload,mode='w') as archive:
  for n,p in files.items():archive.add(p,arcname=n)
 source=r'''
import hashlib,io,json,pathlib,subprocess,sys,tarfile,tempfile,time
assert pathlib.Path('/etc/etherpocket/disk-identity').read_text().strip()=='GM1920-548cb338-mobian-sda21'
def run(args,timeout=30):return subprocess.run(args,capture_output=True,text=True,timeout=timeout,check=True)
def services():return run(['systemctl','show','ssh','NetworkManager','ModemManager','etherpower','etherhardware','etherpocket-modem','bluetooth','-p','MainPID','-p','ActiveState']).stdout
before=services()
old=json.loads(run(['etherupdate','state']).stdout)
assert not old.get('busy') and not old.get('authorizing')
assert all(t['state'] not in ('Preparing','Installing','Health Checking') for t in old.get('history',[]))
with tempfile.TemporaryDirectory(prefix='etherbackup-provision-',dir='/var/tmp') as folder:
 root=pathlib.Path(folder)
 with tarfile.open(fileobj=io.BytesIO(sys.stdin.buffer.read()),mode='r:') as archive:
  for m in archive:
   assert m.isfile() and m.name in HASHES
   data=archive.extractfile(m).read();assert hashlib.sha256(data).hexdigest()==HASHES[m.name];(root/m.name).write_bytes(data)
 args=[str(root/n) for n in HASHES]
 run(['dpkg','--dry-run','-i',*args]);run(['dpkg','--force-confold','-i',*args])
 run(['systemctl','daemon-reload']);run(['systemctl','enable','--now','etherbackup.service'])
 run(['systemctl','restart','etherbackup.service'])
 run(['systemctl','restart','etherupdate.service'])
 for _ in range(30):
  try:
   update=json.loads(run(['etherupdate','state']).stdout)
   if update.get('ready'):break
  except Exception:pass
  time.sleep(.2)
 state=json.loads(run(['etherbackup','status']).stdout)
 assert state['ready'] and not state['destinations'] and not state['history']
 assert state['status']=='Recovery not tested'
 assert before==services()
 # Assert policy is root-owned/private and no backup credential was invented.
 policy=pathlib.Path('/etc/etherbackup/policy.json');assert policy.stat().st_uid==0 and policy.stat().st_mode&0o077==0
 print(json.dumps(dict(packageHashes=HASHES,servicesUnchanged=True,backupState=state,updateReady=update.get('ready'),
  timerEnabled=subprocess.run(['systemctl','is-enabled','etherbackup-scheduled.timer'],capture_output=True,text=True).stdout.strip(),
  backupUnit=run(['systemctl','show','etherbackup','-p','ActiveState','-p','SubState','-p','NRestarts']).stdout,
  sourceContracts=json.loads(policy.read_text()),publication=False)))
'''.replace('HASHES',repr(hashes))
 result=json.loads(remote(source,payload.getvalue(),timeout=150))
 (ROOT/'evidence/etherbackup-install.json').write_text(json.dumps(result,indent=2)+'\n',encoding='utf-8')
 print(json.dumps({k:v for k,v in result.items() if k not in ('sourceContracts',)},indent=2))
