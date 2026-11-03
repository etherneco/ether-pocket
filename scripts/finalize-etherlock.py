"""Collect completed acceptance and regression evidence; never enables locking."""
from pathlib import Path
import hashlib
import io
import json
import runpy
import tarfile
ROOT=Path(__file__).resolve().parents[1]
remote=runpy.run_path(str(ROOT/'scripts/check-etherphone-device.py'))['remote']
if __name__=='__main__':
    stage=json.loads((ROOT/'evidence/etherlock-stage.json').read_text())
    assert hashlib.sha256((ROOT/'build/etherlock_0.1.0_arm64.deb').read_bytes()).hexdigest()==stage['sha256']
    source=r'''
import hashlib,json,pathlib,subprocess,sys,tarfile
folder=pathlib.Path(STAGE)/'results'
tests=json.loads((folder/'acceptance.json').read_text());assert all(tests.values()),tests
assert not pathlib.Path('/etc/etherlock/validation.json').exists(),'Unexpected activation evidence'
user=['runuser','-u','mobian','--','env','XDG_RUNTIME_DIR=/run/user/1000','DBUS_SESSION_BUS_ADDRESS=unix:path=/run/user/1000/bus']
assert subprocess.run(user+['systemctl','--user','is-active','etherlock'],capture_output=True).returncode!=0
hashes={p:hashlib.sha256(pathlib.Path(p).read_bytes()).hexdigest() for p in ['/usr/lib/etherlock/auth_etherlock','/usr/lib/etherlock/etherlock-pam','/etc/pam.d/etherlock','/usr/share/etherlock/core.py','/usr/share/etherlock/service.py']}
(folder/'installed-hashes.json').write_text(json.dumps(hashes,indent=2))
with tarfile.open(fileobj=sys.stdout.buffer,mode='w|gz') as tar:
 for p in folder.iterdir():tar.add(p,arcname=p.name)
'''.replace('STAGE',repr(stage['stage']))
    payload=remote(source,timeout=30)
    output=ROOT/'evidence/etherlock-device';output.mkdir(exist_ok=True)
    with tarfile.open(fileobj=io.BytesIO(payload),mode='r:gz') as tar:tar.extractall(output,filter='data')
    tests=json.loads((output/'acceptance.json').read_text())
    installed=json.loads((output/'installed-hashes.json').read_text())
    previous=json.loads((ROOT/'evidence/etherlock-pam-x11-acceptance.json').read_text())
    assert installed['/usr/lib/etherlock/etherlock-pam']==previous['pamHelperHash'],'PAM helper changed; repeat full PAM acceptance'
    assert all(previous['tests'].values())
    shell=json.loads((ROOT/'evidence/etherlock-shell-stage.json').read_text());assert shell['qa_passed']
    for entry in json.loads((ROOT/'evidence/etherlock-protocol-tests.json').read_text())['tests'].values():assert entry['exit']==0
    manifest=dict(packageSha256=stage['sha256'],automaticLocking=False,shellStage=shell['stage'],
        sourceHashes={str(p.relative_to(ROOT)):hashlib.sha256(p.read_bytes()).hexdigest() for p in (ROOT/'etherlock').rglob('*') if p.is_file() and '__pycache__' not in p.parts},
        pamAssertions=previous['tests'],finalUIAssertions=tests,installedHashes=installed)
    (ROOT/'evidence/etherlock-delivery.json').write_text(json.dumps(manifest,indent=2)+'\n',encoding='utf-8')
    print(json.dumps({'packageSha256':stage['sha256'],'pamAssertions':len(previous['tests']),'finalUIAssertions':tests,'automaticLocking':False},indent=2))
