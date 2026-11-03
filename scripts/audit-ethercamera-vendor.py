"""Read-only fixed vendor image metadata/ELF dependencies. No mounts or code execution."""
from pathlib import Path
import json,runpy,shlex,subprocess
ROOT=Path(__file__).resolve().parent.parent
SSH=runpy.run_path(str(ROOT/'scripts/deploy-ethermobile.py'))['SSH']
SOURCE=r'''
import hashlib,json,os,pathlib,re,subprocess
assert pathlib.Path('/etc/etherpocket/disk-identity').read_text().strip()=='GM1920-548cb338-mobian-sda21'
device='/dev/disk/by-partlabel/vendor_b'
assert pathlib.Path(device).is_symlink()
def query(command):
 p=subprocess.run(['debugfs','-R',command,device],capture_output=True,timeout=15)
 return p.stdout,p.stderr.decode(errors='replace')[:500]
result=dict(source=device,method='debugfs without -w; no mount/journal replay; no vendor code execution',directories={},files={},properties={},init={},
 runtimePaths={p:os.path.exists(p) for p in ['/system/bin/linker64','/vendor/bin/hw/android.hardware.camera.provider@2.4-service_64','/dev/binder','/dev/hwbinder','/dev/vndbinder']})
for directory in ['/lib64/hw','/lib64/camera','/lib/camera','/bin/hw','/etc/camera','/firmware']:
 raw,error=query('ls -l '+directory)
 lines=raw.decode(errors='replace').splitlines()
 result['directories'][directory]=dict(entries=[s for s in lines if re.search('camera|sensor|actuator|eeprom|ois|chromatix|imx|ov[0-9]|s5k|CAMERA|ICP',s,re.I)][:300],error=error)
for path in ['/lib64/hw/camera.qcom.so','/bin/hw/android.hardware.camera.provider@2.4-service','/bin/hw/android.hardware.camera.provider@2.4-service_64','/firmware/CAMERA_ICP.elf','/firmware/camera/CAMERA_ICP.elf']:
 raw,error=query('stat '+path);info=raw.decode(errors='replace')
 entry=dict(stat=info,error=error)
 size=re.search(r'Size:\s+(\d+)',info)
 if size and int(size[1])<=32*1024*1024 and path.endswith(('.so','-service','-service_64')):
  binary,_=query('cat '+path)
  entry.update(bytes=len(binary),sha256=hashlib.sha256(binary).hexdigest())
  if binary.startswith(b'\x7fELF'):
   fd=os.memfd_create('ethercamera-vendor-inspection',os.MFD_CLOEXEC)
   try:
    with os.fdopen(os.dup(fd),'wb') as stream:stream.write(binary)
    args=['readelf','-l','-d','/proc/self/fd/'+str(fd)]
    p=subprocess.run(args,pass_fds=[fd],capture_output=True,text=True,timeout=10)
    entry['elfDependencies']=[line.strip() for line in p.stdout.splitlines() if 'NEEDED' in line or 'interpreter' in line or 'RUNPATH' in line or 'RPATH' in line]
   finally:os.close(fd)
 result['files'][path]=entry
for path in ['/build.prop','/etc/build.prop']:
 raw,_=query('cat '+path)
 result['properties'][path]=[s for s in raw.decode(errors='replace').splitlines() if re.match(r'ro\.(vendor\.)?(product\.(model|device|name)|build\.(version\.(release|sdk)|fingerprint))=',s)]
for path in ['/etc/init/android.hardware.camera.provider@2.4-service.rc','/etc/init/android.hardware.camera.provider@2.4-service_64.rc']:
 raw,error=query('cat '+path)
 result['init'][path]=dict(text=raw.decode(errors='replace')[:10000],error=error)
print(json.dumps(result,indent=2))
'''
if __name__=='__main__':
    p=subprocess.run(SSH+['python3 -c '+shlex.quote(SOURCE)],capture_output=True,timeout=180)
    if p.returncode:raise RuntimeError(p.stderr.decode(errors='replace'))
    data=json.loads(p.stdout)
    (ROOT/'evidence/ethercamera-vendor-audit.json').write_text(json.dumps(data,indent=2)+'\n',encoding='utf-8')
    print(json.dumps(data,indent=2))
