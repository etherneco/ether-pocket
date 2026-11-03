"""Stage an ARM64 package beside 0.4, then integrate with the current X11 session."""
import argparse
import hashlib
from pathlib import Path
import shlex
import subprocess

ROOT=Path(__file__).resolve().parent.parent
SSH=['ssh','-i',str(ROOT/'build/etherpocket_ed25519'),'-o','UserKnownHostsFile='+str(ROOT/'build/mobian-known-hosts'),'-o','BatchMode=yes','-o','ConnectTimeout=8','root@10.77.0.2']
PACKAGE=ROOT/'build/ethershell_2.0.1_arm64.deb'


def remote(source,payload=None):
    return subprocess.run(SSH+['python3 -c '+shlex.quote(source)],input=payload,check=True,timeout=45)


if __name__=='__main__':
    parser=argparse.ArgumentParser()
    parser.add_argument('action',choices=['stage','start','stop','status'])
    args=parser.parse_args()
    digest=hashlib.sha256(PACKAGE.read_bytes()).hexdigest()
    stage='/opt/ethershell2/2.0.1-'+digest[:12]
    if args.action=='stage':
        remote('''import hashlib,json,pathlib,shutil,subprocess,sys
data=sys.stdin.buffer.read()
assert hashlib.sha256(data).hexdigest()==DIGEST
stage=pathlib.Path(STAGE)
package=pathlib.Path('/tmp/ethershell2-'+DIGEST[:12]+'.deb')
package.write_bytes(data)
backup=pathlib.Path('/var/backups/ethershell/before-current-2.0')
backup.mkdir(mode=0o700,parents=True,exist_ok=True)
for name in ['preferences.json','profiles.json','safe-mode','application-settings-backup.json']:
 source=pathlib.Path('/home/mobian/.config/ethershell')/name
 target=backup/name
 if source.is_file() and not target.exists():shutil.copy2(source,target)
if not (backup/'ethershell').exists():shutil.copy2('/usr/bin/ethershell',backup/'ethershell')
source=pathlib.Path('/etc/firefox-esr/etherpocket-touch.js')
if source.is_file() and not (backup/source.name).exists():shutil.copy2(source,backup/source.name)
if not (stage/'staging-complete.json').exists():
 stage.mkdir(parents=True,exist_ok=True)
 subprocess.run(['dpkg-deb','-x',str(package),str(stage)],check=True)
 (stage/'staging-complete.json').write_text(json.dumps({'sha256':DIGEST}))
result=subprocess.run(['ldd',str(stage/'usr/bin/ethershell')],capture_output=True,text=True,check=True)
if 'not found' in result.stdout:raise RuntimeError(result.stdout)
home=pathlib.Path('/home/mobian')
for directory in [home/'.local/bin',home/'.local/share/applications']:
 if not directory.exists():directory.mkdir(parents=True);shutil.chown(directory,user='mobian',group='mobian')
launcher=home/'.local/bin/ethershell2-start'
launcher.write_text('#!/bin/sh\\nset -eu\\nexport PATH='+str(stage/'usr/bin')+':"$PATH"\\nexport ETHERSHELL_PROFILE_DEFAULT='+str(stage/'usr/share/ethershell/profiles.json')+'\\nexec /usr/bin/python3 '+str(stage/'usr/share/ethershell/current_session.py')+' "$@"\\n')
launcher.chmod(0o755);shutil.chown(launcher,user='mobian',group='mobian')
desktop=home/'.local/share/applications/etherneco-window-experience.desktop'
desktop.write_text('[Desktop Entry]\\nType=Application\\nName=EtherShell 2\\nComment=Floating touch windows in the current X11 session\\nExec='+str(launcher)+'\\nIcon=preferences-desktop\\nTerminal=false\\nCategories=System;\\n')
desktop.chmod(0o644);shutil.chown(desktop,user='mobian',group='mobian')
print('Staged '+str(stage)+'; current-session launcher installed; existing binary and session preserved.')
'''.replace('DIGEST',repr(digest)).replace('STAGE',repr(stage)),PACKAGE.read_bytes())
    else:
        remote('''import os,pathlib,subprocess
stage=pathlib.Path(STAGE)
action=ACTION
assert (stage/'staging-complete.json').exists()
environments=[]
for entry in pathlib.Path('/proc').iterdir():
 if not entry.name.isdigit():continue
 try:
  if entry.stat().st_uid!=1000 or (entry/'comm').read_text().strip()!='ethershell':continue
  env=dict(item.split('=',1) for item in (entry/'environ').read_bytes().decode().split('\\0') if '=' in item)
  if env.get('DISPLAY','').removesuffix('.0')==':0':environments.append(env)
 except (FileNotFoundError,PermissionError):pass
env=environments[0] if environments else {'HOME':'/home/mobian','USER':'mobian','LOGNAME':'mobian','DISPLAY':':0','XAUTHORITY':'/home/mobian/.Xauthority','XDG_RUNTIME_DIR':'/run/user/1000','DBUS_SESSION_BUS_ADDRESS':'unix:path=/run/user/1000/bus','PATH':'/usr/local/bin:/usr/bin:/bin'}
env['PATH']=str(stage/'usr/bin')+':'+env.get('PATH','/usr/bin:/bin')
env['ETHERSHELL_PROFILE_DEFAULT']=str(stage/'usr/share/ethershell/profiles.json')
command=['/usr/sbin/runuser','-u','mobian','--','/usr/bin/python3',str(stage/'usr/share/ethershell/current_session.py'),action]
if action=='start':
 log=open('/tmp/ethershell2-current-launch.log','a')
 p=subprocess.Popen(command,env=env,stdin=subprocess.DEVNULL,stdout=log,stderr=subprocess.STDOUT,start_new_session=True)
 print('Current-session launcher PID '+str(p.pid))
else:subprocess.run(command,env=env,check=True,timeout=15)
'''.replace('STAGE',repr(stage)).replace('ACTION',repr(args.action)))
