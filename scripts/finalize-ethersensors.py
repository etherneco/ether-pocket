"""Record installed package hashes, live service health and real shell screenshot."""
from pathlib import Path
import hashlib,io,json,runpy,tarfile
ROOT=Path(__file__).resolve().parent.parent
remote=runpy.run_path(str(ROOT/'scripts/verify-etherupdate-device.py'))['remote']
if __name__=='__main__':
 source=r'''
import io,json,pathlib,subprocess,sys,tarfile
assert pathlib.Path('/etc/etherpocket/disk-identity').read_text().strip()=='GM1920-548cb338-mobian-sda21'
def run(args,timeout=20):
 p=subprocess.run(args,capture_output=True,text=True,timeout=timeout)
 return dict(exit=p.returncode,stdout=p.stdout,stderr=p.stderr[:1000])
user=['runuser','-u','mobian','--','env','XDG_RUNTIME_DIR=/run/user/1000','DBUS_SESSION_BUS_ADDRESS=unix:path=/run/user/1000/bus']
code="""import dbus,json
b=dbus.SessionBus();out={}
for c in ('EtherSensors','EtherLock','EtherCamera','EtherPhone','EtherLocation','EtherNotifications'):
 try:
  n='com.etherneco.'+c+'1';s=json.loads(str(dbus.Interface(b.get_object(n,'/com/etherneco/'+c+'1'),n).GetState(timeout=3)))
  out[c]={k:s.get(k) for k in ('ready','locked','busy','recording','activeSubscriptions','profile')};out[c]['callCount']=len(s.get('calls',[]))
 except dbus.DBusException as e:out[c]={'error':str(e)}
print(json.dumps(out))
"""
health=run(user+['python3','-c',code]);assert health['exit']==0
health=json.loads(health['stdout']);assert health['EtherSensors']['ready'] and health['EtherSensors']['activeSubscriptions']==0
state=json.loads(run(user+['ethersensors','state'])['stdout'])
services=run(['systemctl','is-active','ssh','NetworkManager','ModemManager','etherhardware','etherpower','etherpocket-modem','bluetooth'])
assert services['exit']==0
update=run(['etherupdate','state']);update=json.loads(update['stdout']) if update['exit']==0 else {}
policy=json.loads(pathlib.Path('/etc/etherupdate/policy.json').read_text())
trust=json.loads(pathlib.Path('/etc/etherupdate/trusted-keys.json').read_text())
result=dict(kernel=pathlib.Path('/proc/sys/kernel/osrelease').read_text().strip(),health=health,services=services,
 sensorState=state,packages=run(['dpkg-query','-W','ether-sensors','etherhardware']),
 sensorUnit=run(user+['systemctl','--user','show','ethersensors','-p','ActiveState','-p','SubState','-p','NRestarts']),
 wifiHTTPS=run(['curl','--interface','wlan0','--connect-timeout','8','--max-time','12','-sS','-o','/dev/null','-w','%{http_code}','https://deb.debian.org']),
 touchscreenNodePresent=pathlib.Path('/dev/input/event5').exists(),
 updateCommissioning=dict(ready=update.get('ready'),credentialConfigured=update.get('credentialConfigured'),componentMappings=len(policy.get('components',{})),trustStructureKeys=list(trust) if isinstance(trust,dict) else None),
 acceptance=dict(physicalMeasurements=False,fusion=False,suspendResume=False,bootRoundTrip=False,androidPartitionRegression=False,realCallProximity=False,externalDisplayMotion=False,published=False))
with tarfile.open(fileobj=sys.stdout.buffer,mode='w|gz') as archive:
 data=json.dumps(result,indent=2).encode();info=tarfile.TarInfo('regression.json');info.size=len(data);archive.addfile(info,io.BytesIO(data))
 image=pathlib.Path('/home/mobian/.config/ethershell/validation/settings2-screen.png')
 if image.exists():archive.add(image,arcname='live-screen.png')
'''
 output=ROOT/'evidence/ethersensors-live';output.mkdir(exist_ok=True)
 result=remote(source,timeout=90)
 with tarfile.open(fileobj=io.BytesIO(result),mode='r:gz') as archive:archive.extractall(output,filter='data')
 state=json.loads((output/'regression.json').read_text())
 state['packageHashes']={n:hashlib.sha256((ROOT/'build'/n).read_bytes()).hexdigest() for n in ('ether-sensors_0.1.0_arm64.deb','etherhardware_0.1.1_arm64.deb','ethershell_2.1.0_ethersensors_arm64.deb')}
 state['tests']=dict(sensorUnitTests=25,hardwareRegressionTests=20,unauthorizedBusOperationsRejected=8,uiSizes=4,uiThemes=2)
 state['networkRegression']=dict(wifiConnected=False,httpsPassed=False,
  preexistingFailure='NetworkManager logged DHCP ip-config-unavailable at 2026-10-21T08:21:13Z, before the initial sensor audit at 14:21Z',
  evidence=['ethersensors-network-check.json','ethersensors-wifi-history.json'],networkConfigurationChanged=False)
 state['deliveryStatus']='Independent framework installed; real motion/light/proximity measurements blocked; full Task 10 incomplete'
 (ROOT/'evidence/ethersensors-delivery.json').write_text(json.dumps(state,indent=2)+'\n',encoding='utf-8')
 print(json.dumps({k:v for k,v in state.items() if k not in ('sensorState','health')},indent=2))
