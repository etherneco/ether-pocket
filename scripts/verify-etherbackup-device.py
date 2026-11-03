"""Isolated real encrypted/restore tests on handset; no production repository."""
from pathlib import Path
import hashlib,io,json,runpy,tarfile
ROOT=Path(__file__).resolve().parent.parent
remote=runpy.run_path(str(ROOT/'scripts/verify-etherupdate-device.py'))['remote']
if __name__=='__main__':
 payload=io.BytesIO()
 restic=ROOT/'build/restic_0.18.0-1+b4_arm64.deb'
 hashes={restic.name:hashlib.sha256(restic.read_bytes()).hexdigest()}
 with tarfile.open(fileobj=payload,mode='w') as archive:
  archive.add(restic,arcname=restic.name)
  for component in ('etherbackup','etherupdate'):
   for p in (ROOT/component).rglob('*.py'):
    if '__pycache__' not in p.parts:archive.add(p,arcname=p.relative_to(ROOT).as_posix())
 source=r'''
import hashlib,io,json,os,pathlib,subprocess,sys,tarfile,tempfile,time
assert pathlib.Path('/etc/etherpocket/disk-identity').read_text().strip()=='GM1920-548cb338-mobian-sda21'
def run(args,timeout=30):return subprocess.run(args,capture_output=True,text=True,timeout=timeout)
def services():return run(['systemctl','show','ssh','NetworkManager','ModemManager','etherpower','etherhardware','etherpocket-modem','bluetooth','-p','MainPID','-p','ActiveState']).stdout
before=services();tests={}
with tempfile.TemporaryDirectory(prefix='etherbackup-verify-',dir='/root') as folder:
 root=pathlib.Path(folder)
 with tarfile.open(fileobj=io.BytesIO(sys.stdin.buffer.read()),mode='r:') as archive:archive.extractall(root,filter='data')
 for name,digest in HASHES.items():assert hashlib.sha256((root/name).read_bytes()).hexdigest()==digest
 package=root/'restic_0.18.0-1+b4_arm64.deb'
 dry=run(['dpkg','--dry-run','-i',str(package)]);assert dry.returncode==0,dry.stderr
 install=run(['dpkg','-i',str(package)]);assert install.returncode==0,install.stderr
 for component in ('etherbackup','etherupdate'):
  started=time.monotonic()
  p=run(['python3','-m','unittest','discover','-s',str(root/component/'tests'),'-v'],240)
  tests[component]=dict(exit=p.returncode,log=p.stdout+p.stderr,durationSeconds=time.monotonic()-started)
 after=services();assert before==after
 print(json.dumps(dict(tests=tests,servicesUnchanged=True,architecture=run(['uname','-m']).stdout.strip(),resticVersion=run(['restic','version']).stdout,installedEnginePackageHash=HASHES,productionBackup=False)))
'''.replace('HASHES',repr(hashes))
 result=json.loads(remote(source,payload.getvalue(),timeout=540))
 (ROOT/'evidence/etherbackup-device-tests.json').write_text(json.dumps(result,indent=2)+'\n',encoding='utf-8')
 print(json.dumps(result,indent=2));assert all(t['exit']==0 for t in result['tests'].values())
