"""Stage EtherShell EtherShare integration and run existing isolated UI acceptance."""
from pathlib import Path
import hashlib,io,json,runpy,shlex,subprocess,tarfile,os
ROOT=Path(__file__).resolve().parent.parent
SSH=runpy.run_path(str(ROOT/'scripts/deploy-ethermobile.py'))['SSH']
def remote(source,payload=None,timeout=120):
 r=subprocess.run(SSH+['python3 -c '+shlex.quote(source)],input=payload,capture_output=True,timeout=timeout)
 if r.returncode:raise RuntimeError(r.stderr.decode(errors='replace')[-6000:])
 return r.stdout
if __name__=='__main__':
 package=ROOT/'build/ethershell-share_2.1.0_arm64.deb';digest=hashlib.sha256(package.read_bytes()).hexdigest()
 stage='/opt/ethershell2/2.1.0-share-'+digest[:12]
 source=r'''
import hashlib,json,pathlib,subprocess,sys,tempfile,shutil
assert pathlib.Path('/etc/etherpocket/disk-identity').read_text().strip()=='GM1920-548cb338-mobian-sda21'
payload=sys.stdin.buffer.read();assert hashlib.sha256(payload).hexdigest()==DIGEST
pids=subprocess.check_output(['pgrep','-u','1000','-x','ethershell'],text=True).split();assert len(pids)==1
old=(pathlib.Path('/proc')/pids[0]/'exe').resolve().parent.parent.parent
stage=pathlib.Path(STAGE)
if not stage.exists():shutil.copytree(old,stage,symlinks=True)
with tempfile.TemporaryDirectory(dir='/var/tmp') as f:
 p=pathlib.Path(f)/'shell.deb';p.write_bytes(payload);subprocess.run(['dpkg-deb','-x',str(p),str(stage)],check=True)
print(json.dumps({'stage':str(stage),'previous':str(old),'package_sha256':DIGEST}))
'''.replace('DIGEST',repr(digest)).replace('STAGE',repr(stage))
 data=json.loads(remote(source,package.read_bytes()));print(json.dumps(data),flush=True)
 runner=(ROOT/'scripts/test-ethershell-mobile-ui.py').read_bytes()
 remote("from pathlib import Path;import sys;Path("+repr(stage+'/sharing-ui-test.py')+").write_bytes(sys.stdin.buffer.read())",runner)
 source=r'''
import json,os,pathlib,subprocess,sys,tarfile
stage=pathlib.Path(STAGE);folder=pathlib.Path('/var/tmp/ethershare-shell-qa-'+stage.name);folder.mkdir(exist_ok=True);os.chown(folder,1000,1000);results={}
for name,size in VIEWS:
 out=folder/name
 p=subprocess.run(['/usr/sbin/runuser','-u','mobian','--','env','ETHERMOBILE_EXPECT_REAL_SIM=1','python3',str(stage/'sharing-ui-test.py'),'--binary',str(stage/'usr/bin/ethershell'),'--output',str(out),'--size',size,'--suite','settings']+(['--desktop'] if name=='external' else []),capture_output=True,text=True,timeout=110)
 results[name]={'exit':p.returncode,'log':p.stdout+p.stderr}
(folder/'acceptance.json').write_text(json.dumps(results,indent=2))
with tarfile.open(fileobj=sys.stdout.buffer,mode='w|gz') as archive:
 for child in folder.iterdir():archive.add(child,arcname=child.name)
'''.replace('STAGE',repr(stage)).replace('VIEWS',repr([(k,v) for k,v in [('narrow','360x900x24'),('landscape','1000x600x24'),('external','1920x1080x24')] if k in os.environ.get('ETHERSHARE_QA_VIEWS','narrow,landscape,external').split(',')]))
 archive=remote(source,timeout=360);out=ROOT/'evidence/ethershare-settings-device';out.mkdir(exist_ok=True)
 with tarfile.open(fileobj=io.BytesIO(archive),mode='r:gz') as tar:tar.extractall(out,filter='data')
 results=json.loads((out/'acceptance.json').read_text());data['qa_passed']=all(v['exit']==0 for v in results.values())
 (ROOT/'evidence/ethershare-shell-stage.json').write_text(json.dumps(data,indent=2)+'\n')
 print(json.dumps({k:v['exit'] for k,v in results.items()}));assert data['qa_passed'],'Production shell unchanged; inspect isolated acceptance logs'
