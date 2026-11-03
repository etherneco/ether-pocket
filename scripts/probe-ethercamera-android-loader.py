"""Probe Android's loader in a disposable, device-denied root. Never run a camera HAL."""
from pathlib import Path
import json,runpy,shlex,subprocess
ROOT=Path(__file__).resolve().parent.parent
SSH=runpy.run_path(str(ROOT/'scripts/deploy-ethermobile.py'))['SSH']
SOURCE=r'''
import hashlib,json,pathlib,re,shutil,subprocess,tempfile,uuid,zipfile
assert pathlib.Path('/etc/etherpocket/disk-identity').read_text().strip()=='GM1920-548cb338-mobian-sda21'
system='/dev/disk/by-partlabel/system_b'
def run(args,timeout=20):
 p=subprocess.run(args,capture_output=True,text=True,timeout=timeout)
 return dict(exit=p.returncode,stdout=p.stdout[:30000],stderr=p.stderr[:5000])
result=dict(scope='Read-only debugfs system_b; temporary local APEX extraction; execute only linker64 --help in a device-denied sandbox. No HAL or init execution.',system=system)
with tempfile.TemporaryDirectory(prefix='ethercamera-loader-probe-',dir='/var/tmp') as folder:
 base=pathlib.Path(folder);base.chmod(0o755)
 apex=base/'runtime.apex'
 r=run(['debugfs','-R','dump /system/apex/com.android.runtime.release.apex '+str(apex),system],60)
 assert apex.is_file(),r
 result['apexSha256']=hashlib.sha256(apex.read_bytes()).hexdigest()
 payload=base/'runtime.img'
 with zipfile.ZipFile(apex) as archive:
  info=archive.getinfo('apex_payload.img');assert info.file_size<1024*1024*1024
  with archive.open(info) as source,payload.open('wb') as target:shutil.copyfileobj(source,target)
 root=base/'root';(root/'apex/com.android.runtime/bin').mkdir(parents=True,mode=0o755)
 linker=root/'apex/com.android.runtime/bin/linker64'
 r=run(['debugfs','-R','dump /bin/linker64 '+str(linker),str(payload)])
 assert linker.is_file(),r
 assert linker.read_bytes().startswith(b'\x7fELF')
 linker.chmod(0o755);result['linkerSha256']=hashlib.sha256(linker.read_bytes()).hexdigest()
 unit='ethercamera-loader-probe-'+uuid.uuid4().hex[:12]
 command=['systemd-run','--quiet','--wait','--pipe','--collect','--unit='+unit,
  '-p','RootDirectory='+str(root),'-p','User=65534','-p','Group=65534',
  '-p','PrivateDevices=yes','-p','PrivateNetwork=yes','-p','DevicePolicy=closed',
  '-p','NoNewPrivileges=yes','-p','CapabilityBoundingSet=',
  '-p','ProtectSystem=strict','-p','ProtectHome=yes','-p','ProtectKernelTunables=yes',
  '-p','ProtectControlGroups=yes','-p','RestrictNamespaces=yes',
  '-p','MemoryMax=128M','-p','CPUQuota=20%','-p','RuntimeMaxSec=5',
  '/apex/com.android.runtime/bin/linker64','--help']
 result['probe']=run(command,15)
 result['sandbox']=dict(root='disposable local root',user=65534,privateDevices=True,devicePolicy='closed',privateNetwork=True,capabilities='none',runtimeSeconds=5)
 result['temporaryCopiesRemovedOnExit']=True
print(json.dumps(result,indent=2))
'''
if __name__=='__main__':
    p=subprocess.run(SSH+['python3 -c '+shlex.quote(SOURCE)],capture_output=True,timeout=150)
    if p.returncode:raise RuntimeError(p.stderr.decode(errors='replace'))
    data=json.loads(p.stdout)
    (ROOT/'evidence/ethercamera-android-loader-probe.json').write_text(json.dumps(data,indent=2)+'\n',encoding='utf-8')
    print(json.dumps(data,indent=2))
