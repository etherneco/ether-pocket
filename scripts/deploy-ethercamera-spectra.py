"""Install the native worker; derive its pinned plan privately on the handset."""
from pathlib import Path
import hashlib,json,runpy,shlex,subprocess
ROOT=Path(__file__).resolve().parent.parent
SSH=runpy.run_path(str(ROOT/'scripts/deploy-ethermobile.py'))['SSH']
SOURCE=r'''
import pathlib,subprocess,sys,hashlib,tempfile,json,os
assert pathlib.Path('/etc/etherpocket/disk-identity').read_text().strip()=='GM1920-548cb338-mobian-sda21'
payload=sys.stdin.buffer.read();assert hashlib.sha256(payload).hexdigest()==DIGEST
for p in pathlib.Path('/proc').iterdir():
 if not p.name.isdigit():continue
 try:
  for fd in (p/'fd').iterdir():
   try:target=str(fd.resolve(strict=True))
   except FileNotFoundError:continue
   assert not target.startswith(('/dev/video','/dev/v4l-subdev','/dev/media')),'Media owner active'
 except (FileNotFoundError,ProcessLookupError):continue
with tempfile.TemporaryDirectory(dir='/var/tmp') as folder:
 p=pathlib.Path(folder)/'spectra.deb';p.write_bytes(payload)
 subprocess.run(['dpkg','--dry-run','-i',str(p)],check=True,stdout=sys.stderr)
 subprocess.run(['dpkg','-i',str(p)],check=True,stdout=sys.stderr)
sys.path.insert(0,'/usr/share/ethercamera/spectra')
from capture_profile import capture_profile
profiles=[]
for name in ['semco_imx586','ofilm_imx586','semco_2nd_lens_imx586']:
 raw=subprocess.check_output(['debugfs','-R','cat /lib64/camera/com.qti.sensormodule.'+name+'.bin','/dev/disk/by-partlabel/vendor_b'],stderr=subprocess.DEVNULL)
 profiles.append(capture_profile(raw))
assert len({p['packetSha256'] for p in profiles})==1
target=pathlib.Path('/usr/share/ethercamera/spectra/rear-plan.json')
assert not target.is_symlink()
fd=os.open(target,os.O_WRONLY|os.O_CREAT|os.O_TRUNC|os.O_NOFOLLOW,0o640)
with os.fdopen(fd,'w') as f:json.dump(profiles[0],f)
os.chmod(target,0o640);os.chown(target,0,44)
print(json.dumps(dict(packageSha256=DIGEST,version='0.2.0',planTableSha256=profiles[0]['packetSha256'],vendorPartitionsReadOnly=True,automaticCapture=False)))
'''
payload=(ROOT/'build/ethercamera-spectra_0.2.0_arm64.deb').read_bytes()
p=subprocess.run(SSH+['python3 -c '+shlex.quote(SOURCE.replace('DIGEST',repr(hashlib.sha256(payload).hexdigest())))],input=payload,capture_output=True,timeout=60)
if p.returncode:raise RuntimeError(p.stderr.decode())
data=json.loads(p.stdout)
(ROOT/'evidence/ethercamera-spectra-capture-install.json').write_text(json.dumps(data,indent=2)+'\n')
print(json.dumps(data,indent=2))
