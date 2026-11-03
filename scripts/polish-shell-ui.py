"""Stage, visually verify and activate the touch UI build with rollback."""
from pathlib import Path
import hashlib, io, json, runpy, sys, tarfile

ROOT = Path(__file__).resolve().parent.parent
remote = runpy.run_path(str(ROOT/'scripts/verify-etherupdate-device.py'))['remote']
OUT = ROOT/'evidence/ui-polish'

def stage():
    binary = ROOT/'build/ethershell-ui-polish-arm64'
    digest = hashlib.sha256(binary.read_bytes()).hexdigest()
    payload = io.BytesIO()
    with tarfile.open(fileobj=payload, mode='w') as tar:
        tar.add(binary, arcname='ethershell')
        tar.add(ROOT/'scripts/test-ethershell-mobile-ui.py', arcname='qa.py')
    code = r'''
import hashlib,io,json,os,pathlib,shutil,subprocess,sys,tarfile
assert pathlib.Path('/etc/etherpocket/disk-identity').read_text().strip()=='GM1920-548cb338-mobian-sda21'
pids=subprocess.check_output(['pgrep','-u','1000','-x','ethershell'],text=True).split()
live=[]
for pid in pids:
 proc=pathlib.Path('/proc')/pid
 env=dict(item.split('=',1) for item in (proc/'environ').read_bytes().decode().split('\0') if '=' in item)
 if env.get('DISPLAY','').removesuffix('.0')==':0':live.append(proc)
assert len(live)==1
old=(live[0]/'exe').resolve().parent.parent.parent
assert old.parent==pathlib.Path('/opt/ethershell2')
stage=old.parent/('2.1.0-ui-'+DIGEST[:12]);assert not stage.exists()
shutil.copytree(old,stage,symlinks=True)
with tarfile.open(fileobj=io.BytesIO(sys.stdin.buffer.read()),mode='r:') as tar:
 binary=tar.extractfile('ethershell').read();assert hashlib.sha256(binary).hexdigest()==DIGEST
 (stage/'usr/bin/ethershell').write_bytes(binary)
 qa=stage/'qa.py';qa.write_bytes(tar.extractfile('qa.py').read())
print(json.dumps(dict(stage=str(stage),previous=str(old),binary_sha256=DIGEST)))
'''.replace('DIGEST', repr(digest))
    data = json.loads(remote(code, payload.getvalue()))
    OUT.mkdir(exist_ok=True)
    (OUT/'stage.json').write_text(json.dumps(data,indent=2)+'\n')
    print(json.dumps(data))

def qa():
    data = json.loads((OUT/'stage.json').read_text())
    for name,size in [('narrow','360x900x24'),('portrait','1440x3120x24'),('landscape','1000x600x24')]:
        code=r'''
import hashlib,io,json,os,pathlib,subprocess,sys,tarfile
stage=pathlib.Path(STAGE);out=pathlib.Path('/var/tmp')/(stage.name+'-'+NAME)
out.mkdir(exist_ok=True);os.chown(out,1000,1000)
cmd=['runuser','-u','mobian','--','python3',str(stage/'qa.py'),'--binary',str(stage/'usr/bin/ethershell'),'--output',str(out),'--suite','settings','--size',SIZE]
if NAME=='landscape':cmd+=['--desktop']
with (out/'runner.log').open('wb') as log:p=subprocess.run(cmd,stdout=log,stderr=log,stdin=subprocess.DEVNULL,timeout=110)
(out/'exit.json').write_text(json.dumps({'exit':p.returncode,'binary_sha256':hashlib.sha256((stage/'usr/bin/ethershell').read_bytes()).hexdigest()}))
with tarfile.open(fileobj=sys.stdout.buffer,mode='w|gz') as tar:
 for file in out.iterdir():
  if file.suffix in ('.json','.log') or file.name in ('shell-home.png','home-light.png','home-dark.png','network-light.png','hardware-wireless-dark.png'):tar.add(file,arcname=NAME+'/'+file.name)
'''.replace('STAGE',repr(data['stage'])).replace('NAME',repr(name)).replace('SIZE',repr(size))
        result=remote(code,timeout=125)
        with tarfile.open(fileobj=io.BytesIO(result),mode='r:gz') as tar:tar.extractall(OUT,filter='data')
        checks=json.loads((OUT/name/'results.json').read_text())
        failures=[k for k,v in checks.items() if not v]
        print(json.dumps(dict(size=name,checks=len(checks),failures=failures)),flush=True)
        assert not failures and json.loads((OUT/name/'exit.json').read_text())['exit']==0

def activate():
    data=json.loads((OUT/'stage.json').read_text())
    for name in ['narrow','portrait','landscape']:
        checks=json.loads((OUT/name/'results.json').read_text())
        assert checks and all(checks.values()) and json.loads((OUT/name/'exit.json').read_text())['exit']==0
        assert json.loads((OUT/name/'exit.json').read_text())['binary_sha256']==data['binary_sha256']
    code=r'''
import hashlib,json,os,pathlib,socket,subprocess,time
stage=pathlib.Path(STAGE);old=pathlib.Path(PREVIOUS)
assert hashlib.sha256((stage/'usr/bin/ethershell').read_bytes()).hexdigest()==DIGEST
pids=subprocess.check_output(['pgrep','-u','1000','-x','ethershell'],text=True).split();assert len(pids)==1
proc=pathlib.Path('/proc')/pids[0];assert (proc/'exe').resolve()==old/'usr/bin/ethershell'
env=dict(x.split('=',1) for x in (proc/'environ').read_bytes().decode().split('\0') if '=' in x)
activity="import dbus,json;b=dbus.SessionBus();out={};\nfor c in ('EtherPhone','EtherCamera'):\n n='com.etherneco.'+c+'1';s=json.loads(str(dbus.Interface(b.get_object(n,'/com/etherneco/'+c+'1'),n).GetState(timeout=5)));out[c]=dict(calls=len(s.get('calls',[])),busy=s.get('busy'),recording=s.get('recording'))\nprint(json.dumps(out))"
p=subprocess.run(['runuser','-u','mobian','--','env','XDG_RUNTIME_DIR=/run/user/1000','DBUS_SESSION_BUS_ADDRESS=unix:path=/run/user/1000/bus','python3','-c',activity],capture_output=True,text=True,check=True,timeout=15)
state=json.loads(p.stdout);assert state['EtherPhone']['calls']==0 and not state['EtherCamera']['busy'] and not state['EtherCamera']['recording']
launcher=pathlib.Path('/home/mobian/.local/bin/ethershell2-start');previous=launcher.read_bytes()
backup=launcher.with_name('ethershell2-start.before-'+stage.name)
if backup.exists():assert backup.read_bytes()==previous
else:backup.write_bytes(previous);backup.chmod(0o755);os.chown(backup,1000,1000)
newenv=dict(env,PATH=str(stage/'usr/bin')+':'+env.get('PATH','/usr/bin:/bin'),ETHERSHELL_PROFILE_DEFAULT=str(stage/'usr/share/ethershell/profiles.json'))
def run(action,directory,environment):
 cmd=['/usr/sbin/runuser','-u','mobian','--','/usr/bin/python3',str(directory/'usr/share/ethershell/current_session.py'),action]
 if action=='stop':subprocess.run(cmd,env=environment,check=True,timeout=20,capture_output=True)
 else:
  with open('/var/tmp/ethershell-ui-launch.log','ab') as log:subprocess.Popen(cmd,env=environment,stdin=subprocess.DEVNULL,stdout=log,stderr=log,start_new_session=True)
def request(data):
 with socket.socket(socket.AF_UNIX,socket.SOCK_STREAM) as client:
  client.settimeout(10);client.connect('/run/user/1000/ethershell-control-experience-'+env['DISPLAY'].replace(':','').replace('.','-'));client.sendall(json.dumps(data).encode()+b'\n');return client.recv(8192).decode().strip()
try:
 run('stop',old,env)
 text=previous.decode().replace(str(old),str(stage));assert text!=previous.decode()
 temp=launcher.with_suffix('.new');temp.write_text(text);temp.chmod(0o755);os.chown(temp,1000,1000);temp.replace(launcher)
 run('start',stage,newenv);time.sleep(6)
 found=subprocess.check_output(['pgrep','-u','1000','-x','ethershell'],text=True).split();assert len(found)==1 and (pathlib.Path('/proc')/found[0]/'exe').resolve()==stage/'usr/bin/ethershell'
 assert request({'command':'settings-page','route':'home'})=='ok'
except BaseException:
 launcher.write_bytes(previous);launcher.chmod(0o755);os.chown(launcher,1000,1000)
 run('stop',stage,newenv);run('start',old,env);raise
print(json.dumps({'stage':str(stage),'previous':str(old),'rollback_launcher':str(backup),'pid':found[0]}))
'''.replace('STAGE',repr(data['stage'])).replace('PREVIOUS',repr(data['previous'])).replace('DIGEST',repr(data['binary_sha256']))
    result=json.loads(remote(code,timeout=70))
    (OUT/'deployment.json').write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps(result))

if __name__=='__main__':
    {'stage':stage,'qa':qa,'activate':activate}[sys.argv[1]]()
