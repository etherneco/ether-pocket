"""Read-only GM1920 fingerprint audit over the existing pinned SSH connection.

No device opens, ioctls, mounts, template access or vendor code execution.
"""
import json
from pathlib import Path
import subprocess

ROOT = Path(__file__).resolve().parent.parent
SSH = ['ssh', '-i', str(ROOT/'build/etherpocket_ed25519'), '-o',
       'UserKnownHostsFile='+str(ROOT/'build/mobian-known-hosts'), '-o',
       'BatchMode=yes', '-o', 'ConnectTimeout=8', 'root@10.77.0.2']
SOURCE = r'''
import datetime,gzip,json,pathlib,re,subprocess,os
P=pathlib.Path
assert P('/etc/etherpocket/disk-identity').read_text().strip()=='GM1920-548cb338-mobian-sda21'
pattern=re.compile(r'fingerprint|goodix|qsee|gatekeeper|keymaster|fpc|gf[0-9_]|hbm|dimlayer',re.I)
def read(p):
 try:return P(p).read_bytes()[:131072].decode(errors='replace').replace('\0',' ').strip()
 except OSError:return ''
def run(args):
 try:
  p=subprocess.run(args,capture_output=True,text=True,timeout=20)
  return dict(code=p.returncode,stdout=p.stdout[:65536],stderr=p.stderr[:1000])
 except (OSError,subprocess.TimeoutExpired) as e:return dict(error=type(e).__name__)
result=dict(timeUtc=datetime.datetime.now(datetime.timezone.utc).isoformat(),kernel=read('/proc/version'),buses={},deviceTree={},nodes=[],vendor={},displayPaths=[],readOnly=True)
for bus in ['spi','i2c','platform']:
 entries=[]
 for p in sorted(P('/sys/bus/'+bus+'/devices').glob('*')):
  item=dict(name=p.name,driver=(p/'driver').resolve().name if (p/'driver').exists() else None)
  for name in ['modalias','uevent','of_node/compatible']:item[name]=read(p/name)
  entries.append(item)
 result['buses'][bus]=entries
for p in P('/proc/device-tree').rglob('*'):
 if p.name in ['compatible','status']:
  value=read(p)
  if pattern.search(str(p)+' '+value):result['deviceTree'][str(p)]=value
for p in P('/dev').iterdir():
 if pattern.search(p.name):
  s=p.stat();result['nodes'].append(dict(path=str(p),mode=oct(s.st_mode&0o777),major=os.major(s.st_rdev),minor=os.minor(s.st_rdev)))
for base in ['/sys/class/drm','/sys/class/backlight','/sys/devices/platform/soc']:
 for p in P(base).glob('**/*'):
  if pattern.search(p.name):result['displayPaths'].append(str(p))
try:
 config=gzip.open('/proc/config.gz','rt').read()
 result['kernelConfig']=[s for s in config.splitlines() if pattern.search(s)]
except OSError:result['kernelConfig']=None
result['input']=[s for s in read('/proc/bus/input/devices').split('\n\n') if pattern.search(s)]
result['modules']=read('/proc/modules')
result['packages']=run(['dpkg-query','-W','*fprint*','*pam*','*hybris*'])
result['fprintd']=run(['busctl','--system','--timeout=3','call','net.reactivated.Fprint','/net/reactivated/Fprint/Manager','net.reactivated.Fprint.Manager','GetDevices'])
result['services']=run(['systemctl','is-active','ssh','etherlock','etherhardware','etherpower','etherupdate','NetworkManager'])
result['secureRuntime']={p:P(p).exists() for p in ['/dev/qseecom','/dev/hwbinder','/dev/vndbinder','/system/bin/linker64','/vendor/bin/hw']}
device='/dev/disk/by-partlabel/vendor_b'
assert P(device).is_symlink()
def vendor(command):return run(['debugfs','-R',command,device])
for directory in ['/lib64/hw','/lib/hw','/bin/hw','/etc/init','/firmware','/firmware_mnt/image']:
 data=vendor('ls -l '+directory)
 data['stdout']='\n'.join(s for s in data.get('stdout','').splitlines() if pattern.search(s))
 result['vendor'][directory]=data
for directory in ['/lib64','/lib']:
 data=vendor('ls -l '+directory)
 data['stdout']='\n'.join(s for s in data.get('stdout','').splitlines() if pattern.search(s))
 result['vendor'][directory]=data
result['vendorMethod']='debugfs without -w; metadata and init text only; no mount or binary copying'
result['vendorInit']={path:vendor('cat '+path) for path in [
 '/etc/init/android.hardware.biometrics.fingerprint@2.1-service.rc',
 '/etc/init/qseecomd.rc', '/etc/init/android.hardware.gatekeeper@1.0-service-qti.rc']}
print(json.dumps(result,indent=2))
'''

if __name__ == '__main__':
    p = subprocess.run(SSH+['python3 -'], input=SOURCE.encode(), capture_output=True, timeout=150)
    if p.returncode:
        raise SystemExit(p.stderr.decode(errors='replace'))
    data = json.loads(p.stdout)
    target = ROOT/'evidence/etherfingerprint-device-audit.json'
    target.write_text(json.dumps(data, indent=2)+'\n', encoding='utf-8')
    print(target)
