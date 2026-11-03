"""Bounded read-only handset audit; never streams or touches motor/calibration."""
from pathlib import Path
import json, runpy, shlex, subprocess
ROOT = Path(__file__).resolve().parent.parent
SSH = runpy.run_path(str(ROOT/'scripts/deploy-ethermobile.py'))['SSH']
SOURCE = r'''
import datetime,fcntl,gzip,json,os,pathlib,re,shutil,struct,subprocess
def read(p):
 try:return pathlib.Path(p).read_text(errors='replace').replace('\0',' ').strip()
 except OSError:return None
def run(args):
 if not shutil.which(args[0]):return {'available':False}
 try:
  p=subprocess.run(args,capture_output=True,text=True,timeout=15)
  return dict(exit=p.returncode,stdout=p.stdout[:150000],stderr=p.stderr[:4000])
 except subprocess.TimeoutExpired:return {'error':'timeout'}
nodes=[]
for p in pathlib.Path('/sys/class/video4linux').glob('*'):
 row=dict(node='/dev/'+p.name,name=read(p/'name'),driver=str((p/'device/driver').resolve()))
 if p.name.startswith('video'):
  try:
   fd=os.open(row['node'],os.O_RDONLY|os.O_NONBLOCK)
   try:
    b=bytearray(104);fcntl.ioctl(fd,0x80685600,b,True)
    row.update(queryDriver=bytes(b[:16]).split(b'\0')[0].decode(),card=bytes(b[16:48]).split(b'\0')[0].decode())
    version,caps,devcaps=struct.unpack_from('=III',b,80);row.update(caps=caps,deviceCaps=devcaps)
   finally:os.close(fd)
  except OSError as e:row['queryError']=str(e)
 nodes.append(row)
dt={}
base=pathlib.Path('/sys/firmware/devicetree/base')
for p in base.rglob('*'):
 if p.name in ('compatible','status','qcom,sensor-name','qcom,actuator-name') and re.search('cam|cci|csiphy|actuator|eeprom|motor',str(p),re.I):dt[str(p.relative_to(base))]=read(p)
try:config=gzip.open('/proc/config.gz','rt').read()
except OSError:config=''
data=dict(timestamp=datetime.datetime.now(datetime.timezone.utc).isoformat(),identity=read('/etc/etherpocket/disk-identity'),model=read(base/'model'),compatible=read(base/'compatible'),kernel=read('/proc/sys/kernel/osrelease'),nodes=nodes,deviceTree=dt,
 config=[x for x in config.splitlines() if re.search('CAMERA|CAMSS|VIDEO_V4L2|VIDEO_VIDEOBUF|MEDIA_CONTROLLER|USB_VIDEO|MSM_CCI|MSM_ISP',x)],
 commands={k:run(v) for k,v in {'v4l':['v4l2-ctl','--list-devices'],'media0':['media-ctl','-d','/dev/media0','-p'],'media1':['media-ctl','-d','/dev/media1','-p'],'log':['dmesg'],'modules':['lsmod'],'services':['systemctl','is-active','ssh','NetworkManager','etherhardware','etherpower','etherpocket-audio'],'packages':['dpkg-query','-W','*camera*','*libcamera*','*gstreamer*','*zxing*'],'mounts':['findmnt','-rn','-o','TARGET,SOURCE,FSTYPE']}.items()},
 vendorPaths={p:os.path.exists(p) for p in ['/vendor/lib64/hw/camera.qcom.so','/vendor/bin/hw/android.hardware.camera.provider@2.4-service','/dev/cam_req_mgr','/dev/cam_sync','/dev/ion']},
 motor={str(p):dict(driver=str((p/'driver').resolve()),attributes=[x.name for x in p.iterdir()]) for p in pathlib.Path('/sys/devices/platform/vendor').glob('*motor*')},
 firmwarePaths={p:os.path.exists(p) for p in ['/lib/firmware/CAMERA_ICP.elf','/lib/firmware/qcom/CAMERA_ICP.elf','/vendor/firmware/CAMERA_ICP.elf']},
 scope='Read-only querycap/topology; no stream, motor attribute access, firmware, partition or calibration writes')
data['commands']['log']['stdout']='\n'.join(x for x in data['commands']['log'].get('stdout','').splitlines() if re.search('cam|sensor|cci|csiphy|eeprom|actuator|motor|venus',x,re.I))
print(json.dumps(data,indent=2))
'''
if __name__ == '__main__':
    p=subprocess.run(SSH+['python3 -c '+shlex.quote(SOURCE)],capture_output=True,check=True,timeout=150)
    data=json.loads(p.stdout)
    target=ROOT/'evidence/ethercamera-audit-2026-10-20.json'
    target.write_text(json.dumps(data,indent=2)+'\n',encoding='utf-8')
    print(json.dumps(data,indent=2))
