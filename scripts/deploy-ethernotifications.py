"""Coordinated reversible ownership migration, after private ARM64/UI acceptance."""
from pathlib import Path
import hashlib,io,json,runpy,tarfile
ROOT=Path(__file__).resolve().parent.parent
remote=runpy.run_path(str(ROOT/'scripts/check-etherphone-device.py'))['remote']
if __name__=='__main__':
    stage=json.loads((ROOT/'evidence/ethernotifications-shell-stage.json').read_text(encoding='utf-8'))
    assert stage['qa_passed']
    tested=json.loads((ROOT/'evidence/ethernotifications-device/acceptance.json').read_text(encoding='utf-8'))
    for name,digest in tested['sourceHashes'].items():
        assert hashlib.sha256((ROOT/'ethernotifications'/name).read_bytes()).hexdigest()==digest, 'Retest changed source before installation'
    for file in ['ethernotifications-device/acceptance.json','ethernotifications-integration-tests.json']:
        assert all(v['exit']==0 for v in json.loads((ROOT/'evidence'/file).read_text(encoding='utf-8'))['tests'].values())
    assert hashlib.sha256((ROOT/'build/ethershell-notifications_2.1.0_arm64.deb').read_bytes()).hexdigest()==stage['package_sha256']
    names=['ethernotifications_0.1.0_arm64.deb','etheraudio-notifications_0.1.0_arm64.deb','etherphone-notifications_0.1.0_arm64.deb','ethersms-notifications_0.1.0_arm64.deb']
    hashes={name:hashlib.sha256((ROOT/'build'/name).read_bytes()).hexdigest() for name in names}
    payload=io.BytesIO()
    with tarfile.open(fileobj=payload,mode='w:gz') as tar:
        for name in names:tar.add(ROOT/'build'/name,arcname=name)
    source=r'''
import dbus,hashlib,io,json,os,pathlib,shutil,socket,subprocess,sys,tarfile,tempfile,time
assert pathlib.Path('/etc/etherpocket/disk-identity').read_text().strip()=='GM1920-548cb338-mobian-sda21'
stage=pathlib.Path(STAGE['stage']);old=pathlib.Path(STAGE['previous'])
user=['runuser','-u','mobian','--','env','XDG_RUNTIME_DIR=/run/user/1000','DBUS_SESSION_BUS_ADDRESS=unix:path=/run/user/1000/bus']
def run(args):return subprocess.check_output(args,text=True,timeout=20).strip()
def probe():
 return {'boot':pathlib.Path('/proc/sys/kernel/random/boot_id').read_text().strip(),'services':{n:run(['systemctl','is-active',n]) for n in ['ssh','NetworkManager','ModemManager','etherpocket-modem','bluetooth','etherhardware','etherpower','ethershare']},'audioServers':{n:run(user+['systemctl','--user','show',n,'-p','MainPID','--value']) for n in ['pipewire','pipewire-pulse','wireplumber']},'network':run(['nmcli','-t','-f','DEVICE,TYPE,STATE','device'])}
before=probe()
watched={'etheraudio':['/usr/share/etheraudio/core.py','/usr/share/etheraudio/service.py'],'etherphone':['/usr/share/etherphone/core.py','/usr/share/etherphone/service.py','/usr/share/etherphone/provider.py','/usr/bin/etherphone'],'ethernotifications':['/usr/share/ethernotifications/core.py','/usr/share/ethernotifications/service.py']}
def code_hashes():return {name:[hashlib.sha256(pathlib.Path(p).read_bytes()).hexdigest() if pathlib.Path(p).exists() else None for p in paths] for name,paths in watched.items()}
previous_code=code_hashes()
prior_notification_pid=subprocess.run(user+['systemctl','--user','show','ethernotifications','-p','MainPID','--value'],capture_output=True,text=True).stdout.strip()
phone=json.loads(run(user+['etherphone-control','state']));assert phone['ready'] and not phone['calls'],'Refuse migration during calls'
audio=json.loads(run(user+['etheraudio','state']));assert not audio.get('managedCaptures') and not audio.get('recording') and not audio.get('focus'),'Refuse migration during active audio leases/captures'
assert subprocess.run(['pgrep','-u','1000','-x','ethersms'],capture_output=True).returncode!=0,'Close EtherSMS before replacing it'
pids=run(['pgrep','-u','1000','-x','ethershell']).split();assert len(pids)==1
proc=pathlib.Path('/proc')/pids[0];assert (proc/'exe').resolve()==old/'usr/bin/ethershell'
env=dict(x.split('=',1) for x in (proc/'environ').read_bytes().decode().split('\0') if '=' in x)
launcher=pathlib.Path('/home/mobian/.local/bin/ethershell2-start');previous=launcher.read_bytes()
backup_root=pathlib.Path('/var/backups/ethernotifications');backup_root.mkdir(mode=0o700,parents=True,exist_ok=True)
prior=[p for p in sorted(backup_root.iterdir()) if (p/'launcher').exists() and (p/'launcher').read_bytes()==previous and (p/'before.tar.gz').exists()]
backup=prior[0] if prior else backup_root/str(time.time_ns())
if not prior:
 backup.mkdir(mode=0o700)
 with tarfile.open(backup/'before.tar.gz','w:gz') as archive:
  for p in ['/usr/share/etheraudio','/usr/share/etherphone','/usr/bin/etherphone','/usr/bin/ethersms','/usr/lib/systemd/user/etheraudio.service','/usr/lib/systemd/user/etherphone.service']:
   if pathlib.Path(p).exists():archive.add(p,arcname=p.lstrip('/'))
 (backup/'launcher').write_bytes(previous)
newenv=dict(env,ETHERSHELL_SOFT_BLANK='1',PATH=str(stage/'usr/bin')+':'+env.get('PATH','/usr/bin:/bin'),ETHERSHELL_PROFILE_DEFAULT=str(stage/'usr/share/ethershell/profiles.json'))
def shell(action,directory,environment):
 cmd=['/usr/sbin/runuser','-u','mobian','--','/usr/bin/python3',str(directory/'usr/share/ethershell/current_session.py'),action]
 if action=='stop':subprocess.run(cmd,env=environment,check=True,capture_output=True,timeout=20)
 else:
  with open('/var/tmp/ethernotifications-shell.log','ab') as log:subprocess.Popen(cmd,env=environment,stdin=subprocess.DEVNULL,stdout=log,stderr=log,start_new_session=True)
def request(data):
 endpoint='/run/user/1000/ethershell-control-experience-'+env['DISPLAY'].replace(':','').replace('.','-')
 with socket.socket(socket.AF_UNIX,socket.SOCK_STREAM) as client:
  client.settimeout(6);client.connect(endpoint);client.sendall(json.dumps(data).encode()+b'\n');return client.recv(8192).decode().strip()
with tempfile.TemporaryDirectory(dir='/var/tmp') as f:
 folder=pathlib.Path(f)
 with tarfile.open(fileobj=io.BytesIO(sys.stdin.buffer.read()),mode='r:gz') as tar:tar.extractall(folder,filter='data')
 packages=[]
 for name,digest in HASHES.items():
  p=folder/name;assert hashlib.sha256(p.read_bytes()).hexdigest()==digest;packages.append(str(p))
 subprocess.run(['dpkg','--dry-run','-i']+packages,check=True,stdout=sys.stderr)
 subprocess.run(['dpkg','-i']+packages,check=True,stdout=sys.stderr)
subprocess.run(user+['systemctl','--user','daemon-reload'],check=True)
try:
 shell('stop',old,env)
 subprocess.run(user+['systemctl','--user','enable','--now','ethernotifications'],check=True,stdout=sys.stderr)
 current_code=code_hashes()
 restart=[name for name in watched if current_code[name]!=previous_code[name] and (name!='ethernotifications' or prior_notification_pid not in ('','0'))]
 if restart:subprocess.run(user+['systemctl','--user','restart']+restart,check=True)
 text='#!/bin/sh\nset -eu\nexport ETHERSHELL_SOFT_BLANK=1\nexport PATH='+str(stage/'usr/bin')+':"$PATH"\nexport ETHERSHELL_PROFILE_DEFAULT='+newenv['ETHERSHELL_PROFILE_DEFAULT']+'\nexec /usr/bin/python3 '+str(stage/'usr/share/ethershell/current_session.py')+' "$@"\n'
 temp=launcher.with_suffix('.new');temp.write_text(text);temp.chmod(0o755);os.chown(temp,1000,1000);temp.replace(launcher)
 shell('start',stage,newenv)
 state={}
 for _ in range(80):
  time.sleep(.1)
  try:state=json.loads(request({'command':'notification-state'}))
  except (OSError,ValueError):continue
  if state.get('ready'):break
 assert state.get('ready'),state
 assert request({'command':'settings-page','route':'sound'})=='ok';time.sleep(1)
 assert request({'command':'settings-screenshot'})=='ok'
except BaseException:
 subprocess.run(user+['systemctl','--user','disable','--now','ethernotifications'],capture_output=True)
 shell('stop',stage,newenv)
 launcher.write_bytes(previous);launcher.chmod(0o755);os.chown(launcher,1000,1000)
 # Restores previous module code if migration fails; package metadata is kept in
 # the report/backup for explicit repair rather than pretending rollback is dpkg.
 with tarfile.open(backup/'before.tar.gz','r:gz') as archive:archive.extractall('/',filter='data')
 subprocess.run(user+['systemctl','--user','daemon-reload'],capture_output=True)
 subprocess.run(user+['systemctl','--user','restart','etheraudio','etherphone'],capture_output=True)
 shell('start',old,env);raise
after=probe();assert before==after,(before,after)
print(json.dumps({'before':before,'after':after,'stage':str(stage),'previous':str(old),'backup':str(backup),'packages':HASHES,'state':state,'notificationPID':run(user+['systemctl','--user','show','ethernotifications','-p','MainPID','--value']),'unitEnabled':run(user+['systemctl','--user','is-enabled','ethernotifications'])},indent=2))
'''.replace('STAGE',repr({k:stage[k] for k in ('stage','previous','package_sha256')})).replace('HASHES',repr(hashes))
    result=json.loads(remote(source,payload.getvalue(),timeout=120))
    (ROOT/'evidence/ethernotifications-install.json').write_text(json.dumps(result,indent=2),encoding='utf-8')
    print(json.dumps(result,indent=2))
