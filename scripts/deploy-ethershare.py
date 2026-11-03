"""Install the native package and idle system service; no sharing activation."""
from pathlib import Path
import hashlib, json, runpy, shlex, subprocess
ROOT=Path(__file__).resolve().parent.parent
SSH=runpy.run_path(str(ROOT/'scripts/deploy-ethermobile.py'))['SSH']
if __name__=='__main__':
    package=ROOT/'build/ethershare_0.1.0_arm64.deb'
    payload=package.read_bytes()
    source=r'''
import hashlib,json,pathlib,subprocess,sys,tempfile
assert pathlib.Path('/etc/etherpocket/disk-identity').read_text().strip()=='GM1920-548cb338-mobian-sda21'
payload=sys.stdin.buffer.read();assert hashlib.sha256(payload).hexdigest()==DIGEST
with tempfile.TemporaryDirectory(dir='/var/tmp') as folder:
 p=pathlib.Path(folder)/'ethershare.deb';p.write_bytes(payload)
 subprocess.run(['dpkg','--dry-run','--install',str(p)],check=True,stdout=sys.stderr)
 subprocess.run(['dpkg','--install',str(p)],check=True,stdout=sys.stderr)
rule=pathlib.Path('/usr/share/ethershare/integration/49-etherpocket-sharing.rules')
pathlib.Path('/etc/polkit-1/rules.d/49-etherpocket-sharing.rules').write_bytes(rule.read_bytes())
subprocess.run(['systemctl','daemon-reload'],check=True)
subprocess.run(['systemctl','enable','ethershare.service'],check=True,stdout=sys.stderr)
subprocess.run(['systemctl','restart','ethershare.service'],check=True)
print(json.dumps({'package_sha256':DIGEST,'service':'installed; idle unless explicit autostart was previously configured'}))
'''.replace('DIGEST',repr(hashlib.sha256(payload).hexdigest()))
    r=subprocess.run(SSH+['python3 -c '+shlex.quote(source)],input=payload,capture_output=True,timeout=60)
    if r.returncode:raise RuntimeError(r.stderr.decode()[-5000:])
    data=json.loads(r.stdout)
    (ROOT/'evidence/ethershare-install.json').write_text(json.dumps(data,indent=2)+'\n')
    print(json.dumps(data))
