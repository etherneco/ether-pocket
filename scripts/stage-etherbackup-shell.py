"""Render the real backup Settings page with actual coarse state in isolated X11."""
from pathlib import Path
import hashlib,io,json,runpy,tarfile,subprocess
ROOT=Path(__file__).resolve().parent.parent
remote=runpy.run_path(str(ROOT/'scripts/verify-etherupdate-device.py'))['remote']
if __name__=='__main__':
 package=ROOT/'build/ethershell_2.1.0_etherbackup_arm64.deb'
 # Actual backup state from the installed handset service.
 snapshot=json.loads((ROOT/'evidence/etherbackup-install.json').read_text())['backupState']
 payload=io.BytesIO()
 with tarfile.open(fileobj=payload,mode='w') as archive:
  archive.add(package,arcname='shell.deb');archive.add(ROOT/'scripts/test-ethershell-mobile-ui.py',arcname='qa.py')
  data=json.dumps(snapshot).encode();info=tarfile.TarInfo('state.json');info.size=len(data);archive.addfile(info,io.BytesIO(data))
 source=r'''
import hashlib,io,json,os,pathlib,subprocess,sys,tarfile,tempfile
assert pathlib.Path('/etc/etherpocket/disk-identity').read_text().strip()=='GM1920-548cb338-mobian-sda21'
if True:
 folder=tempfile.mkdtemp(prefix='etherbackup-ui-',dir='/var/tmp')
 root=pathlib.Path(folder)
 with tarfile.open(fileobj=io.BytesIO(sys.stdin.buffer.read()),mode='r:') as archive:archive.extractall(root,filter='data')
 assert hashlib.sha256((root/'shell.deb').read_bytes()).hexdigest()==DIGEST
 subprocess.run(['dpkg-deb','-x',str(root/'shell.deb'),str(root/'stage')],check=True,stdout=sys.stderr)
 for p in [root,*root.rglob('*')]:os.chown(p,1000,1000)
 results={}
 for name,size in [('narrow','360x900x24'),('portrait','1080x2340x24'),('landscape','1000x600x24'),('external','1920x1080x24')]:
  out=root/'results'/name
  cmd=['runuser','-u','mobian','--','env','ETHERSHELL_BACKUP_UI_ONLY=1','ETHERBACKUP_QA_STATE='+str(root/'state.json'),'python3',str(root/'qa.py'),'--binary',str(root/'stage/usr/bin/ethershell'),'--output',str(out),'--suite','settings','--size',size]
  if name=='external':cmd+=['--desktop']
  # Detached desktop helpers must not inherit SSH or capture-pipe descriptors.
  logfile=root/(name+'-runner.log')
  with logfile.open('wb') as log:
   p=subprocess.run(cmd,stdin=subprocess.DEVNULL,stdout=log,stderr=log,timeout=110)
  results[name]=dict(exit=p.returncode,log=logfile.read_text(errors='replace'))
 (root/'results/acceptance.json').write_text(json.dumps(results,indent=2))
 print(json.dumps(dict(path=str(root),acceptance=results)))
'''.replace('DIGEST',repr(hashlib.sha256(package.read_bytes()).hexdigest()))
 result=json.loads(remote(source,payload.getvalue(),timeout=480))
 (ROOT/'evidence/etherbackup-ui-run.json').write_text(json.dumps(result,indent=2)+'\n',encoding='utf-8')
 output=ROOT/'evidence/etherbackup-ui';output.mkdir(exist_ok=True)
 ssh=runpy.run_path(str(ROOT/'scripts/deploy-ethermobile.py'))['SSH']
 assert result['path'].startswith('/var/tmp/etherbackup-ui-') and ' ' not in result['path']
 subprocess.run(['scp',*ssh[1:-1],'-r',ssh[-1]+':'+result['path']+'/results/.',str(output)],capture_output=True,timeout=60,check=True)
 results=json.loads((output/'acceptance.json').read_text())
 passed=all(v['exit']==0 for v in results.values())
 (ROOT/'evidence/etherbackup-ui-package.json').write_text(json.dumps(dict(package_sha256=hashlib.sha256(package.read_bytes()).hexdigest(),passed=passed,source='Actual installed backup state; no invented restore points'),indent=2)+'\n',encoding='utf-8')
 print(json.dumps(results,indent=2));assert passed
