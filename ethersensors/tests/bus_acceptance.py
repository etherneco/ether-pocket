"""Run under dbus-run-session on Linux; no physical sensor fixtures/injection."""
import json,os,subprocess,sys,time
from pathlib import Path
import dbus
root=Path(__file__).resolve().parents[1]
p=subprocess.Popen([sys.executable,str(root/'service.py')],stdout=subprocess.PIPE,stderr=subprocess.PIPE)
try:
 bus=dbus.SessionBus()
 for n in range(50):
  if bus.name_has_owner('com.etherneco.EtherSensors1'):break
  if p.poll() is not None:raise RuntimeError(p.stderr.read().decode())
  time.sleep(.1)
 api=dbus.Interface(bus.get_object('com.etherneco.EtherSensors1','/com/etherneco/EtherSensors1'),'com.etherneco.EtherSensors1')
 state=json.loads(str(api.GetState()));assert state['ready'] and not state['simulated'] and state['activeSubscriptions']==0
 sensors=json.loads(str(api.ListSensors()));assert sensors and all(not s['verified'] for s in sensors)
 assert not json.loads(str(api.GetOrientation()))['available']
 assert not json.loads(str(api.GetMotionState()))['available']
 denied=[]
 for method,args in [('Configure',('{"autoRotate":true}',)),('RequestPermission',('{"rate":10,"background":true}',)),('GetManagement',()),('TestSensor',('unavailable:accelerometer',)),('StartSubscription',('unavailable:accelerometer',1.,False)),('ReadLatest',('forged-token',)),('ExportDiagnostics',()),('RequestCalibration',('unavailable:gyroscope',))]:
  try:getattr(api,method)(*args)
  except dbus.DBusException:denied.append(method)
  else:raise AssertionError('Unauthorized operation accepted: '+method)
 assert json.loads(str(api.GetState()))['activeSubscriptions']==0
 print(json.dumps(dict(ready=True,denied=denied,realMeasurementsVerified=False,sensors=len(sensors),idle=True)))
finally:
 p.terminate()
 try:p.wait(timeout=5)
 except subprocess.TimeoutExpired:p.kill();p.wait()
