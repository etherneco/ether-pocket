"""Drive production QML on the real session bus with the rear native camera."""
from pathlib import Path
import json,runpy,subprocess,shlex,io,tarfile
ROOT=Path(__file__).resolve().parent.parent
SSH=runpy.run_path(str(ROOT/'scripts/deploy-ethermobile.py'))['SSH']
SOURCE=r'''
import pathlib,subprocess,json,os,time
assert pathlib.Path('/etc/etherpocket/disk-identity').read_text().strip()=='GM1920-548cb338-mobian-sda21'
user=['runuser','-u','mobian','--','env','XDG_RUNTIME_DIR=/run/user/1000','DBUS_SESSION_BUS_ADDRESS=unix:path=/run/user/1000/bus']
state=json.loads(subprocess.check_output(user+['ethercamera','state'],text=True));assert not state['active'] and not state['busy']
folder=pathlib.Path('/var/tmp/ethercamera-physical-ui');folder.mkdir(exist_ok=True);os.chown(folder,1000,1000)
was_active=subprocess.run(user+['systemctl','--user','is-active','ethercamera-ui'],capture_output=True,text=True).stdout.strip()=='active'
if was_active:subprocess.run(user+['systemctl','--user','stop','ethercamera-ui'],check=True)
try:
 p=subprocess.run(user+['env','DISPLAY=:0','XAUTHORITY=/home/mobian/.Xauthority','QT_ENABLE_HIGHDPI_SCALING=0',str(folder/'ethercamera-ui-test'),'physical-capture',str(folder)],capture_output=True,text=True,timeout=45)
 (folder/'console.txt').write_text(p.stdout+p.stderr)
 assert p.returncode==0,(p.stdout+p.stderr)[-4500:]
 result=json.loads((folder/'result.json').read_text());assert not result['error'],result
finally:
 if was_active:subprocess.run(user+['systemd-run','--user','--collect','--unit=ethercamera-ui','env','DISPLAY=:0','XAUTHORITY=/home/mobian/.Xauthority','QT_ENABLE_HIGHDPI_SCALING=0','/usr/bin/ethercamera-app'],check=True,stdout=subprocess.DEVNULL)
state=json.loads(subprocess.check_output(user+['ethercamera','state'],text=True));assert not state['active'] and not state['busy']
print(json.dumps(result,indent=2))
'''
folder='/var/tmp/ethercamera-physical-ui'
subprocess.run(SSH+['install -d -o mobian -g mobian -m 700 '+folder],check=True)
binary=subprocess.check_output(['wsl','-d','EtherPocketBuild','--','cat','/opt/etherpocket/ethercamera-arm64/ethercamera-ui-test'])
code='import pathlib,sys;p=pathlib.Path("'+folder+'/ethercamera-ui-test");p.write_bytes(sys.stdin.buffer.read());p.chmod(0o755)'
subprocess.run(SSH+['python3 -c '+shlex.quote(code)],input=binary,check=True)
p=subprocess.run(SSH+['python3 -c '+shlex.quote(SOURCE)],capture_output=True,text=True,timeout=65)
if p.returncode:raise RuntimeError(p.stderr)
destination=ROOT/'evidence/ethercamera-physical-ui';destination.mkdir(exist_ok=True)
archive=subprocess.check_output(SSH+['tar -C '+folder+' -cf - result.json console.txt preview.png recording.png saved.png'])
with tarfile.open(fileobj=io.BytesIO(archive)) as tar:tar.extractall(destination,filter='data')
print(p.stdout)
