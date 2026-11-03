"""Bounded native Spectra transport bring-up on the identified idle handset.
This exercises CRM/ISP/command memory, not sensor probing or capture. CRM
close invokes vendor subdevice cleanup: no camera/media owner may be active.
"""
from pathlib import Path
import argparse,hashlib,json,runpy,shlex,subprocess
ROOT=Path(__file__).resolve().parent.parent
SSH=runpy.run_path(str(ROOT/'scripts/deploy-ethermobile.py'))['SSH']
SOURCE=r'''
import hashlib,json,pathlib,subprocess,sys,time
assert pathlib.Path('/etc/etherpocket/disk-identity').read_text().strip()=='GM1920-548cb338-mobian-sda21'
binary=pathlib.Path('/var/tmp/ethercamera-spectra-native/ethercamera-spectra')
assert hashlib.sha256(binary.read_bytes()).hexdigest()==DIGEST
user=['runuser','-u','mobian','--','env','XDG_RUNTIME_DIR=/run/user/1000','DBUS_SESSION_BUS_ADDRESS=unix:path=/run/user/1000/bus']
def state():return json.loads(subprocess.check_output(user+['ethercamera','state'],text=True,timeout=10))
def snapshot():
 return dict(bootId=pathlib.Path('/proc/sys/kernel/random/boot_id').read_text().strip(),
  services={name:subprocess.check_output(['systemctl','show',name,'-p','MainPID','--value'],text=True).strip() for name in ['NetworkManager','ssh','etherhardware','etherpower','ModemManager']},
  processes={name:subprocess.run(['pgrep','-u','1000','-x',name],capture_output=True,text=True).stdout.strip() for name in ['ethershell','pipewire','wireplumber']})
before=snapshot();camera=state();assert not camera['busy'] and not camera['active']
def holders():
 result=[]
 for proc in pathlib.Path('/proc').iterdir():
  if not proc.name.isdigit():continue
  try:
   for fd in (proc/'fd').iterdir():
    try:target=str(fd.resolve(strict=True))
    except FileNotFoundError:continue
    if target.startswith(('/dev/video','/dev/v4l-subdev','/dev/media')):result.append(dict(pid=proc.name,node=target))
  except (FileNotFoundError,ProcessLookupError):continue
 return result
assert holders()==[],'Do not disturb another media device owner'
if REAR:
 profiles={}
 for name,digest in [('semco_imx586','0e67372a3fb69030ab0e9749bf8de2c0b1a1774719ff9e388e6527be3afbb950'),('ofilm_imx586','ff92daf0496ee923f77f459e959d29907490dc15ed2e2eec932c1575cccd074d'),('semco_2nd_lens_imx586','5dc0f4ab6916f425a7dafaeaa6588d78e94673812bbc233009268627d4ee167d')]:
  raw=subprocess.check_output(['debugfs','-R','cat /lib64/camera/com.qti.sensormodule.'+name+'.bin','/dev/disk/by-partlabel/vendor_b'],stderr=subprocess.DEVNULL,timeout=15)
  profile=decode(raw);assert profile['sourceSha256']==digest
  profiles[name]=profile
 first=next(iter(profiles.values()))
 assert all(p['powerUp']==first['powerUp'] and p['powerDown']==first['powerDown'] for p in profiles.values())
nodes={}
for p in pathlib.Path('/sys/class/video4linux').iterdir():
 name=(p/'name').read_text().strip()
 if name in ['cam-req-mgr','cam-isp']:
  assert name not in nodes
  nodes[name]='/dev/'+p.name
assert set(nodes)=={'cam-req-mgr','cam-isp'}
test=subprocess.run(user+['/var/tmp/ethercamera-spectra-native/spectra-transport-test'],capture_output=True,text=True,timeout=10)
assert test.returncode==0,test.stderr
command=['systemd-run','--wait','--pipe','--collect','--unit=ethercamera-spectra-transport-test',
 '--property=Type=exec','--property=RuntimeMaxSec=12','--property=TimeoutStopSec=3',
 '--property=NoNewPrivileges=yes','--property=ProtectSystem=strict','--property=ProtectHome=yes',
 '--property=PrivateNetwork=yes','--property=ProtectKernelTunables=yes',
 '--property=CapabilityBoundingSet=','--property=DevicePolicy=closed']
for node in nodes.values():command.append('--property=DeviceAllow='+node+' rw')
if REAR:
 for p in pathlib.Path('/sys/class/video4linux').iterdir():
  if (p/'name').read_text().strip()=='cam-sensor-driver':command.append('--property=DeviceAllow=/dev/'+p.name+' rw')
command += [str(binary),'--probe-rear-imx586' if REAR else '--transport-self-test']
p=subprocess.run(command,capture_output=True,text=True,timeout=25)
after=snapshot();assert before==after,(before,after)
assert holders()==[],'Camera descriptors leaked after native test'
current=state();assert not current['busy'] and not current['active'] and current['verified']==camera['verified']
result=dict(testExecutableStaged=True,binarySha256=DIGEST,before=before,after=after,nodes=nodes,
 softwareTests=test.stdout,exit=p.returncode,stderr=p.stderr,stdout=p.stdout,
 physicalFrameVerified=False,sensorProbeAttempted=REAR,openCameraNodesAfter=[])
if p.returncode==0:
 result['transport']=json.loads(p.stdout);assert result['transport']['transportVerified']
print(json.dumps(result,indent=2))
'''
if __name__=='__main__':
 parser=argparse.ArgumentParser();parser.add_argument('--rear-probe',action='store_true');args=parser.parse_args()
 subprocess.run(SSH+['install -d -m 755 /var/tmp/ethercamera-spectra-native'],check=True)
 for name in ['ethercamera-spectra','spectra-transport-test']:
  payload=subprocess.check_output(['wsl','-d','EtherPocketBuild','--','cat','/opt/etherpocket/ethercamera-spectra-arm64/'+name])
  (ROOT/'build'/(name+'_arm64')).write_bytes(payload)
  code=f'import pathlib,sys;p=pathlib.Path({("/var/tmp/ethercamera-spectra-native/"+name)!r});p.write_bytes(sys.stdin.buffer.read());p.chmod(0o755)'
  subprocess.run(SSH+['python3 -c '+shlex.quote(code)],input=payload,check=True,timeout=20)
 digest=hashlib.sha256((ROOT/'build/ethercamera-spectra_arm64').read_bytes()).hexdigest()
 prelude=(ROOT/'ethercamera/spectra/module_profile.py').read_text() if args.rear_probe else ''
 source=prelude+'\nREAR='+repr(args.rear_probe)+'\n'+SOURCE.replace('DIGEST',repr(digest))
 p=subprocess.run(SSH+['python3 -c '+shlex.quote(source)],capture_output=True,text=True,timeout=80)
 if p.returncode:raise RuntimeError(p.stderr)
 data=json.loads(p.stdout);target='ethercamera-spectra-rear-probe.json' if args.rear_probe else 'ethercamera-spectra-device.json'
 (ROOT/'evidence'/target).write_text(json.dumps(data,indent=2)+'\n',encoding='utf-8')
 print(json.dumps(data,indent=2))
