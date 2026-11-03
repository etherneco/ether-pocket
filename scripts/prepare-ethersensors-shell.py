"""Prepare a root-owned versioned shell stage after exact-package UI acceptance."""
from pathlib import Path
import hashlib,json,runpy
ROOT=Path(__file__).resolve().parent.parent
remote=runpy.run_path(str(ROOT/'scripts/verify-etherupdate-device.py'))['remote']
if __name__=='__main__':
 package=ROOT/'build/ethershell_2.1.0_ethersensors_arm64.deb'
 digest=hashlib.sha256(package.read_bytes()).hexdigest()
 qa=json.loads((ROOT/'evidence/ethersensors-ui-package.json').read_text());assert qa['passed'] and qa['package_sha256']==digest
 source=r'''
import hashlib,json,pathlib,shutil,subprocess,sys,tempfile
payload=sys.stdin.buffer.read();assert hashlib.sha256(payload).hexdigest()==DIGEST
assert pathlib.Path('/etc/etherpocket/disk-identity').read_text().strip()=='GM1920-548cb338-mobian-sda21'
pids=subprocess.check_output(['pgrep','-u','1000','-x','ethershell'],text=True).split();assert len(pids)==1
old=(pathlib.Path('/proc')/pids[0]/'exe').resolve().parent.parent.parent
assert old.parent==pathlib.Path('/opt/ethershell2')
stage=old.parent/('2.1.0-sensors-'+DIGEST[:12]);assert not stage.exists()
with tempfile.TemporaryDirectory(prefix='ethersensors-shell-',dir='/var/tmp') as folder:
 path=pathlib.Path(folder)/'shell.deb';path.write_bytes(payload)
 shutil.copytree(old,stage,symlinks=True)
 subprocess.run(['dpkg-deb','-x',str(path),str(stage)],check=True,stdout=sys.stderr)
assert (stage/'usr/bin/ethershell').stat().st_uid==0 and not (stage/'usr/bin/ethershell').stat().st_mode&0o022
print(json.dumps(dict(stage=str(stage),previous=str(old),package_sha256=DIGEST,binary_sha256=hashlib.sha256((stage/'usr/bin/ethershell').read_bytes()).hexdigest(),qa_passed=True)))
'''.replace('DIGEST',repr(digest))
 result=json.loads(remote(source,package.read_bytes()))
 (ROOT/'evidence/ethersensors-stage.json').write_text(json.dumps(result,indent=2)+'\n',encoding='utf-8')
 print(json.dumps(result,indent=2))
