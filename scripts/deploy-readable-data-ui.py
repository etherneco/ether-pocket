"""Install the reviewed ARM64 UI with backups and shell activation rollback."""
from pathlib import Path
import hashlib
import json
import subprocess

ROOT = Path(__file__).resolve().parent.parent
SSH = ['ssh', '-i', str(ROOT/'build/etherpocket_ed25519'), '-o',
       'UserKnownHostsFile='+str(ROOT/'build/mobian-known-hosts'), '-o',
       'BatchMode=yes', '-o', 'ConnectTimeout=5', 'root@10.77.0.2']


def main():
    uploads = {
        'ethershell': ROOT/'build/structured-ui/ethershell-arm64',
        'ethermap': ROOT/'build/structured-ui/ethermap-arm64',
        'etherbluetooth': ROOT/'build/structured-ui/etherbluetooth-arm64',
        'notification-core.py': ROOT/'ethernotifications/core.py',
    }
    hashes = {}
    for name, path in uploads.items():
        data = path.read_bytes()
        hashes[name] = hashlib.sha256(data).hexdigest()
        subprocess.run(SSH+['cat > /var/tmp/readable-ui-'+name], input=data, check=True, timeout=45)
    source = r'''
from pathlib import Path
import hashlib,json,os,shutil,socket,subprocess,time
hashes=HASHES
for name,digest in hashes.items():
 assert hashlib.sha256(Path('/var/tmp/readable-ui-'+name).read_bytes()).hexdigest()==digest
pid=subprocess.check_output(['pgrep','-u','1000','-x','ethershell'],text=True).split()
assert len(pid)==1
proc=Path('/proc')/pid[0]
old=(proc/'exe').resolve().parent.parent.parent
assert str(old).startswith('/opt/ethershell2/')
env=dict(v.split('=',1) for v in (proc/'environ').read_bytes().decode().split('\0') if '=' in v)
stage=old.with_name('2.1.0-readable-data-'+hashes['ethershell'][:12])
assert stage!=old,'This UI build is already active; run verify-readable-data-ui.py instead'
if not stage.exists():shutil.copytree(old,stage,symlinks=True)
shutil.copyfile('/var/tmp/readable-ui-ethershell',stage/'usr/bin/ethershell')
(stage/'usr/bin/ethershell').chmod(0o755)
assert 'not found' not in subprocess.check_output(['ldd',str(stage/'usr/bin/ethershell')],text=True)
launcher=Path('/home/mobian/.local/bin/ethershell2-start')
previous=launcher.read_bytes()
backup=launcher.with_name('ethershell2-start.before-'+stage.name)
if not backup.exists():backup.write_bytes(previous);backup.chmod(0o755);os.chown(backup,1000,1000)
newenv=dict(env,PATH=str(stage/'usr/bin')+':'+env.get('PATH','/usr/bin:/bin'),ETHERSHELL_PROFILE_DEFAULT=str(stage/'usr/share/ethershell/profiles.json'))
user=['/usr/sbin/runuser','-u','mobian','--','env','XDG_RUNTIME_DIR=/run/user/1000','DBUS_SESSION_BUS_ADDRESS=unix:path=/run/user/1000/bus']
targets={Path('/usr/share/ethernotifications/core.py'):'notification-core.py',Path('/usr/bin/ethermap'):'ethermap',Path('/usr/bin/etherbluetooth'):'etherbluetooth'}
originals={}
for target,name in targets.items():
 assert target.is_file() and not target.is_symlink(),str(target)
 if name!='notification-core.py':assert 'not found' not in subprocess.check_output(['ldd','/var/tmp/readable-ui-'+name],text=True)
 originals[target]=target.read_bytes()
 saved=target.with_name(target.name+'.before-readable-data')
 if not saved.exists():shutil.copy2(target,saved)
endpoint='/run/user/1000/ethershell-control-experience-'+env['DISPLAY'].replace(':','').replace('.','-')
def request(data):
 with socket.socket(socket.AF_UNIX,socket.SOCK_STREAM) as s:
  s.settimeout(5);s.connect(endpoint);s.sendall(json.dumps(data).encode()+b'\n');return s.recv(16384).decode().strip()
def shell(action,folder,environment):
 cmd=['/usr/sbin/runuser','-u','mobian','--','python3',str(folder/'usr/share/ethershell/current_session.py'),action]
 if action=='stop':subprocess.run(cmd,env=environment,check=True,capture_output=True,timeout=20)
 else:
  with open('/var/tmp/readable-ui-launch.log','ab') as log:subprocess.Popen(cmd,env=environment,stdin=subprocess.DEVNULL,stdout=log,stderr=log,start_new_session=True)
try:
 for target,name in targets.items():
  incoming=target.with_name(target.name+'.readable-new')
  shutil.copyfile('/var/tmp/readable-ui-'+name,incoming);incoming.chmod(target.stat().st_mode&0o777);incoming.replace(target)
 subprocess.run(user+['systemctl','--user','restart','ethernotifications'],check=True,timeout=20)
 shell('stop',old,env)
 launcher.write_text('#!/bin/sh\nset -eu\nexport ETHERSHELL_SOFT_BLANK=1\nexport PATH='+str(stage/'usr/bin')+':"$PATH"\nexport ETHERSHELL_PROFILE_DEFAULT='+str(stage/'usr/share/ethershell/profiles.json')+'\nexec python3 '+str(stage/'usr/share/ethershell/current_session.py')+' "$@"\n')
 launcher.chmod(0o755);os.chown(launcher,1000,1000)
 shell('start',stage,newenv)
 for _ in range(80):
  try:
   state=json.loads(request({'command':'notification-state'}))
   if state.get('ready'):break
  except (OSError,ValueError):pass
  time.sleep(.2)
 else:raise RuntimeError('Notification UI did not become ready')
 found=subprocess.check_output(['pgrep','-u','1000','-x','ethershell'],text=True).split()
 assert len(found)==1 and (Path('/proc')/found[0]/'exe').resolve()==stage/'usr/bin/ethershell'
except BaseException:
 launcher.write_bytes(previous);launcher.chmod(0o755);os.chown(launcher,1000,1000)
 for target,data in originals.items():
  incoming=target.with_name(target.name+'.rollback');incoming.write_bytes(data);incoming.chmod(target.stat().st_mode&0o777);incoming.replace(target)
 subprocess.run(user+['systemctl','--user','restart','ethernotifications'],timeout=20)
 shell('stop',stage,newenv);shell('start',old,env);raise
print(json.dumps(dict(stage=str(stage),previous=str(old),rollbackLauncher=str(backup),hashes=hashes,notifications=state)))
'''.replace('HASHES', repr(hashes))
    result = subprocess.run(SSH+['python3 -'], input=source, text=True,
                            capture_output=True, timeout=90)
    if result.returncode:
        raise RuntimeError(result.stderr+result.stdout)
    receipt = json.loads(result.stdout)
    (ROOT/'evidence/readable-data-ui-deployment.json').write_text(
        json.dumps(receipt, indent=2)+'\n', encoding='utf-8')
    print(json.dumps(receipt, indent=2))


if __name__ == '__main__':
    main()
