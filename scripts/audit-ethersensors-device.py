"""Read-only sensor audit over the existing pinned handset SSH channel."""
from pathlib import Path
import json, runpy, subprocess
ROOT = Path(__file__).resolve().parent.parent
SSH = runpy.run_path(str(ROOT/'scripts/deploy-ethermobile.py'))['SSH']
SOURCE = r'''
import datetime,gzip,json,pathlib,re,shutil,subprocess,os,select
def read(p):
 try:return pathlib.Path(p).read_text(errors='replace').replace('\0',' ').strip()[:16000]
 except OSError:return None
def run(args):
 if not shutil.which(args[0]):return {'available':False}
 try:
  p=subprocess.run(args,capture_output=True,text=True,timeout=12)
  return dict(exit=p.returncode,stdout=p.stdout[:100000],stderr=p.stderr[:2000])
 except subprocess.TimeoutExpired:return {'error':'timeout'}
base=pathlib.Path('/sys/firmware/devicetree/base')
try:config=gzip.open('/proc/config.gz','rt').read()
except OSError:config=''
iio=[]
for p in pathlib.Path('/sys/bus/iio/devices').glob('iio:device*'):
 attrs={x.name:read(x) for x in p.iterdir() if x.is_file() and (x.name=='name' or re.match(r'in_.*(raw|input|scale|offset|available)$',x.name) or x.name=='sampling_frequency')}
 driver=p/'device/driver'
 if not driver.exists():driver=p.resolve().parent/'driver'
 iio.append(dict(path=str(p),driver=str(driver.resolve()) if driver.exists() else None,attributes=attrs))
commands={k:run(v) for k,v in {
 'log':['dmesg'],'modules':['lsmod'],'qrtr':['qrtr-lookup'],'iio':['iio_info','-s'],
 'input':['libinput','list-devices'],'services':['systemctl','is-active','ssh','NetworkManager','etherhardware','etherpower','ModemManager'],
 'sensorServices':['sh','-c','ps -eo comm,args | head -250'],
 'hardware':['busctl','call','com.etherneco.EtherHardware1','/com/etherneco/EtherHardware1','com.etherneco.EtherHardware1','GetState'],
 'packages':['dpkg-query','-W','*sensor*','*iio*','*qrtr*']}.items()}
commands['log']['stdout']='\n'.join(x for x in commands['log'].get('stdout','').splitlines() if re.search('slpi|ssc|sensor|adsp|dsps|smd|qrtr|remoteproc|pil|firmware',x,re.I))
commands['sensorServices']['stdout']='\n'.join(x for x in commands['sensorServices'].get('stdout','').splitlines() if re.search('sensor|slpi|ssc|adsprpc',x,re.I))
passive={}
for p in pathlib.Path('/sys/class/input').glob('event*'):
 if read(p/'device/name') not in ('STM VL53L1 proximity sensor','elliptic_ultrasound_proximity'):continue
 node='/dev/input/'+p.name
 try:
  fd=os.open(node,os.O_RDONLY|os.O_NONBLOCK)
  try:passive[node]={'bytes':len(os.read(fd,4096)) if select.select([fd],[],[],1)[0] else 0,'measurementVerified':False}
  finally:os.close(fd)
 except OSError as e:passive[node]={'error':str(e)}
data=dict(passiveInput=passive,timestamp=datetime.datetime.now(datetime.timezone.utc).isoformat(),kernel=read('/proc/sys/kernel/osrelease'),identity=read('/etc/etherpocket/disk-identity'),model=read(base/'model'),iio=iio,
 input=read('/proc/bus/input/devices'),inputNodes=[dict(path=str(p),name=read(p/'device/name')) for p in pathlib.Path('/sys/class/input').glob('event*')],
 nodes=[str(p) for p in pathlib.Path('/dev').iterdir() if re.search('iio|sensor|smd|slpi|ssc|adsprpc',p.name,re.I)],
 ssc={str(p):[x.name for x in p.iterdir()] for p in pathlib.Path('/sys/class/ssc').glob('*')},
 config=[x for x in config.splitlines() if re.search('IIO|SENSORS|SLPI|SSC|SENSORS_SSC|MSM_DSPS|REMOTEPROC|QRTR|MSM_SMD|MSM_GL|RPMSG',x)],
 deviceTree={str(p.relative_to(base)):read(p) for p in base.rglob('*') if p.name in ('compatible','status','firmware-name') and re.search('slpi|ssc|sensor|dsps',str(p),re.I)},
 vendor={p:pathlib.Path(p).exists() for p in ['/vendor/lib64/hw/sensors.ssc.so','/vendor/bin/sensors.qcom','/vendor/bin/sscrpcd','/persist/sensors','/mnt/vendor/persist/sensors','/dev/sensors','/lib/firmware/slpi.mdt','/vendor/firmware/slpi.mdt']},commands=commands,
 scope='Read-only: no input grab, sensor enable, firmware load, calibration read/write or partition changes; changing physical measurements not yet verified')
print(json.dumps(data,indent=2))
'''
if __name__ == '__main__':
 p=subprocess.run(SSH+['python3 -'],input=SOURCE.encode(),capture_output=True,timeout=150,check=True)
 target=ROOT/'evidence/ethersensors-hardware-audit.json'
 target.write_text(json.dumps(json.loads(p.stdout),indent=2)+'\n',encoding='utf-8')
 print(target)
