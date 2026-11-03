"""Stage shell beside current release; run all existing Settings acceptance views."""
from pathlib import Path
import hashlib,io,json,runpy,tarfile
ROOT=Path(__file__).resolve().parent.parent
remote=runpy.run_path(str(ROOT/'scripts/check-etherphone-device.py'))['remote']
if __name__=='__main__':
    package=ROOT/'build/ethershell-notifications_2.1.0_arm64.deb'
    digest=hashlib.sha256(package.read_bytes()).hexdigest()
    payload=io.BytesIO()
    with tarfile.open(fileobj=payload,mode='w:gz') as tar:
        tar.add(package,arcname='shell.deb')
        tar.add(ROOT/'scripts/test-ethershell-mobile-ui.py',arcname='ui-test.py')
    source=r'''
import hashlib,io,json,os,pathlib,shutil,subprocess,sys,tarfile,tempfile
assert pathlib.Path('/etc/etherpocket/disk-identity').read_text().strip()=='GM1920-548cb338-mobian-sda21'
stage=pathlib.Path('/opt/ethershell2/2.1.0-notifications-'+DIGEST[:12])
pids=subprocess.check_output(['pgrep','-u','1000','-x','ethershell'],text=True).split();assert len(pids)==1
old=(pathlib.Path('/proc')/pids[0]/'exe').resolve().parent.parent.parent
if not stage.exists():shutil.copytree(old,stage,symlinks=True)
with tempfile.TemporaryDirectory(dir='/var/tmp') as temp:
 folder=pathlib.Path(temp)
 with tarfile.open(fileobj=io.BytesIO(sys.stdin.buffer.read()),mode='r:gz') as tar:tar.extractall(folder,filter='data')
 assert hashlib.sha256((folder/'shell.deb').read_bytes()).hexdigest()==DIGEST
 subprocess.run(['dpkg-deb','-x',str(folder/'shell.deb'),str(stage)],check=True)
 shutil.copyfile(folder/'ui-test.py',stage/'notification-ui-test.py')
folder=pathlib.Path(tempfile.mkdtemp(prefix='ethernotifications-shell-qa-',dir='/var/tmp'));os.chown(folder,1000,1000)
results={}
for name,size in [('narrow','360x900x24'),('landscape','1000x600x24'),('external','1920x1080x24')]:
 out=folder/name
 p=subprocess.run(['runuser','-u','mobian','--','env','XDG_RUNTIME_DIR=/run/user/1000','ETHERMOBILE_EXPECT_REAL_SIM=1','python3',str(stage/'notification-ui-test.py'),'--binary',str(stage/'usr/bin/ethershell'),'--output',str(out),'--size',size,'--suite','settings']+(['--desktop'] if name=='external' else []),capture_output=True,text=True,timeout=110)
 results[name]={'exit':p.returncode,'log':p.stdout+p.stderr}
data={'stage':str(stage),'previous':str(old),'package_sha256':DIGEST,'qa_passed':all(r['exit']==0 for r in results.values()),'tests':results}
(folder/'acceptance.json').write_text(json.dumps(data,indent=2))
with tarfile.open(fileobj=sys.stdout.buffer,mode='w|gz') as archive:
 for p in folder.iterdir():archive.add(p,arcname=p.name)
'''.replace('DIGEST',repr(digest))
    archive=remote(source,payload.getvalue(),timeout=360)
    out=ROOT/'evidence/ethernotifications-shell';out.mkdir(exist_ok=True)
    with tarfile.open(fileobj=io.BytesIO(archive),mode='r:gz') as tar:tar.extractall(out,filter='data')
    result=json.loads((out/'acceptance.json').read_text(encoding='utf-8'))
    (ROOT/'evidence/ethernotifications-shell-stage.json').write_text(json.dumps(result,indent=2),encoding='utf-8')
    print(json.dumps({k:v for k,v in result.items() if k!='tests'},indent=2))
    print(json.dumps({k:v['exit'] for k,v in result['tests'].items()}))
    if not result['qa_passed']:print(json.dumps(result['tests'],indent=2))
    assert result['qa_passed']
