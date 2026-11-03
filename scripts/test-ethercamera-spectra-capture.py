"""Bounded physical rear RAW acquisition; vendor tables stay on the phone."""
from pathlib import Path
import hashlib,json,runpy,shlex,subprocess,sys
ROOT=Path(__file__).resolve().parent.parent
SSH=runpy.run_path(str(ROOT/'scripts/deploy-ethermobile.py'))['SSH']
SOURCE=r'''
import pathlib,subprocess,json,hashlib,time,os
assert pathlib.Path('/etc/etherpocket/disk-identity').read_text().strip()=='GM1920-548cb338-mobian-sda21'
folder=pathlib.Path('/var/tmp/ethercamera-spectra-native')
assert hashlib.sha256((folder/'ethercamera-spectra-capture').read_bytes()).hexdigest()==DIGEST
user=['runuser','-u','mobian','--','env','XDG_RUNTIME_DIR=/run/user/1000','DBUS_SESSION_BUS_ADDRESS=unix:path=/run/user/1000/bus']
state=json.loads(subprocess.check_output(user+['ethercamera','state'],text=True));assert not state['active'] and not state['busy']
def holders():
 found=[]
 for p in pathlib.Path('/proc').iterdir():
  if not p.name.isdigit():continue
  try:
   for fd in (p/'fd').iterdir():
    try:target=str(fd.resolve(strict=True))
    except FileNotFoundError:continue
    if target.startswith(('/dev/video','/dev/v4l-subdev','/dev/media')):found.append((p.name,target))
  except (FileNotFoundError,ProcessLookupError):continue
 return found
assert not holders(),'Another media owner is active'
profiles=[]
for name in ['semco_imx586','ofilm_imx586','semco_2nd_lens_imx586']:
 raw=subprocess.check_output(['debugfs','-R','cat /lib64/camera/com.qti.sensormodule.'+name+'.bin','/dev/disk/by-partlabel/vendor_b'],stderr=subprocess.DEVNULL)
 profiles.append(capture_profile(raw))
assert len({p['packetSha256'] for p in profiles})==1
plan=folder/'capture-profile.json';plan.write_text(json.dumps(profiles[0]));plan.chmod(0o640);os.chown(plan,0,44)
output=folder/('rear-'+str(time.time_ns())+'.raw')
command=['systemd-run','--wait','--pipe','--collect','--unit=ethercamera-spectra-raw-test',
 '--property=Type=exec','--property=RuntimeMaxSec=20','--property=TimeoutStopSec=3',
 '--property=NoNewPrivileges=yes','--property=ProtectSystem=strict','--property=ProtectHome=yes',
 '--property=PrivateNetwork=yes','--property=ProtectKernelTunables=yes',
 '--property=CapabilityBoundingSet=','--property=DevicePolicy=closed','--property=MemoryMax=256M',
 '--property=ReadWritePaths='+str(folder)]
for p in pathlib.Path('/sys/class/video4linux').iterdir():
 if (p/'name').read_text().strip() in ['cam-req-mgr','cam-isp','cam_sync','cam-sensor-driver','cam-csiphy-driver']:
  command.append('--property=DeviceAllow=/dev/'+p.name+' rw')
command += [str(folder/'ethercamera-spectra-capture'),str(plan),str(output)]
if STREAM:
 command += []
 command[command.index(str(output))]='--rgb-stream'
 command.insert(5,'--property=User=mobian')
 worker=subprocess.Popen(command,stdout=subprocess.PIPE,stderr=subprocess.PIPE)
 frames=0;last=None
 try:
  for i in range(20):
   data=bytearray()
   while len(data)<640*480*3:
    chunk=worker.stdout.read(640*480*3-len(data))
    if not chunk:raise RuntimeError('Native stream ended: '+worker.stderr.read().decode())
    data.extend(chunk)
   frames+=1;last=bytes(data)
 finally:
  subprocess.run(['systemctl','kill','--signal=SIGTERM','ethercamera-spectra-raw-test.service'],capture_output=True)
  out,err=worker.communicate(timeout=10)
 from PIL import Image
 Image.frombytes('RGB',(640,480),last).save(str(output)+'.jpg')
 import types
 p=types.SimpleNamespace(returncode=worker.returncode,stdout=json.dumps(dict(frames=frames,rgbBytes=len(last))),stderr=err.decode())
else:p=subprocess.run(command,capture_output=True,text=True,timeout=30)
plan.unlink()
assert not holders(),'Leaked camera descriptors'
result=dict(exit=p.returncode,stdout=p.stdout,stderr=p.stderr,binarySha256=DIGEST,rawPath=str(output) if output.exists() else None,physicalFrameVerified=False)
print(json.dumps(result,indent=2))
'''
payload=subprocess.check_output(['wsl','-d','EtherPocketBuild','--','cat','/opt/etherpocket/ethercamera-spectra-arm64/ethercamera-spectra-capture'])
digest=hashlib.sha256(payload).hexdigest()
code='import pathlib,sys;p=pathlib.Path("/var/tmp/ethercamera-spectra-native/ethercamera-spectra-capture");p.write_bytes(sys.stdin.buffer.read());p.chmod(0o755)'
subprocess.run(SSH+['python3 -c '+shlex.quote(code)],input=payload,check=True)
prelude=(ROOT/'ethercamera/spectra/module_profile.py').read_text()+'\n'+(ROOT/'ethercamera/spectra/capture_profile.py').read_text().replace('from module_profile import decode,ProfileError','')
source=prelude+'\nSTREAM='+repr('--stream' in sys.argv)+'\n'+SOURCE.replace('DIGEST',repr(digest))
p=subprocess.run(SSH+['python3 -c '+shlex.quote(source)],capture_output=True,text=True,timeout=70)
if p.returncode:raise RuntimeError(p.stderr)
data=json.loads(p.stdout)
(ROOT/'evidence/ethercamera-spectra-raw-test.json').write_text(json.dumps(data,indent=2)+'\n')
print(json.dumps(data,indent=2))
