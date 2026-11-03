"""Bounded read-only GNSS feasibility audit via the existing pinned SSH channel."""
from pathlib import Path
import json, runpy, subprocess
ROOT=Path(__file__).resolve().parent.parent
SSH=runpy.run_path(str(ROOT/'scripts/deploy-ethermobile.py'))['SSH']
SOURCE=r'''
import datetime,gzip,json,pathlib,re,shutil,subprocess
def run(args):
 if not shutil.which(args[0]):return {'available':False}
 try:
  p=subprocess.run(args,capture_output=True,text=True,timeout=12)
  return dict(exit=p.returncode,stdout=p.stdout[:60000],stderr=p.stderr[:2000])
 except subprocess.TimeoutExpired:return {'error':'timeout'}
def read(p):
 try:return pathlib.Path(p).read_text(errors='replace').replace('\0',' ').strip()
 except OSError:return None
base=pathlib.Path('/sys/firmware/devicetree/base')
try:config=gzip.open('/proc/config.gz','rt').read()
except OSError:config=''
commands={k:run(v) for k,v in {
 'modems':['mmcli','-L'],'qrtr':['qrtr-lookup'],
 'services':['systemctl','is-active','ModemManager','ofono','gpsd','geoclue','ssh','NetworkManager','etherhardware','etherpower'],
 'bus':['busctl','--system','list','--no-pager'],
 'packages':['dpkg-query','-W','*gps*','*gnss*','*geoclue*','*qmi*','*qrtr*'],
 'log':['dmesg'],'qmiHelp':['qmicli','--help-loc'],
 'hardware':['busctl','call','com.etherneco.EtherHardware1','/com/etherneco/EtherHardware1','com.etherneco.EtherHardware1','GetState'],
 'mmObjects':['busctl','tree','org.freedesktop.ModemManager1']}.items()}
commands['log']['stdout']='\n'.join(x for x in commands['log'].get('stdout','').splitlines() if re.search('gnss|gps|modem|qmi|qrtr|remoteproc|pil.*mba',x,re.I))
print(json.dumps(dict(timestamp=datetime.datetime.now(datetime.timezone.utc).isoformat(),
 identity=read('/etc/etherpocket/disk-identity'),kernel=read('/proc/sys/kernel/osrelease'),model=read(base/'model'),
 nodes=[str(p) for p in pathlib.Path('/dev').iterdir() if re.search('gnss|gps|smd|qmi|qrtr|cdc-wdm|ttyUSB|ttyACM',p.name,re.I)],
 config=[x for x in config.splitlines() if re.search('GNSS|QRTR|QMI|REMOTEPROC|MSM_SMD|MSM_GL|RPMSG',x)],
 deviceTree={str(p.relative_to(base)):read(p) for p in base.rglob('compatible') if re.search('gnss|gps|modem|qrtr',str(p),re.I)},
 vendor={p:pathlib.Path(p).exists() for p in ['/vendor/bin/loc_launcher','/vendor/bin/gnss_service','/vendor/lib64/hw/gps.default.so','/vendor/bin/hw/android.hardware.gnss@2.0-service-qti','/dev/gnss0']},
 commands=commands,realFix='Not tested',scope='Read only; no daemon installation, modem restart, firmware or partition writes'),indent=2))
'''
if __name__=='__main__':
 p=subprocess.run(SSH+['python3 -'],input=SOURCE.encode(),capture_output=True,check=True,timeout=160)
 data=json.loads(p.stdout);target=ROOT/'evidence/etherlocation-hardware-audit.json'
 target.write_text(json.dumps(data,indent=2)+'\n',encoding='utf-8');print(target)
 for key in ('qrtr','modems','services'):print(key,data['commands'][key])
