"""Provision the tested framework locally. Not an AutoUpdate Center release."""
from pathlib import Path
import hashlib,io,json,runpy,tarfile
ROOT=Path(__file__).resolve().parent.parent
remote=runpy.run_path(str(ROOT/'scripts/verify-etherupdate-device.py'))['remote']
if __name__=='__main__':
 tests=json.loads((ROOT/'evidence/ethersensors-device-tests.json').read_text())
 assert tests['servicesUnchanged'] and all(t['exit']==0 for t in tests['tests'].values())
 files={name:ROOT/'build'/name for name in ('ether-sensors_0.1.0_arm64.deb','etherhardware_0.1.1_arm64.deb')}
 hashes={name:hashlib.sha256(path.read_bytes()).hexdigest() for name,path in files.items()}
 payload=io.BytesIO()
 with tarfile.open(fileobj=payload,mode='w') as archive:
  for name,path in files.items():archive.add(path,arcname=name)
 source=r'''
import hashlib,io,json,pathlib,subprocess,sys,tarfile,tempfile,time
assert pathlib.Path('/etc/etherpocket/disk-identity').read_text().strip()=='GM1920-548cb338-mobian-sda21'
def run(args,timeout=30):return subprocess.run(args,capture_output=True,text=True,check=True,timeout=timeout)
user=['runuser','-u','mobian','--','env','XDG_RUNTIME_DIR=/run/user/1000','DBUS_SESSION_BUS_ADDRESS=unix:path=/run/user/1000/bus']
def probe():return run(['systemctl','show','ssh','NetworkManager','ModemManager','etherpower','etherpocket-modem','bluetooth','-p','MainPID','-p','ActiveState']).stdout
before=probe()
previous=subprocess.run(user+['ethersensors','state'],capture_output=True,text=True,timeout=10)
if previous.returncode==0:assert json.loads(previous.stdout)['activeSubscriptions']==0,'Stop sensor sessions before upgrading'
with tempfile.TemporaryDirectory(prefix='ethersensors-provision-',dir='/var/tmp') as folder:
 root=pathlib.Path(folder)
 with tarfile.open(fileobj=io.BytesIO(sys.stdin.buffer.read()),mode='r:') as archive:
  for m in archive:
   assert m.name in HASHES and m.isfile()
   data=archive.extractfile(m).read();assert hashlib.sha256(data).hexdigest()==HASHES[m.name];(root/m.name).write_bytes(data)
 run(['dpkg','--dry-run','-i']+[str(root/n) for n in HASHES])
 run(['dpkg','-i']+[str(root/n) for n in HASHES])
 run(user+['systemctl','--user','daemon-reload'])
 run(user+['systemctl','--user','enable','--now','ethersensors'])
 run(user+['systemctl','--user','restart','ethersensors'])
 run(['systemctl','restart','etherhardware'])
 state=json.loads(run(user+['ethersensors','state']).stdout)
 assert state['ready'] and state['activeSubscriptions']==0 and all(not r['verified'] for r in state['sensors'])
 hardware=json.loads(run(['busctl','--json=short','call','com.etherneco.EtherHardware1','/com/etherneco/EtherHardware1','com.etherneco.EtherHardware1','GetState']).stdout)['data'][0]
 hardware=json.loads(hardware)
 for n in range(30):
  if hardware.get('ready') and not hardware.get('busy'):break
  time.sleep(.2)
  hardware=json.loads(json.loads(run(['busctl','--json=short','call','com.etherneco.EtherHardware1','/com/etherneco/EtherHardware1','com.etherneco.EtherHardware1','GetState']).stdout)['data'][0])
 assert any(c['id']=='sensors.orientation' and c.get('physical') is False for c in hardware['capabilities'])
 after=probe();assert before==after
 print(json.dumps(dict(packageHashes=HASHES,servicesUnchanged=True,sensorState=state,hardwareRegistryIntegrated=True,publication=False)))
'''.replace('HASHES',repr(hashes))
 result=json.loads(remote(source,payload.getvalue(),timeout=120))
 (ROOT/'evidence/ethersensors-install.json').write_text(json.dumps(result,indent=2)+'\n',encoding='utf-8')
 print(json.dumps({k:v for k,v in result.items() if k!='sensorState'},indent=2))
