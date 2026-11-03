"""Install software blanking beside the active build, retaining its exact UI."""
from pathlib import Path
import hashlib
import shlex
import subprocess

root = Path(__file__).resolve().parent.parent
binary = root / 'build/ethershell-soft-blank-arm64'
digest = hashlib.sha256(binary.read_bytes()).hexdigest()
ssh = ['ssh', '-i', str(root/'build/etherpocket_ed25519'), '-o',
       'UserKnownHostsFile='+str(root/'build/mobian-known-hosts'),
       '-o', 'BatchMode=yes', 'root@10.77.0.2']
subprocess.run(ssh+['cat > /tmp/ethershell-soft-blank-arm64'], input=binary.read_bytes(), check=True)
source = r'''
from pathlib import Path
import hashlib, os, shutil, subprocess, time
incoming = Path('/tmp/ethershell-soft-blank-arm64')
assert hashlib.sha256(incoming.read_bytes()).hexdigest() == DIGEST
pids = subprocess.check_output(['pgrep','-u','1000','-x','ethershell'], text=True).split()
assert len(pids)==1, pids
proc = Path('/proc')/pids[0]
oldexe = (proc/'exe').resolve()
assert oldexe.parent.parent.parent.name.startswith('2.0.1-7b446a1157ed'), 'Active build changed'
env = dict(item.split('=',1) for item in (proc/'environ').read_bytes().decode().split('\0') if '=' in item)
oldstage = oldexe.parent.parent.parent
stage = oldstage.with_name(oldstage.name.split('-soft-')[0]+'-soft-'+DIGEST[:8])
if not stage.exists(): shutil.copytree(oldstage, stage, symlinks=True)
replacement = stage/'usr/bin/ethershell.new'
shutil.copyfile(incoming, replacement)
replacement.chmod(0o755)
replacement.replace(stage/'usr/bin/ethershell')
launcher = Path('/home/mobian/.local/bin/ethershell2-start')
previous = launcher.read_bytes()
backup = launcher.with_name('ethershell2-start.before-soft-blank')
if not backup.exists(): backup.write_bytes(previous); backup.chmod(0o755); os.chown(backup,1000,1000)
def run(action, directory, environment):
    command = ['/usr/sbin/runuser','-u','mobian','--','/usr/bin/python3',str(directory/'usr/share/ethershell/current_session.py'),action]
    if action=='stop': subprocess.run(command,env=environment,check=True,timeout=20)
    else:
        with open('/tmp/ethershell-soft-blank-launch.log','a') as log:
            subprocess.Popen(command,env=environment,stdin=subprocess.DEVNULL,stdout=log,stderr=log,start_new_session=True)
run('stop',oldstage,env)
newenv = dict(env, ETHERSHELL_SOFT_BLANK='1', PATH=str(stage/'usr/bin')+':'+env.get('PATH','/usr/bin:/bin'))
newenv['ETHERSHELL_PROFILE_DEFAULT']=str(stage/'usr/share/ethershell/profiles.json')
launcher.write_text('#!/bin/sh\nset -eu\nexport ETHERSHELL_SOFT_BLANK=1\nexport PATH='+str(stage/'usr/bin')+':"$PATH"\nexport ETHERSHELL_PROFILE_DEFAULT='+newenv['ETHERSHELL_PROFILE_DEFAULT']+'\nexec /usr/bin/python3 '+str(stage/'usr/share/ethershell/current_session.py')+' "$@"\n')
launcher.chmod(0o755); os.chown(launcher,1000,1000)
run('start',stage,newenv)
time.sleep(4)
found = subprocess.run(['pgrep','-u','1000','-x','ethershell'],capture_output=True,text=True).stdout.split()
if len(found)!=1 or (Path('/proc')/found[0]/'exe').resolve()!=stage/'usr/bin/ethershell':
    launcher.write_bytes(previous)
    run('stop',stage,newenv)
    run('start',oldstage,env)
    raise RuntimeError('Software blank startup failed; previous launcher restored')
print('Installed:',stage)
print('PID:',found[0])
print('Rollback launcher:',backup)
'''.replace('DIGEST', repr(digest))
subprocess.run(ssh+['python3 -c '+shlex.quote(source)],check=True,timeout=45)
