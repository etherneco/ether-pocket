"""Render the real sensor Settings page with audited metadata in isolated X11."""
from pathlib import Path
import hashlib,io,json,runpy,tarfile
ROOT=Path(__file__).resolve().parent.parent
remote=runpy.run_path(str(ROOT/'scripts/verify-etherupdate-device.py'))['remote']
if __name__=='__main__':
 package=ROOT/'build/ethershell_2.1.0_ethersensors_arm64.deb'
 # Real discovered metadata from the installed handset service, no fake samples.
 snapshot=json.loads((ROOT/'evidence/ethersensors-install.json').read_text())['sensorState']
 payload=io.BytesIO()
 with tarfile.open(fileobj=payload,mode='w') as archive:
  archive.add(package,arcname='shell.deb');archive.add(ROOT/'scripts/test-ethershell-mobile-ui.py',arcname='qa.py')
  data=json.dumps(snapshot).encode();info=tarfile.TarInfo('state.json');info.size=len(data);archive.addfile(info,io.BytesIO(data))
 source=r'''
import hashlib,io,json,os,pathlib,subprocess,sys,tarfile,tempfile
assert pathlib.Path('/etc/etherpocket/disk-identity').read_text().strip()=='GM1920-548cb338-mobian-sda21'
with tempfile.TemporaryDirectory(prefix='ethersensors-ui-',dir='/var/tmp') as folder:
 root=pathlib.Path(folder)
 with tarfile.open(fileobj=io.BytesIO(sys.stdin.buffer.read()),mode='r:') as archive:archive.extractall(root,filter='data')
 assert hashlib.sha256((root/'shell.deb').read_bytes()).hexdigest()==DIGEST
 subprocess.run(['dpkg-deb','-x',str(root/'shell.deb'),str(root/'stage')],check=True,stdout=sys.stderr)
 for p in [root,*root.rglob('*')]:os.chown(p,1000,1000)
 results={}
 for name,size in [('narrow','360x900x24'),('portrait','1080x2340x24'),('landscape','1000x600x24'),('external','1920x1080x24')]:
  out=root/'results'/name
  cmd=['runuser','-u','mobian','--','env','ETHERSHELL_SENSORS_UI_ONLY=1','ETHERSENSORS_QA_STATE='+str(root/'state.json'),'python3',str(root/'qa.py'),'--binary',str(root/'stage/usr/bin/ethershell'),'--output',str(out),'--suite','settings','--size',size]
  if name=='external':cmd+=['--desktop']
  p=subprocess.run(cmd,capture_output=True,text=True,timeout=110)
  results[name]=dict(exit=p.returncode,log=p.stdout+p.stderr)
 (root/'results/acceptance.json').write_text(json.dumps(results,indent=2))
 with tarfile.open(fileobj=sys.stdout.buffer,mode='w|gz') as archive:
  for p in (root/'results').iterdir():archive.add(p,arcname=p.name)
'''.replace('DIGEST',repr(hashlib.sha256(package.read_bytes()).hexdigest()))
 result=remote(source,payload.getvalue(),timeout=480)
 output=ROOT/'evidence/ethersensors-ui';output.mkdir(exist_ok=True)
 with tarfile.open(fileobj=io.BytesIO(result),mode='r:gz') as archive:archive.extractall(output,filter='data')
 results=json.loads((output/'acceptance.json').read_text())
 passed=all(v['exit']==0 for v in results.values())
 (ROOT/'evidence/ethersensors-ui-package.json').write_text(json.dumps(dict(package_sha256=hashlib.sha256(package.read_bytes()).hexdigest(),passed=passed,source='Real handset discovery metadata; no simulated measurements'),indent=2)+'\n',encoding='utf-8')
 print(json.dumps(results,indent=2));assert passed
