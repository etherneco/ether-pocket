"""Render the native Software Updates page in isolated unprivileged X11."""
from pathlib import Path
import hashlib
import io
import json
import runpy
import tarfile
ROOT=Path(__file__).resolve().parent.parent
remote=runpy.run_path(str(ROOT/'scripts/verify-etherupdate-device.py'))['remote']


if __name__=='__main__':
    package=ROOT/'build/ethershell_2.1.0_etherupdate_arm64.deb'
    snapshot=dict(ready=True,agentVersion='0.1.0',server='https://autoupddate.etherneco.com',busy=False,
                  discovery=dict(status='No compatible release',lastSuccessfulCheck=1792584000,updates=[dict(project='qa-only',name='EtherShell (isolated visual fixture)',installed='2.1.0',version='2.2.0',channel='Stable',
                       status='No compatible release',compatible=False,reason='Publisher signature not commissioned',notes='Review release notes, device compatibility and recovery before installing.',size=1048576)]),
                  history=[],trustKeys=[],cacheUsage=0)
    payload=io.BytesIO()
    with tarfile.open(fileobj=payload,mode='w') as tar:
        tar.add(package,arcname='shell.deb');tar.add(ROOT/'scripts/test-ethershell-mobile-ui.py',arcname='qa.py')
        data=json.dumps(snapshot).encode();info=tarfile.TarInfo('state.json');info.size=len(data);tar.addfile(info,io.BytesIO(data))
    source=r'''
import hashlib,io,json,os,pathlib,subprocess,sys,tarfile,tempfile
assert pathlib.Path('/etc/etherpocket/disk-identity').read_text().strip()=='GM1920-548cb338-mobian-sda21'
with tempfile.TemporaryDirectory(prefix='etherupdate-ui-',dir='/var/tmp') as folder:
 root=pathlib.Path(folder)
 with tarfile.open(fileobj=io.BytesIO(sys.stdin.buffer.read()),mode='r:') as tar:tar.extractall(root,filter='data')
 assert hashlib.sha256((root/'shell.deb').read_bytes()).hexdigest()==DIGEST
 subprocess.run(['dpkg-deb','-x',str(root/'shell.deb'),str(root/'stage')],check=True,stdout=sys.stderr)
 for p in [root,*root.rglob('*')]:
  os.chown(p,1000,1000)
 results={}
 for name,size in [('narrow','360x900x24'),('portrait','1080x2340x24'),('landscape','1000x600x24'),('external','1920x1080x24')]:
  out=root/'results'/name
  cmd=['runuser','-u','mobian','--','env','ETHERSHELL_UPDATE_UI_ONLY=1','ETHERUPDATE_QA_STATE='+str(root/'state.json'),'python3',str(root/'qa.py'),'--binary',str(root/'stage/usr/bin/ethershell'),'--output',str(out),'--suite','settings','--size',size]
  if name=='external':cmd+=['--desktop']
  p=subprocess.run(cmd,capture_output=True,text=True,timeout=110)
  results[name]=dict(exit=p.returncode,log=p.stdout+p.stderr)
 (root/'results/acceptance.json').write_text(json.dumps(results,indent=2))
 with tarfile.open(fileobj=sys.stdout.buffer,mode='w|gz') as tar:
  for p in (root/'results').iterdir():tar.add(p,arcname=p.name)
'''.replace('DIGEST',repr(hashlib.sha256(package.read_bytes()).hexdigest()))
    result=remote(source,payload.getvalue(),timeout=480)
    output=ROOT/'evidence/etherupdate-ui';output.mkdir(exist_ok=True)
    with tarfile.open(fileobj=io.BytesIO(result),mode='r:gz') as tar:tar.extractall(output,filter='data')
    results=json.loads((output/'acceptance.json').read_text())
    (ROOT/'evidence/etherupdate-ui-package.json').write_text(json.dumps(dict(package_sha256=hashlib.sha256(package.read_bytes()).hexdigest(),passed=all(v['exit']==0 for v in results.values())),indent=2)+'\n',encoding='utf-8')
    print(json.dumps(results,indent=2));assert all(v['exit']==0 for v in results.values())
