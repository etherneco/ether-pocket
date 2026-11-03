"""Native ARM64 unit and real D-Bus rejection checks in an isolated session."""
from pathlib import Path
import io,json,runpy,tarfile
ROOT=Path(__file__).resolve().parent.parent
remote=runpy.run_path(str(ROOT/'scripts/verify-etherupdate-device.py'))['remote']
if __name__=='__main__':
 payload=io.BytesIO()
 with tarfile.open(fileobj=payload,mode='w') as archive:
  for p in (ROOT/'ethersensors').rglob('*.py'):
   if '__pycache__' not in p.parts:archive.add(p,arcname=p.relative_to(ROOT).as_posix())
 source=r'''
import io,json,os,pathlib,subprocess,sys,tarfile,tempfile
assert pathlib.Path('/etc/etherpocket/disk-identity').read_text().strip()=='GM1920-548cb338-mobian-sda21'
def probe():return subprocess.check_output(['systemctl','show','ssh','NetworkManager','ModemManager','etherhardware','etherpower','-p','MainPID','-p','ActiveState'],text=True)
before=probe()
with tempfile.TemporaryDirectory(prefix='ethersensors-tests-',dir='/var/tmp') as folder:
 with tarfile.open(fileobj=io.BytesIO(sys.stdin.buffer.read()),mode='r:') as archive:archive.extractall(folder,filter='data')
 root=pathlib.Path(folder);os.chmod(root,0o755)
 for p in root.rglob('*'):os.chmod(p,0o755 if p.is_dir() else 0o644)
 results={}
 for name,args in [('unit',['python3','-m','unittest','discover','-s',folder+'/ethersensors/tests','-v']),('bus',['dbus-run-session','--','python3',folder+'/ethersensors/tests/bus_acceptance.py'])]:
  p=subprocess.run(['runuser','-u','mobian','--']+args,capture_output=True,text=True,timeout=45)
  results[name]={'exit':p.returncode,'stdout':p.stdout,'stderr':p.stderr}
 print(json.dumps(dict(architecture=os.uname().machine,tests=results,servicesUnchanged=before==probe())))
'''
 result=json.loads(remote(source,payload.getvalue(),timeout=110))
 (ROOT/'evidence/ethersensors-device-tests.json').write_text(json.dumps(result,indent=2)+'\n',encoding='utf-8')
 print(json.dumps(result,indent=2));assert result['servicesUnchanged'] and all(v['exit']==0 for v in result['tests'].values())
