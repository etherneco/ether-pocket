"""Stage and render Mobile Settings; optionally switch the existing user launcher.

Preserves the exact previous stage, soft blanking and session helper. No network,
radio, WM or shared service restart. Activation automatically restores the old
launcher if the new shell fails its process/socket startup checks.
"""
from pathlib import Path
import argparse
import hashlib
import io
import json
import runpy
import shlex
import subprocess
import tarfile

ROOT=Path(__file__).resolve().parent.parent
SSH=runpy.run_path(str(ROOT/'scripts/deploy-ethermobile.py'))['SSH']

def remote(source,payload=None,timeout=120):
    result=subprocess.run(SSH+['python3 -c '+shlex.quote(source)],input=payload,capture_output=True,timeout=timeout)
    if result.returncode:raise RuntimeError(result.stderr.decode('utf-8',errors='replace'))
    return result

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--activate',action='store_true')
    args=parser.parse_args()
    payload=(ROOT/'build/ethershell_2.0.2_arm64.deb').read_bytes()
    digest=hashlib.sha256(payload).hexdigest()
    stage='/opt/ethershell2/2.0.2-mobile-'+digest[:12]
    source=r'''import hashlib,json,pathlib,shutil,subprocess,sys,tempfile
assert pathlib.Path('/etc/etherpocket/disk-identity').read_text().strip()=='GM1920-548cb338-mobian-sda21'
payload=sys.stdin.buffer.read();assert hashlib.sha256(payload).hexdigest()==DIGEST
pids=subprocess.check_output(['pgrep','-u','1000','-x','ethershell'],text=True).split();assert len(pids)==1
old=(pathlib.Path('/proc')/pids[0]/'exe').resolve().parent.parent.parent
assert old.parent==pathlib.Path('/opt/ethershell2')
stage=pathlib.Path(STAGE)
if not stage.exists():shutil.copytree(old,stage,symlinks=True)
with tempfile.TemporaryDirectory(prefix='mobile-settings-',dir='/run') as folder:
 package=pathlib.Path(folder)/'shell.deb';package.write_bytes(payload)
 subprocess.run(['dpkg-deb','--extract',str(package),str(stage)],check=True)
subprocess.run(['ldd',str(stage/'usr/bin/ethershell')],check=True,capture_output=True)
print(json.dumps({'stage':str(stage),'previous':str(old),'package_sha256':DIGEST}))
'''.replace('DIGEST',repr(digest)).replace('STAGE',repr(stage))
    staged=json.loads(remote(source,payload).stdout)
    helper=(ROOT/'scripts/test-ethershell-mobile-ui.py').read_bytes()
    remote("import pathlib,sys;p=pathlib.Path("+repr(stage+'/mobile-ui-test.py')+");p.write_bytes(sys.stdin.buffer.read());p.chmod(0o755)",helper)
    # Each test uses its own authenticated private X server and user data.
    source=r'''import json,os,pathlib,subprocess,sys,tarfile,tempfile
stage=pathlib.Path(STAGE);results={}
with tempfile.TemporaryDirectory(prefix='ethershell-mobile-qa-',dir='/var/tmp') as folder:
 root=pathlib.Path(folder);os.chown(root,1000,1000)
 for name,size in [('portrait','480x1000x24'),('landscape','1000x600x24'),('external','1920x1080x24')]:
  output=root/name
  p=subprocess.run(['runuser','-u','mobian','--','env','ETHERMOBILE_EXPECT_REAL_SIM=1','python3',str(stage/'mobile-ui-test.py'),'--binary',str(stage/'usr/bin/ethershell'),'--output',str(output),'--size',size],capture_output=True,text=True,timeout=110)
  results[name]={'exit':p.returncode,'log':p.stdout+p.stderr}
 (root/'acceptance.json').write_text(json.dumps(results,indent=2))
 with tarfile.open(fileobj=sys.stdout.buffer,mode='w|gz') as archive:
  for child in root.iterdir():archive.add(child,arcname=child.name)
'''.replace('STAGE',repr(stage))
    archive=remote(source,timeout=360).stdout
    output=ROOT/'evidence/ethershell-mobile-device'
    output.mkdir(parents=True,exist_ok=True)
    with tarfile.open(fileobj=io.BytesIO(archive),mode='r:gz') as files:
        for item in files.getmembers():
            target=(output/item.name).resolve()
            assert target.is_relative_to(output.resolve()) and not item.issym() and not item.islnk()
        files.extractall(output,filter='data')
    results=json.loads((output/'acceptance.json').read_text())
    print(json.dumps({k:v['exit'] for k,v in results.items()}))
    assert all(v['exit']==0 for v in results.values()),'UI tests failed; production launcher unchanged'
    (ROOT/'evidence/mobile-settings-stage.json').write_text(json.dumps(staged,indent=2)+'\n')
    if not args.activate:return
    source=r'''import hashlib,json,os,pathlib,subprocess,time
stage=pathlib.Path(STAGE);pids=subprocess.check_output(['pgrep','-u','1000','-x','ethershell'],text=True).split();assert len(pids)==1
proc=pathlib.Path('/proc')/pids[0];old=(proc/'exe').resolve().parent.parent.parent
assert str(old)==PREVIOUS
env=dict(item.split('=',1) for item in (proc/'environ').read_bytes().decode().split('\0') if '=' in item)
launcher=pathlib.Path('/home/mobian/.local/bin/ethershell2-start');previous=launcher.read_bytes()
backup=launcher.with_name('ethershell2-start.before-mobile-settings')
assert not backup.exists() or backup.read_bytes()==previous,'Existing rollback launcher differs; review before overwriting'
if not backup.exists():backup.write_bytes(previous);backup.chmod(0o755);os.chown(backup,1000,1000)
def run(action,directory,environment):
 command=['/usr/sbin/runuser','-u','mobian','--','/usr/bin/python3',str(directory/'usr/share/ethershell/current_session.py'),action]
 if action=='stop':subprocess.run(command,env=environment,check=True,timeout=20,capture_output=True)
 else:
  with open('/var/tmp/ethershell-mobile-launch.log','ab') as log:subprocess.Popen(command,env=environment,stdin=subprocess.DEVNULL,stdout=log,stderr=log,start_new_session=True)
newenv=dict(env,ETHERSHELL_SOFT_BLANK='1',PATH=str(stage/'usr/bin')+':'+env.get('PATH','/usr/bin:/bin'),ETHERSHELL_PROFILE_DEFAULT=str(stage/'usr/share/ethershell/profiles.json'))
text='#!/bin/sh\nset -eu\nexport ETHERSHELL_SOFT_BLANK=1\nexport PATH='+str(stage/'usr/bin')+':"$PATH"\nexport ETHERSHELL_PROFILE_DEFAULT='+newenv['ETHERSHELL_PROFILE_DEFAULT']+'\nexec /usr/bin/python3 '+str(stage/'usr/share/ethershell/current_session.py')+' "$@"\n'
try:
 run('stop',old,env)
 temporary=launcher.with_suffix('.new');temporary.write_text(text);temporary.chmod(0o755);os.chown(temporary,1000,1000);temporary.replace(launcher)
 run('start',stage,newenv)
 time.sleep(6)
 found=subprocess.run(['pgrep','-u','1000','-x','ethershell'],capture_output=True,text=True).stdout.split()
 assert len(found)==1 and (pathlib.Path('/proc')/found[0]/'exe').resolve()==stage/'usr/bin/ethershell','New shell did not stay running'
 sockets=list(pathlib.Path('/run/user/1000').glob('ethershell-control-*'));assert sockets,'Shell control endpoint missing'
except BaseException:
 launcher.write_bytes(previous);launcher.chmod(0o755);os.chown(launcher,1000,1000)
 run('stop',stage,newenv);run('start',old,env)
 raise
print(json.dumps({'stage':str(stage),'pid':found[0],'uid':1000,'previous':str(old),'rollback_launcher':str(backup),'soft_blank':True}))
'''.replace('STAGE',repr(stage)).replace('PREVIOUS',repr(staged['previous']))
    installed=json.loads(remote(source,timeout=60).stdout)
    (ROOT/'evidence/mobile-settings-deployment.json').write_text(json.dumps(installed,indent=2)+'\n')
    print(json.dumps(installed,indent=2))

if __name__=='__main__':main()
