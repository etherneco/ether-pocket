"""Stage 1 installation and isolated ARM64 acceptance; no live mandatory locking."""
from pathlib import Path
import hashlib
import io
import json
import runpy
import tarfile
import sys
ROOT = Path(__file__).resolve().parents[1]
remote = runpy.run_path(str(ROOT/'scripts/check-etherphone-device.py'))['remote']
if __name__ == '__main__':
    package = ROOT/'build/etherlock_0.1.0_arm64.deb'
    digest = hashlib.sha256(package.read_bytes()).hexdigest()
    payload = io.BytesIO()
    with tarfile.open(fileobj=payload, mode='w:gz') as tar:
        tar.add(package, arcname='etherlock.deb')
        tar.add(ROOT/'etherlock/tests/device_acceptance.py', arcname='acceptance.py')
    source = r'''
import hashlib,io,json,pathlib,subprocess,sys,tarfile,tempfile
assert pathlib.Path('/etc/etherpocket/disk-identity').read_text().strip()=='GM1920-548cb338-mobian-sda21'
folder=pathlib.Path(tempfile.mkdtemp(prefix='etherlock-stage-',dir='/var/tmp'))
with tarfile.open(fileobj=io.BytesIO(sys.stdin.buffer.read()),mode='r:gz') as tar:tar.extractall(folder,filter='data')
package=folder/'etherlock.deb';assert hashlib.sha256(package.read_bytes()).hexdigest()==DIGEST
subprocess.run(['dpkg','--dry-run','-i',str(package)],check=True,stdout=sys.stderr)
subprocess.run(['dpkg','-i',str(package)],check=True,stdout=sys.stderr)
# No start/enable/lock command against the live session.
out=folder/'results'
with (folder/'acceptance.log').open('wb') as log:
 p=subprocess.Popen(['python3',str(folder/'acceptance.py'),str(out)]+TEST_FLAGS,stdout=log,stderr=log,start_new_session=True)
print(json.dumps({'stage':str(folder),'pid':p.pid,'sha256':DIGEST,'automaticLocking':False,'testFlags':TEST_FLAGS}))
'''.replace('DIGEST', repr(digest)).replace('TEST_FLAGS', repr(['--ui-only'] if '--ui-only' in sys.argv else []))
    data = json.loads(remote(source, payload.getvalue(), timeout=50))
    (ROOT/'evidence/etherlock-stage.json').write_text(json.dumps(data, indent=2)+'\n', encoding='utf-8')
    print(json.dumps(data, indent=2))
