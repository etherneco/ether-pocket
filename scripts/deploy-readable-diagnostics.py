"""Stage, check and activate the readable diagnostics UI without network changes."""
from pathlib import Path
import argparse
import hashlib
import io
import json
import runpy
import tarfile

ROOT = Path(__file__).resolve().parent.parent
remote = runpy.run_path(str(ROOT / 'scripts/deploy-settings2.py'))['remote']

if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--activate', action='store_true')
    args = parser.parse_args()
    binary = (ROOT / 'build/ethershell-diagnostics-arm64').read_bytes()
    digest = hashlib.sha256(binary).hexdigest()
    stage = '/opt/ethershell2/2.1.0-diagnostics-' + digest[:12]
    report_file = ROOT / 'evidence/readable-diagnostics-stage.json'
    if not args.activate:
        source = '''import hashlib,json,pathlib,shutil,sys
assert pathlib.Path('/etc/etherpocket/disk-identity').read_text().strip()=='GM1920-548cb338-mobian-sda21'
data=sys.stdin.buffer.read();assert hashlib.sha256(data).hexdigest()==DIGEST
pid=__import__('subprocess').check_output(['pgrep','-u','1000','-x','ethershell'],text=True).strip()
old=(pathlib.Path('/proc')/pid/'exe').resolve().parent.parent.parent
stage=pathlib.Path(STAGE)
if not stage.exists():shutil.copytree(old,stage,symlinks=True)
(stage/'usr/bin/ethershell').write_bytes(data)
print(json.dumps({'stage':str(stage),'previous':str(old),'binary_sha256':DIGEST}))
'''.replace('DIGEST', repr(digest)).replace('STAGE', repr(stage))
        report = json.loads(remote(source, binary).stdout)
        for local, name in [('scripts/test-ethershell-mobile-ui.py', 'mobile-ui-test.py'), ('build/ethermobile-diagnostics-arm64', 'ethermobile')]:
            source = "import pathlib,sys;p=pathlib.Path(" + repr(stage + '/' + name) + ");p.write_bytes(sys.stdin.buffer.read());p.chmod(0o755)"
            remote(source, (ROOT / local).read_bytes())
        source = '''import json,os,pathlib,subprocess,sys,tarfile
stage=pathlib.Path(STAGE);output=stage/'diagnostics-qa';output.mkdir(exist_ok=True);os.chown(output,1000,1000)
results={}
for name,size,suite in [('narrow-mobile','360x900x24','mobile'),('landscape-mobile','1000x600x24','mobile'),('portrait-settings','1080x2340x24','settings')]:
 p=subprocess.run(['runuser','-u','mobian','--','env','ETHERMOBILE_EXPECT_REAL_SIM=1','ETHERSHELL_DIAGNOSTICS_QA=1','python3',str(stage/'mobile-ui-test.py'),'--binary',str(stage/'usr/bin/ethershell'),'--output',str(output/name),'--size',size,'--suite',suite],capture_output=True,text=True,timeout=110)
 results[name]={'exit':p.returncode,'log':p.stdout+p.stderr}
# The standalone app also runs its real Doctor, in a private offscreen session.
env=dict(os.environ,QT_QPA_PLATFORM='offscreen',QT_QUICK_BACKEND='software',LANG='C.UTF-8')
p=subprocess.run(['runuser','-u','mobian','--','env','QT_QPA_PLATFORM=offscreen','QT_QUICK_BACKEND=software','dbus-run-session','--',str(stage/'ethermobile'),'--compact','--doctor','--smoke-test'],capture_output=True,text=True,timeout=30)
results['standalone']={'exit':p.returncode,'log':p.stdout+p.stderr}
if pathlib.Path('/tmp/ethermobile-smoke-1000.png').exists():__import__('shutil').copy2('/tmp/ethermobile-smoke-1000.png',output/'standalone.png')
(output/'acceptance.json').write_text(json.dumps(results,indent=2))
with tarfile.open(fileobj=sys.stdout.buffer,mode='w|gz') as archive:
 for child in output.iterdir():archive.add(child,arcname=child.name)
'''.replace('STAGE', repr(stage))
        archive = remote(source, timeout=360).stdout
        output = ROOT / 'evidence/readable-diagnostics'
        output.mkdir(exist_ok=True)
        with tarfile.open(fileobj=io.BytesIO(archive), mode='r:gz') as files:
            files.extractall(output, filter='data')
        results = json.loads((output / 'acceptance.json').read_text())
        print(json.dumps({key: value['exit'] for key, value in results.items()}))
        assert all(value['exit'] == 0 for value in results.values()), 'UI checks failed; active shell unchanged'
        report_file.write_text(json.dumps(report, indent=2) + '\n')
    else:
        report = json.loads(report_file.read_text())
        assert report['stage'] == stage and report['binary_sha256'] == digest
        source = '''import hashlib,json,os,pathlib,subprocess,time
stage=pathlib.Path(STAGE)
pid=subprocess.check_output(['pgrep','-u','1000','-x','ethershell'],text=True).strip();proc=pathlib.Path('/proc')/pid
old=(proc/'exe').resolve().parent.parent.parent;assert str(old)==PREVIOUS
assert hashlib.sha256((stage/'usr/bin/ethershell').read_bytes()).hexdigest()==DIGEST
env=dict(i.split('=',1) for i in (proc/'environ').read_bytes().decode().split('\\0') if '=' in i)
launcher=pathlib.Path('/home/mobian/.local/bin/ethershell2-start');previous=launcher.read_bytes()
backup=launcher.with_name('ethershell2-start.before-readable-diagnostics')
assert not backup.exists() or backup.read_bytes()==previous
backup.write_bytes(previous);backup.chmod(0o755);os.chown(backup,1000,1000)
def run(action,directory,environment):
 command=['/usr/sbin/runuser','-u','mobian','--','/usr/bin/python3',str(directory/'usr/share/ethershell/current_session.py'),action]
 if action=='stop':subprocess.run(command,env=environment,check=True,timeout=20,capture_output=True)
 else:
  with open('/var/tmp/ethershell-diagnostics-launch.log','ab') as log:subprocess.Popen(command,env=environment,stdin=subprocess.DEVNULL,stdout=log,stderr=log,start_new_session=True)
newenv=dict(env,PATH=str(stage/'usr/bin')+':'+env['PATH'],ETHERSHELL_PROFILE_DEFAULT=str(stage/'usr/share/ethershell/profiles.json'))
text=previous.decode().replace(str(old),str(stage))
try:
 run('stop',old,env)
 launcher.write_text(text);launcher.chmod(0o755);os.chown(launcher,1000,1000)
 run('start',stage,newenv);time.sleep(6)
 found=subprocess.check_output(['pgrep','-u','1000','-x','ethershell'],text=True).split();assert len(found)==1
 assert (pathlib.Path('/proc')/found[0]/'exe').resolve()==stage/'usr/bin/ethershell'
except BaseException:
 launcher.write_bytes(previous);launcher.chmod(0o755);os.chown(launcher,1000,1000)
 run('stop',stage,newenv);run('start',old,env);raise
# Update the standalone UI atomically, retaining its previous executable.
target=pathlib.Path('/usr/bin/ethermobile');saved=pathlib.Path('/var/backups/ethermobile-before-readable-diagnostics')
if not saved.exists():__import__('shutil').copy2(target,saved)
temporary=target.with_suffix('.diagnostics-new');__import__('shutil').copy2(stage/'ethermobile',temporary);temporary.replace(target)
print(json.dumps({'stage':str(stage),'previous':str(old),'pid':found[0],'mobile_data_service':subprocess.check_output(['systemctl','is-active','ethermobile-data'],text=True).strip()}))
'''.replace('STAGE', repr(stage)).replace('PREVIOUS', repr(report['previous'])).replace('DIGEST', repr(digest))
        installed = json.loads(remote(source, timeout=45).stdout)
        (ROOT / 'evidence/readable-diagnostics-deployment.json').write_text(json.dumps(installed, indent=2) + '\n')
        print(json.dumps(installed, indent=2))
