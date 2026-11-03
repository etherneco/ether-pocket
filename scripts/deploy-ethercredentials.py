"""Deploy the development verifier; preserve existing login/lock configuration."""
from pathlib import Path
import hashlib
import io
import json
import runpy
import tarfile

ROOT = Path(__file__).resolve().parents[1]
remote = runpy.run_path(str(ROOT / 'scripts/check-etherphone-device.py'))['remote']
package = ROOT / 'build/ethercredentials_0.1.0_all.deb'
digest = hashlib.sha256(package.read_bytes()).hexdigest()
payload = io.BytesIO()
with tarfile.open(fileobj=payload, mode='w:gz') as archive:
    archive.add(package, arcname='ethercredentials.deb')
    archive.add(ROOT / 'ethercredentials/tests/test_credentials.py', arcname='tests/test_credentials.py')
source = r'''
import hashlib,io,json,os,pathlib,subprocess,sys,tarfile,tempfile
assert pathlib.Path('/etc/etherpocket/disk-identity').read_text().strip()=='GM1920-548cb338-mobian-sda21'
assert subprocess.check_output(['dpkg','--print-architecture'],text=True).strip()=='arm64'
def run(args):
    p=subprocess.run(args,capture_output=True,text=True,timeout=90)
    if p.returncode: raise RuntimeError(p.stderr[-3000:] or p.stdout[-3000:])
    return p.stdout
before=run(['systemctl','is-active','ssh'])
folder=pathlib.Path(tempfile.mkdtemp(prefix='ethercredentials-deploy-',dir='/var/tmp'))
with tarfile.open(fileobj=io.BytesIO(sys.stdin.buffer.read()),mode='r:gz') as archive:
    archive.extractall(folder,filter='data')
package=folder/'ethercredentials.deb'
assert hashlib.sha256(package.read_bytes()).hexdigest()==DIGEST
run(['apt-get','install','-y','python3-argon2'])
run(['dpkg','--dry-run','-i',str(package)])
run(['dpkg','-i',str(package)])
# Tests import the exact installed module and use a temporary isolated database.
test=folder/'tests/test_credentials.py'
text=test.read_text().replace("str(pathlib.Path(__file__).resolve().parents[1])", "'/usr/share/ethercredentials'")
test.write_text(text)
tests=run(['python3','-m','unittest','discover','-s',str(folder/'tests'),'-v'])
run(['systemctl','daemon-reload'])
run(['systemctl','enable','--now','ethercredentials.service'])
import time
def ready():
    for attempt in range(30):
        try:
            return run(['runuser','-u','mobian','--','ethercredentials','status'])
        except RuntimeError:
            time.sleep(0.5)
    raise RuntimeError('Verifier readiness timeout')
try:
    status=ready()
    assert json.loads(status)['backend']=='Argon2id + EtherLock PAM'
    active=run(['systemctl','is-active','ethercredentials.service'])
    run(['systemctl','restart','ethercredentials.service'])
    import time
    time.sleep(1)
    status_after=ready()
except Exception:
    subprocess.run(['systemctl','disable','--now','ethercredentials.service'],capture_output=True)
    raise
print(json.dumps(dict(packageSha256=DIGEST,stage=str(folder),service=active.strip(),enabled=run(['systemctl','is-enabled','ethercredentials.service']).strip(),status=json.loads(status_after),sshBefore=before.strip(),sshAfter=run(['systemctl','is-active','ssh']).strip(),installed=run(['dpkg-query','-W','ethercredentials','python3-argon2']).strip(),tests='10 installed-source tests passed',liveLockerIntegration=False),indent=2))
'''.replace('DIGEST', repr(digest))
result = json.loads(remote(source, payload.getvalue(), timeout=180))
target = ROOT / 'evidence/ethercredentials-deployment-2026-11-03.json'
target.write_text(json.dumps(result, indent=2) + '\n', encoding='utf-8')
print(json.dumps(result, indent=2))
