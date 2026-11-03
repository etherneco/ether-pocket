"""Apply and verify supported profiles through D-Bus; restore baseline, then Balanced.
Never suspend, modify charging, detach USB or stop existing hardware services.
"""
from pathlib import Path
import json,runpy,shlex,subprocess
ROOT=Path(__file__).resolve().parent.parent
SSH=runpy.run_path(str(ROOT/'scripts/deploy-ethermobile.py'))['SSH']
SOURCE=r'''
import dbus,json,pathlib,subprocess,time
api=dbus.Interface(dbus.SystemBus().get_object('com.etherneco.EtherPower1','/com/etherneco/EtherPower1'),'com.etherneco.EtherPower1')
def state():
 for _ in range(60):
  d=json.loads(str(api.GetState()))
  if d.get('ready') and not d.get('busy'):return d
  time.sleep(.2)
 raise AssertionError('Service did not settle')
def guards():return {s:subprocess.run(['systemctl','is-active',s],capture_output=True,text=True).stdout.strip() for s in ['NetworkManager','ModemManager','bluetooth','ssh','ethershare','ethermobile-data','etherpocket-modem','etherpocket-usb-debug','etherpocket-usb-storage']}
before=state();services=guards();results={}
charging_fields=['charging_enabled','input_suspend','charge_control_limit','sw_jeita_enabled']
def charging():
 d={}
 for k in charging_fields:
  try:d[k]=(pathlib.Path('/sys/class/power_supply/battery')/k).read_text().strip()
  except OSError:d[k]=None
 return d
protected=charging()
try:
 for mode in ['balanced','power-saver','performance']:
  api.ApplyProfile(mode,'',timeout=60);s=state()
  assert s['profileState']['requested']==mode and s['profileState']['effective']==mode,s['profileState']
  governor={'balanced':'schedutil','power-saver':'conservative','performance':'performance'}[mode]
  assert all(p['governor']==governor for p in s['controls']['cpu'])
  assert s['controls']['gpu']['governor']=='msm-adreno-tz'
  results[mode]={'profile':s['profileState'],'controls':s['controls'],'telemetry':{k:s[k] for k in ['batteryPowerW','usbInputPowerW','cpuTemperatureC','batteryTemperatureC','status']}}
 api.RestoreOriginal(timeout=60);restored=state()
 assert all(p['governor']=='performance' for p in restored['controls']['cpu'])
 original_config=dict(restored['config'])
 api.Configure(json.dumps({'batteryTimeout':30}),timeout=60)
 assert state()['config']['batteryTimeout']==30
 api.Configure(json.dumps({'batteryTimeout':original_config['batteryTimeout']}),timeout=60)
 try:api.ApplyProfile('custom','{"cpu":{"../../etc/passwd":{}}}',timeout=60)
 except dbus.DBusException:pass
 else:raise AssertionError('Unsafe policy accepted')
 s=state();assert all(p['governor']=='performance' for p in s['controls']['cpu'])
 try:api.PowerAction('suspend',timeout=60)
 except dbus.DBusException as e:assert 'wake' in str(e).lower() or 'busy' in str(e).lower()
 else:raise AssertionError('Unverified suspend accepted')
 api.ApplyProfile('balanced','',timeout=60);final=state()
 subprocess.run(['systemctl','restart','etherpower'],check=True)
 api=dbus.Interface(dbus.SystemBus().get_object('com.etherneco.EtherPower1','/com/etherneco/EtherPower1'),'com.etherneco.EtherPower1')
 final=state();assert final['profileState']['effective']=='balanced'
 assert final['config']['batteryTimeout']==original_config['batteryTimeout']
 api.GetHistory(dbus.UInt32(24))
 for _ in range(60):
  h=json.loads(str(api.GetHistory(dbus.UInt32(24))))
  if h['ready'] and h['samples']:break
  time.sleep(.2)
 assert h['samples']
 assert guards()==services and charging()==protected
 print(json.dumps({'before':before,'profiles':results,'restored':restored['controls'],'final':final,'servicesBefore':services,'servicesAfter':guards(),'chargingBefore':protected,'chargingAfter':charging(),'historyPoints':len(h['samples']),'suspendBlocked':True,'unsafePolicyRejected':True},indent=2))
except BaseException:
 try:api.RestoreOriginal(timeout=60)
 except Exception:pass
 raise
'''
if __name__=='__main__':
 p=subprocess.run(SSH+['python3 -c '+shlex.quote(SOURCE)],capture_output=True,timeout=120)
 if p.returncode:raise RuntimeError(p.stderr.decode(errors='replace')[-7000:])
 d=json.loads(p.stdout);(ROOT/'evidence/etherpower-profiles.json').write_text(json.dumps(d,indent=2)+'\n',encoding='utf-8')
 print(json.dumps({'profiles':list(d['profiles']),'effective':d['final']['profileState'],'historyPoints':d['historyPoints'],'suspendBlocked':d['suspendBlocked']},indent=2))
