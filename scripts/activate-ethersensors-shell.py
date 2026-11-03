"""Activate the exact EtherSensors settings shell stage only after its isolated acceptance passes."""
from pathlib import Path
import hashlib,json,runpy,shlex,subprocess
ROOT=Path(__file__).resolve().parent.parent
SSH=runpy.run_path(str(ROOT/'scripts/deploy-ethermobile.py'))['SSH']
if __name__=='__main__':
 data=json.loads((ROOT/'evidence/ethersensors-stage.json').read_text());assert data['qa_passed']
 assert hashlib.sha256((ROOT/'build/ethershell_2.1.0_ethersensors_arm64.deb').read_bytes()).hexdigest()==data['package_sha256']
 acceptance=json.loads((ROOT/'evidence/ethersensors-ui/acceptance.json').read_text());assert set(acceptance)=={'narrow','portrait','landscape','external'} and all(v['exit']==0 for v in acceptance.values())
 # Compare the staged binary with the exact packaged executable before switching.
 binary_check=r'''
import hashlib,io,json,pathlib,subprocess,sys,tarfile,tempfile
payload=sys.stdin.buffer.read();assert hashlib.sha256(payload).hexdigest()==DIGEST
with tempfile.TemporaryDirectory(dir='/var/tmp') as folder:
 p=pathlib.Path(folder)/'shell.deb';p.write_bytes(payload)
 archive=subprocess.check_output(['dpkg-deb','--fsys-tarfile',str(p)])
 with tarfile.open(fileobj=io.BytesIO(archive)) as tar:
  expected=hashlib.sha256(tar.extractfile('./usr/bin/ethershell').read()).hexdigest()
 actual=hashlib.sha256(pathlib.Path(BINARY).read_bytes()).hexdigest()
 assert actual==expected
print(actual)
'''.replace('DIGEST',repr(data['package_sha256'])).replace('BINARY',repr(data['stage']+'/usr/bin/ethershell'))
 expected_binary=subprocess.run(SSH+['python3 -c '+shlex.quote(binary_check)],input=(ROOT/'build/ethershell_2.1.0_ethersensors_arm64.deb').read_bytes(),capture_output=True,check=True,timeout=30).stdout.decode().strip()
 source=r'''
import hashlib,json,os,pathlib,subprocess,time,socket
stage=pathlib.Path(STAGE);old=pathlib.Path(PREVIOUS)
pids=subprocess.check_output(['pgrep','-u','1000','-x','ethershell'],text=True).split();assert len(pids)==1
proc=pathlib.Path('/proc')/pids[0]
running=str((proc/'exe').resolve())
assert running.removesuffix(' (deleted)')==str(old/'usr/bin/ethershell')
assert hashlib.sha256((proc/'exe').read_bytes()).digest()==hashlib.sha256((old/'usr/bin/ethershell').read_bytes()).digest(),'Running predecessor differs from its verified package'
assert hashlib.sha256((stage/'usr/bin/ethershell').read_bytes()).hexdigest()==EXPECTED_BINARY
env=dict(x.split('=',1) for x in (proc/'environ').read_bytes().decode().split('\0') if '=' in x)
launcher=pathlib.Path('/home/mobian/.local/bin/ethershell2-start');previous=launcher.read_bytes()
backup=launcher.with_name('ethershell2-start.before-'+stage.name)
if not backup.exists():backup.write_bytes(previous);backup.chmod(0o755);os.chown(backup,1000,1000)
assert backup.read_bytes()==previous
newenv=dict(env,ETHERSHELL_SOFT_BLANK='1',PATH=str(stage/'usr/bin')+':'+env.get('PATH','/usr/bin:/bin'),ETHERSHELL_PROFILE_DEFAULT=str(stage/'usr/share/ethershell/profiles.json'))
def run(action,directory,environment):
 command=['/usr/sbin/runuser','-u','mobian','--','/usr/bin/python3',str(directory/'usr/share/ethershell/current_session.py'),action]
 if action=='stop':subprocess.run(command,env=environment,check=True,timeout=20,capture_output=True)
 else:
  with open('/var/tmp/ethersensors-shell-launch.log','ab') as log:subprocess.Popen(command,env=environment,stdin=subprocess.DEVNULL,stdout=log,stderr=log,start_new_session=True)
def request(data):
 endpoint='/run/user/1000/ethershell-control-experience-'+env['DISPLAY'].replace(':','').replace('.','-')
 with socket.socket(socket.AF_UNIX,socket.SOCK_STREAM) as client:
  client.settimeout(10);client.connect(endpoint);client.sendall(json.dumps(data).encode()+b'\n');return client.recv(8192).decode().strip()
# Check session-owned activity providers before replacing only the shell.
activity_code="import dbus,json;b=dbus.SessionBus();out={};\nfor c in ('EtherPhone','EtherCamera'):\n n='com.etherneco.'+c+'1';s=json.loads(str(dbus.Interface(b.get_object(n,'/com/etherneco/'+c+'1'),n).GetState(timeout=5)));out[c]=dict(ready=s.get('ready'),calls=len(s.get('calls',[])),busy=s.get('busy'),recording=s.get('recording'))\nprint(json.dumps(out))"
activity=subprocess.run(['/usr/sbin/runuser','-u','mobian','--','env','XDG_RUNTIME_DIR=/run/user/1000','DBUS_SESSION_BUS_ADDRESS=unix:path=/run/user/1000/bus','python3','-c',activity_code],capture_output=True,text=True,check=True,timeout=15)
activity=json.loads(activity.stdout)
assert activity['EtherPhone']['ready'] and activity['EtherPhone']['calls']==0
assert activity['EtherCamera']['ready'] and activity['EtherCamera']['busy'] is False and activity['EtherCamera']['recording'] is False
try:
 run('stop',old,env)
 text='#!/bin/sh\nset -eu\nexport ETHERSHELL_SOFT_BLANK=1\nexport PATH='+str(stage/'usr/bin')+':"$PATH"\nexport ETHERSHELL_PROFILE_DEFAULT='+newenv['ETHERSHELL_PROFILE_DEFAULT']+'\nexec /usr/bin/python3 '+str(stage/'usr/share/ethershell/current_session.py')+' "$@"\n'
 temporary=launcher.with_suffix('.new');temporary.write_text(text);temporary.chmod(0o755);os.chown(temporary,1000,1000);temporary.replace(launcher)
 run('start',stage,newenv);time.sleep(6)
 found=subprocess.check_output(['pgrep','-u','1000','-x','ethershell'],text=True).split();assert len(found)==1 and (pathlib.Path('/proc')/found[0]/'exe').resolve()==stage/'usr/bin/ethershell'
 assert request({'command':'settings-page','route':'sensors'})=='ok';time.sleep(1.2)
 state=json.loads(request({'command':'settings-state'}));assert state['route']=='sensors'
 assert request({'command':'settings-screenshot'})=='ok'
except BaseException:
 launcher.write_bytes(previous);launcher.chmod(0o755);os.chown(launcher,1000,1000)
 run('stop',stage,newenv);run('start',old,env);raise
print(json.dumps({'stage':str(stage),'previous':str(old),'rollback_launcher':str(backup),'pid':found[0],'settings_route':state['route'],'services':subprocess.run(['systemctl','is-active','NetworkManager','ssh','bluetooth','etherpocket-modem','ModemManager'],capture_output=True,text=True).stdout.splitlines()}))
'''.replace('STAGE',repr(data['stage'])).replace('PREVIOUS',repr(data['previous'])).replace('EXPECTED_BINARY',repr(expected_binary))
 r=subprocess.run(SSH+['python3 -c '+shlex.quote(source)],capture_output=True,timeout=80)
 if r.returncode:raise RuntimeError(r.stderr.decode(errors='replace')[-3000:])
 result=json.loads(r.stdout)
 (ROOT/'evidence/ethersensors-deployment.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result,indent=2))
