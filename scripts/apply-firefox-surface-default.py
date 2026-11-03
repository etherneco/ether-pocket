"""Apply the supported Firefox titlebar default and request a normal restart."""
import hashlib
from pathlib import Path
import shlex
import subprocess

root=Path(__file__).resolve().parent.parent
digest=hashlib.sha256((root/'build/ethershell_2.0.0_arm64.deb').read_bytes()).hexdigest()
stage='/opt/ethershell2/2.0.0-'+digest[:12]
ssh=['ssh','-i',str(root/'build/etherpocket_ed25519'),'-o','UserKnownHostsFile='+str(root/'build/mobian-known-hosts'),'-o','BatchMode=yes','-o','ConnectTimeout=8','root@10.77.0.2']
source='''import os,pathlib,shutil,socket,json,subprocess,time
stage=pathlib.Path(STAGE)
target=pathlib.Path('/etc/firefox-esr/etherpocket-touch.js')
backup=pathlib.Path('/var/backups/ethershell/before-current-2.0')/target.name
assert backup.exists()
shutil.copyfile(stage/'etc/firefox-esr/etherpocket-touch.js',target)
os.chmod(target,0o644)
env=os.environ.copy();env.update(DISPLAY=':0.0',XAUTHORITY='/home/mobian/.Xauthority')
clients=subprocess.check_output(['runuser','-u','mobian','--','wmctrl','-lx'],env=env,text=True)
windows=[line.split()[0] for line in clients.splitlines() if 'firefox-esr' in line.lower()]
for window in windows:subprocess.run(['runuser','-u','mobian','--','wmctrl','-ic',window],env=env,check=True)
for _ in range(40):
 if subprocess.run(['pgrep','-x','firefox-esr'],stdout=subprocess.DEVNULL).returncode:break
 time.sleep(.2)
else:raise SystemExit('Firefox retained its window or a confirmation prompt; no forced close.')
with socket.socket(socket.AF_UNIX) as client:
 client.settimeout(5);client.connect('/run/user/1000/ethershell-control-experience-0-0');client.sendall(b'{"command":"launch","id":"firefox-esr.desktop"}\\n');assert client.recv(32).startswith(b'ok')
print('Firefox received the supported external titlebar default and restarted normally.')
'''.replace('STAGE',repr(stage))
subprocess.run(ssh+['python3 -c '+shlex.quote(source)],check=True,timeout=30)
