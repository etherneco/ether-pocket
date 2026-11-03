"""Install the reviewed app only. No radio, kernel, backend service or shell reset."""
from pathlib import Path
import hashlib
import json
import shlex
import subprocess

ROOT=Path(__file__).resolve().parent.parent
SSH=['ssh','-i',str(ROOT/'build/etherpocket_ed25519'),'-o',
     'UserKnownHostsFile='+str(ROOT/'build/mobian-known-hosts'),'-o',
     'BatchMode=yes','-o','ConnectTimeout=8','root@10.77.0.2']

if __name__=='__main__':
    package=ROOT/'build/ethermobile_0.1.1_arm64.deb'
    payload=package.read_bytes()
    source='''import hashlib,json,pathlib,platform,subprocess,sys,tempfile
assert platform.machine()=='aarch64'
assert pathlib.Path('/etc/etherpocket/disk-identity').read_text().strip()=='GM1920-548cb338-mobian-sda21'
payload=sys.stdin.buffer.read()
assert hashlib.sha256(payload).hexdigest()==DIGEST
def probe():
 return {'services':subprocess.run(['systemctl','is-active','NetworkManager','ssh','bluetooth','etherpocket-modem'],capture_output=True,text=True).stdout,
         'devices':subprocess.run(['nmcli','-t','-f','DEVICE,TYPE,STATE','device'],capture_output=True,text=True).stdout}
before=probe()
with tempfile.TemporaryDirectory(prefix='ethermobile-install-',dir='/run') as folder:
 path=pathlib.Path(folder)/'ethermobile_0.1.1_arm64.deb'
 path.write_bytes(payload)
 subprocess.run(['dpkg','--dry-run','--install',str(path)],check=True,stdout=sys.stderr)
 subprocess.run(['dpkg','--install',str(path)],check=True,stdout=sys.stderr)
print(json.dumps({'sha256':DIGEST,'before':before,'after':probe()},indent=2))
'''.replace('DIGEST',repr(hashlib.sha256(payload).hexdigest()))
    r=subprocess.run(SSH+['python3 -c '+shlex.quote(source)],input=payload,capture_output=True,check=True,timeout=90)
    data=json.loads(r.stdout)
    target=ROOT/'evidence/ethermobile-install-2026-10-18.json'
    target.write_text(json.dumps(data,indent=2)+'\n',encoding='utf-8')
    print(target)
