"""Activate the exact tested shell, preserving the previous launcher for rollback."""
from pathlib import Path
import hashlib
import json
import runpy

ROOT = Path(__file__).resolve().parent.parent
remote = runpy.run_path(str(ROOT / 'scripts/verify-etherupdate-device.py'))['remote']

if __name__ == '__main__':
    qa = json.loads((ROOT / 'evidence/etherkeyboard-qa.json').read_text())
    assert all(run['exit'] == 0 and run['results'] and all(run['results'].values()) for run in qa['runs'].values())
    assert all(qa['runs']['hotplug']['results'][name] for name in ('keyboard-hotplug-hides', 'keyboard-physical-suppresses', 'keyboard-unplug-opens'))
    assert hashlib.sha256((ROOT / 'build/ethershell-keyboard-arm64').read_bytes()).hexdigest() == qa['sha256']
    source = r'''
import hashlib,json,os,pathlib,shutil,socket,subprocess,time
qa=QA
old=pathlib.Path(qa['previous']);stage=pathlib.Path('/opt/ethershell2/2.1.0-keyboard-'+qa['sha256'][:12])
assert old.parent==stage.parent and old!=stage
pid=subprocess.check_output(['pgrep','-u','1000','-x','ethershell'],text=True).strip()
proc=pathlib.Path('/proc')/pid
assert (proc/'exe').resolve()==old/'usr/bin/ethershell'
env=dict(item.split('=',1) for item in (proc/'environ').read_bytes().decode().split('\0') if '=' in item)
binary=pathlib.Path(qa['path'])/'ethershell'
assert hashlib.sha256(binary.read_bytes()).hexdigest()==qa['sha256']
if not stage.exists():
    shutil.copytree(old,stage)
    shutil.copy2(binary,stage/'usr/bin/ethershell')
assert hashlib.sha256((stage/'usr/bin/ethershell').read_bytes()).hexdigest()==qa['sha256']
ldd=subprocess.check_output(['ldd',str(stage/'usr/bin/ethershell')],text=True);assert 'not found' not in ldd
launcher=pathlib.Path('/home/mobian/.local/bin/ethershell2-start')
previous=launcher.read_bytes();backup=launcher.with_name('ethershell2-start.before-'+stage.name)
if not backup.exists():backup.write_bytes(previous);backup.chmod(0o755);os.chown(backup,1000,1000)
newenv=dict(env,ETHERSHELL_SOFT_BLANK='1',PATH=str(stage/'usr/bin')+':'+env.get('PATH','/usr/bin:/bin'),ETHERSHELL_PROFILE_DEFAULT=str(stage/'usr/share/ethershell/profiles.json'))
def run(action,directory,environment):
    command=['/usr/sbin/runuser','-u','mobian','--','/usr/bin/python3',str(directory/'usr/share/ethershell/current_session.py'),action]
    if action=='stop':subprocess.run(command,env=environment,check=True,timeout=20,capture_output=True)
    else:
        with open('/var/tmp/etherkeyboard-launch.log','ab') as log:subprocess.Popen(command,env=environment,stdin=subprocess.DEVNULL,stdout=log,stderr=log,start_new_session=True)
def request(payload):
    endpoint='/run/user/1000/ethershell-control-experience-'+env['DISPLAY'].replace(':','').replace('.','-')
    with socket.socket(socket.AF_UNIX,socket.SOCK_STREAM) as client:
        client.settimeout(10);client.connect(endpoint);client.sendall(json.dumps(payload).encode()+b'\n');return client.recv(16384).decode().strip()
activity_code="import dbus,json;b=dbus.SessionBus();out={};\nfor c in ('EtherPhone','EtherCamera'):\n n='com.etherneco.'+c+'1';s=json.loads(str(dbus.Interface(b.get_object(n,'/com/etherneco/'+c+'1'),n).GetState(timeout=5)));out[c]=dict(ready=s.get('ready'),calls=len(s.get('calls',[])),busy=s.get('busy'),recording=s.get('recording'))\nprint(json.dumps(out))"
activity=json.loads(subprocess.check_output(['runuser','-u','mobian','--','env','XDG_RUNTIME_DIR=/run/user/1000','DBUS_SESSION_BUS_ADDRESS=unix:path=/run/user/1000/bus','python3','-c',activity_code],text=True,timeout=15))
assert activity['EtherPhone']['calls']==0 and not activity['EtherCamera']['busy'] and not activity['EtherCamera']['recording']
try:
    run('stop',old,env)
    text='#!/bin/sh\nset -eu\nexport ETHERSHELL_SOFT_BLANK=1\nexport PATH='+str(stage/'usr/bin')+':"$PATH"\nexport ETHERSHELL_PROFILE_DEFAULT='+newenv['ETHERSHELL_PROFILE_DEFAULT']+'\nexec /usr/bin/python3 '+str(stage/'usr/share/ethershell/current_session.py')+' "$@"\n'
    temporary=launcher.with_suffix('.new');temporary.write_text(text);temporary.chmod(0o755);os.chown(temporary,1000,1000);temporary.replace(launcher)
    run('start',stage,newenv);time.sleep(6)
    found=subprocess.check_output(['pgrep','-u','1000','-x','ethershell'],text=True).split()
    assert len(found)==1 and (pathlib.Path('/proc')/found[0]/'exe').resolve()==stage/'usr/bin/ethershell'
    assert request({'command':'settings-page','route':'input'})=='ok';time.sleep(1)
    state=json.loads(request({'command':'settings-state'}));assert state['route']=='input'
except BaseException:
    launcher.write_bytes(previous);launcher.chmod(0o755);os.chown(launcher,1000,1000)
    run('stop',stage,newenv);run('start',old,env);raise
print(json.dumps({'stage':str(stage),'previous':str(old),'rollbackLauncher':str(backup),'pid':found[0],'state':state,'sha256':qa['sha256']}))
'''.replace('QA', repr({key: qa[key] for key in ('path', 'previous', 'sha256')}))
    data = json.loads(remote(source, timeout=80))
    (ROOT / 'evidence/etherkeyboard-deployment.json').write_text(json.dumps(data, indent=2) + '\n', encoding='utf-8')
    print(json.dumps(data, indent=2))
