"""Actual user shell, bounded blank/wake, brightness, resource and power samples.
No suspend, reboot, charger removal, radio action or physical-display reconfiguration.
"""
from pathlib import Path
import json,runpy,shlex,subprocess
ROOT=Path(__file__).resolve().parent.parent
SSH=runpy.run_path(str(ROOT/'scripts/deploy-ethermobile.py'))['SSH']
SOURCE=r'''
import dbus,json,os,pathlib,socket,struct,subprocess,time
api=dbus.Interface(dbus.SystemBus().get_object('com.etherneco.EtherPower1','/com/etherneco/EtherPower1'),'com.etherneco.EtherPower1')
pids=subprocess.check_output(['pgrep','-u','1000','-x','ethershell'],text=True).split();assert len(pids)==1
proc=pathlib.Path('/proc')/pids[0];assert proc.stat().st_uid==1000
assert (proc/'exe').resolve()==pathlib.Path(EXPECTED_STAGE)/'usr/bin/ethershell'
env=dict(x.split('=',1) for x in (proc/'environ').read_bytes().decode().split('\0') if '=' in x)
assert env.get('ETHERSHELL_SOFT_BLANK')=='1'
endpoint='/run/user/1000/ethershell-control-experience-'+env['DISPLAY'].replace(':','').replace('.','-')
def request(data):
 with socket.socket(socket.AF_UNIX,socket.SOCK_STREAM) as s:
  s.settimeout(10);s.connect(endpoint);s.sendall(json.dumps(data).encode()+b'\n');result=s.recv(8192).decode().strip()
  assert result!='locked','Existing session is locked; do not bypass it'
  return result
def display(action='state'):return json.loads(request({'command':'power-display','action':action}))
def state():
 for _ in range(100):
  d=json.loads(str(api.GetState()))
  if d.get('ready') and not d.get('busy'):return d
  time.sleep(.1)
 raise AssertionError('Power service did not settle')
def measure(label):
 old=state()['timestamp'];api.Refresh()
 for _ in range(100):
  s=state()
  if s['timestamp']!=old:break
  time.sleep(.15)
 assert s['timestamp']!=old
 return {'label':label,'display':display(),'timestamp':s['timestamp'],
 'profile':s['profileState'],'cpuCurrentKHz':[p['currentKHz'] for p in s['controls']['cpu']],
 'batteryStatus':s['status'],'batteryPowerW':s['batteryPowerW'],'usbInputEstimateW':s['usbInputPowerW'],
 'totalDevicePowerW':s['totalDevicePowerW'],'cpuTemperatureC':s['cpuTemperatureC'],'batteryTemperatureC':s['batteryTemperatureC'],
 'scope':'USB-powered ADC observation; battery terminal and USB input are separate, not a battery endurance or total-device power measurement'}
initial=state();original_timeout=initial['config']['externalTimeout'];original_brightness=int(pathlib.Path('/sys/class/backlight/panel0-backlight/brightness').read_text())
assert initial['externalPower'],'USB-powered measurement requires a detected external source'
preferences=json.loads(pathlib.Path('/home/mobian/.config/ethershell/preferences.json').read_text())
old_brightness_preference=preferences.get('powerBrightnessExternal',-1)
services=['NetworkManager','ModemManager','bluetooth','ssh','ethershare','ethermobile-data','etherpocket-modem','etherhardware','etherpocket-usb-debug','etherpocket-usb-storage']
def guard():return {s:subprocess.run(['systemctl','is-active',s],capture_output=True,text=True).stdout.strip() for s in services}
before_services=guard();samples=[];safety=None;load=None
try:
 assert request({'command':'settings-page','route':'power'})=='ok'
 assert not display('on')['blank']
 # A separate short-lived wake helper survives a failed parent/SSH test.
 safety=subprocess.Popen(['python3','-c',"import os,subprocess,time;time.sleep(45);subprocess.run(['xset','s','reset'],env=os.environ)"],env=env,stdin=subprocess.DEVNULL,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,start_new_session=True)
 test=subprocess.run(['python3','/run/etherpower-soft-blank-test.py'],env=env,capture_output=True,text=True,timeout=35)
 assert test.returncode==0,test.stdout+test.stderr
 soft=json.loads(test.stdout)
 safety.terminate();safety.wait(timeout=3);safety=None
 display('on');time.sleep(.8)
 with open('/dev/input/event0','wb',buffering=0) as device:
  device.write(struct.pack('@llHHi',0,0,1,116,1));device.write(struct.pack('@llHHi',0,0,0,0,0));time.sleep(1.8)
  device.write(struct.pack('@llHHi',0,0,1,116,0));device.write(struct.pack('@llHHi',0,0,0,0,0))
 time.sleep(.6);long_press_awake=not display()['blank'];assert long_press_awake
 assert request({'command':'settings-screenshot'})=='ok'
 pathlib.Path('/run/etherpower-long-press.png').write_bytes(pathlib.Path('/home/mobian/.config/ethershell/validation/settings2-screen.png').read_bytes())
 assert request({'command':'key','symbol':'Escape'})=='ok';time.sleep(.3)
 # Existing user control validates and reads back the actual panel brightness.
 old_percent=display()['brightness'];trial=15 if old_percent!=15 else 20
 # The setting persists preference only; the live helper below exercises Core's provider.
 assert request({'command':'power-brightness','value':trial})=='ok'
 time.sleep(1);brightness=display();assert abs(int(brightness['brightness'])-trial)<=1
 assert request({'command':'power-brightness','value':old_percent})=='ok';time.sleep(.5)
 assert abs(int(display()['brightness'])-int(old_percent))<=1
 # Actual saved timeout -> X11 readback -> software blank -> wake.
 api.Configure(json.dumps({'externalTimeout':15}),timeout=60)
 for _ in range(30):
  if display()['timeoutSeconds']==15:break
  time.sleep(.2)
 assert display()['timeoutSeconds']==15
 display('on');time.sleep(16.5);timeout_blank=display()['blank'];assert timeout_blank
 assert not display('on')['blank']
 api.Configure(json.dumps({'externalTimeout':original_timeout}),timeout=60)
 api.ApplyProfile('performance','',timeout=60);samples.append(measure('performance-screen-on'))
 api.ApplyProfile('balanced','',timeout=60);samples.append(measure('balanced-screen-on'))
 safety=subprocess.Popen(['python3','-c',"import os,subprocess,time;time.sleep(25);subprocess.run(['xset','s','reset'],env=os.environ)"],env=env,stdin=subprocess.DEVNULL,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,start_new_session=True)
 assert display('off')['blank'];samples.append(measure('balanced-software-blank'))
 assert samples[-1]['display']['blank'];display('on');safety.terminate();safety.wait(timeout=3);safety=None
 if state()['cpuTemperatureC'] is None or state()['cpuTemperatureC']<70:
  load=subprocess.Popen(['runuser','-u','mobian','--','python3','-c','import time\nend=time.monotonic()+15\nwhile time.monotonic()<end: sum(i*i for i in range(1000))'],stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
  time.sleep(1);sample=measure('balanced-one-core-bounded-load');sample['loadActiveAtSample']=load.poll() is None;samples.append(sample)
  load.wait(timeout=20);load=None
 else:samples.append({'label':'bounded-load','skipped':'CPU temperature above conservative test guard'})
 # No electrical model is attached to application resources.
 for _ in range(20):
  resources=subprocess.run(['runuser','-u','mobian','--','etherpower','processes'],capture_output=True,text=True)
  if resources.returncode==0:break
  time.sleep(.3)
 assert resources.returncode==0,resources.stderr
 resources=json.loads(resources.stdout);assert resources['ready']
 assert all(r['energyWh'] is None for r in resources['processes'])
 assert all((pathlib.Path('/proc')/str(r['pid'])).stat().st_uid==1000 for r in resources['processes'] if (pathlib.Path('/proc')/str(r['pid'])).exists())
 # Short idle service-overhead sample; no actual wattage target is inferred.
 pid=int(subprocess.check_output(['systemctl','show','etherpower','-p','MainPID','--value'],text=True));p=pathlib.Path('/proc')/str(pid)
 def ticks():
  s=(p/'stat').read_text().split();return int(s[13])+int(s[14])
 start=time.monotonic();first=ticks();time.sleep(20);duration=time.monotonic()-start
 cpu=100*(ticks()-first)/os.sysconf('SC_CLK_TCK')/duration
 rss=next(s for s in (p/'status').read_text().splitlines() if s.startswith('VmRSS:'))
 final=state();assert final['profileState']['effective']=='balanced';assert final['sessionDisplay']['uid']==1000
 assert guard()==before_services
 assert request({'command':'settings-screenshot'})=='ok'
 print(json.dumps({'softBlankChecks':soft,'longPowerPressKeptScreenOn':long_press_awake,'brightnessTest':{'requested':trial,'effective':brightness['brightness'],'restoredPercent':display()['brightness']},
 'timeoutBlankVerified':timeout_blank,'samples':samples,'serviceOverhead':{'seconds':duration,'cpuPercentOfOneCore':cpu,'rss':rss},
 'resourceProcesses':len(resources['processes']),'resourceScope':resources['scope'],
 'servicesBefore':before_services,'servicesAfter':guard(),'finalState':final,'screenOn':not display()['blank']},indent=2))
finally:
 if safety and safety.poll() is None:safety.terminate()
 if load and load.poll() is None:load.terminate();load.wait(timeout=3)
 try:api.Configure(json.dumps({'externalTimeout':original_timeout}),timeout=60)
 except Exception:pass
 try:api.ApplyProfile('balanced','',timeout=60)
 except Exception:pass
 if 'old_percent' in locals():
  try:
   request({'command':'power-brightness','value':old_percent})
   request({'command':'setting','name':'powerBrightnessExternal','value':old_brightness_preference})
  except Exception:pass
 try:display('on')
 except Exception:subprocess.run(['xset','s','reset'],env=env,capture_output=True)
'''
if __name__=='__main__':
 deployment=json.loads((ROOT/'evidence/etherpower-shell-deployment.json').read_text())
 helper=(ROOT/'ethershell/tools/soft_blank_test.py').read_bytes()
 subprocess.run(SSH+['cat > /run/etherpower-soft-blank-test.py'],input=helper,check=True,timeout=20)
 p=subprocess.run(SSH+['python3 -c '+shlex.quote(SOURCE.replace('EXPECTED_STAGE',repr(deployment['stage'])))],capture_output=True,timeout=190)
 if p.returncode:raise RuntimeError(p.stderr.decode(errors='replace')[-7000:])
 d=json.loads(p.stdout);(ROOT/'evidence/etherpower-live-validation.json').write_text(json.dumps(d,indent=2)+'\n',encoding='utf-8')
 for remote,local in [('/run/etherpower-long-press.png','etherpower-long-press.png'),('/home/mobian/.config/ethershell/validation/settings2-screen.png','etherpower-live.png')]:
  image=subprocess.run(SSH+['cat '+remote],capture_output=True,check=True,timeout=20).stdout
  assert image.startswith(b'\x89PNG');(ROOT/'evidence'/local).write_bytes(image)
 print(json.dumps({k:d[k] for k in ['softBlankChecks','brightnessTest','timeoutBlankVerified','serviceOverhead','screenOn']},indent=2))
