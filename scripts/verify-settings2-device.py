"""Verify the active Settings stage, capture live UI and test temporary XI2 touch.

No network, modem or persistent device settings are changed. The transient input
device is destroyed on exit; shell navigation is left on Settings home.
"""
from pathlib import Path
import json
import runpy
import shlex
import subprocess

ROOT = Path(__file__).resolve().parent.parent
SSH = runpy.run_path(str(ROOT / 'scripts/deploy-ethermobile.py'))['SSH']
deployment = json.loads((ROOT / 'evidence/settings2-deployment.json').read_text())

source = r'''import hashlib,json,pathlib,socket,subprocess,time
from evdev import AbsInfo,UInput,ecodes as e
stage=pathlib.Path(STAGE)
pids=subprocess.check_output(['pgrep','-u','1000','-x','ethershell'],text=True).split();assert len(pids)==1
proc=pathlib.Path('/proc')/pids[0];assert (proc/'exe').resolve()==stage/'usr/bin/ethershell'
env=dict(i.split('=',1) for i in (proc/'environ').read_bytes().decode().split('\0') if '=' in i)
assert env.get('ETHERSHELL_SOFT_BLANK')=='1'
endpoint='/run/user/1000/ethershell-control-experience-'+env['DISPLAY'].replace(':','').replace('.','-')
def request(data):
 with socket.socket(socket.AF_UNIX,socket.SOCK_STREAM) as client:
  client.settimeout(10);client.connect(endpoint);client.sendall(json.dumps(data).encode()+b'\n')
  return client.recv(8192).decode().strip()
def state():return json.loads(request({'command':'settings-state'}))
assert request({'command':'diagnose'})=='ok'
ui=json.loads(pathlib.Path('/home/mobian/.config/ethershell/validation/pocket.json').read_text())['ui']
assert not ui['homeLocked'],'Unlock the existing session before UI verification'
for route in ['home','network','wifi','appearance','input']:
 assert request({'command':'settings-page','route':route})=='ok';time.sleep(1.2)
 assert state()['route']==route
 assert request({'command':'settings-screenshot'})=='ok'
 folder=pathlib.Path('/home/mobian/.config/ethershell/validation')
 (folder/('settings2-live-'+route+'.png')).write_bytes((folder/'settings2-screen.png').read_bytes())
assert request({'command':'home','page':'mobile'})=='ok';time.sleep(1.5)
assert state()['page']=='mobile';assert request({'command':'settings-screenshot'})=='ok'
(folder/'settings2-live-mobile.png').write_bytes((folder/'settings2-screen.png').read_bytes())
assert request({'command':'settings-page','route':'home'})=='ok';time.sleep(.8)
before=state();width,height=before['width'],before['height']
caps={e.EV_KEY:[e.BTN_TOUCH],e.EV_ABS:[
 (e.ABS_X,AbsInfo(0,0,width-1,0,0,0)),(e.ABS_Y,AbsInfo(0,0,height-1,0,0,0)),
 (e.ABS_MT_SLOT,AbsInfo(0,0,9,0,0,0)),(e.ABS_MT_TRACKING_ID,AbsInfo(0,0,65535,0,0,0)),
 (e.ABS_MT_POSITION_X,AbsInfo(0,0,width-1,0,0,0)),(e.ABS_MT_POSITION_Y,AbsInfo(0,0,height-1,0,0,0))]}
with UInput(caps,name='EtherShell Settings validation touch',input_props=[e.INPUT_PROP_DIRECT]) as touch:
 time.sleep(2)
 touch.write(e.EV_KEY,e.BTN_TOUCH,1);touch.write(e.EV_ABS,e.ABS_MT_SLOT,0);touch.write(e.EV_ABS,e.ABS_MT_TRACKING_ID,1)
 for n in range(41):
  x=int(width*.5);y=int(height*(.76-n*.010))
  for code,value in [(e.ABS_X,x),(e.ABS_Y,y),(e.ABS_MT_POSITION_X,x),(e.ABS_MT_POSITION_Y,y)]:touch.write(e.EV_ABS,code,value)
  touch.syn();time.sleep(.02)
 touch.write(e.EV_ABS,e.ABS_MT_TRACKING_ID,-1);touch.write(e.EV_KEY,e.BTN_TOUCH,0);touch.syn();time.sleep(1.5)
 after=state()
 assert request({'command':'settings-page','route':'input'})=='ok';time.sleep(1)
 touch.write(e.EV_KEY,e.BTN_TOUCH,1);touch.write(e.EV_ABS,e.ABS_MT_SLOT,0);touch.write(e.EV_ABS,e.ABS_MT_TRACKING_ID,2)
 for code,value in [(e.ABS_X,width//2),(e.ABS_Y,int(height*.513)),(e.ABS_MT_POSITION_X,width//2),(e.ABS_MT_POSITION_Y,int(height*.513))]:touch.write(e.EV_ABS,code,value)
 touch.syn();time.sleep(.12)
 touch.write(e.EV_ABS,e.ABS_MT_TRACKING_ID,-1);touch.write(e.EV_KEY,e.BTN_TOUCH,0);touch.syn();time.sleep(1.5)
 keyboard=state()
 assert request({'command':'settings-screenshot'})=='ok'
 (folder/'settings2-live-keyboard.png').write_bytes((folder/'settings2-screen.png').read_bytes())
 assert request({'command':'keyboard','visible':False})=='ok'
 assert request({'command':'settings-page','route':'home'})=='ok'
services={s:subprocess.run(['systemctl','is-active',s],capture_output=True,text=True).stdout.strip() for s in ['NetworkManager','ModemManager','ssh','bluetooth','etherpocket-modem']}
devices=subprocess.check_output(['nmcli','-t','-f','DEVICE,TYPE,STATE','device'],text=True)
wm=subprocess.run(['/usr/sbin/runuser','-u','mobian','--','/usr/bin/wmctrl','-m'],env=env,capture_output=True,text=True)
powered=subprocess.run(['busctl','--system','get-property','org.bluez','/org/bluez/hci0','org.bluez.Adapter1','Powered'],capture_output=True,text=True)
result={'stage':str(stage),'uid':proc.stat().st_uid,'binary_sha256':hashlib.sha256((proc/'exe').read_bytes()).hexdigest(),'soft_blank':True,
 'services':services,'wifi_connected':'wlan0:wifi:connected' in devices,'bluetooth_powered':powered.stdout.strip()=='b true','xfwm4_running':'Name: Xfwm4' in wm.stdout,
 'touch_kind':'temporary synthetic XI2 touchscreen','touch_before':before,'touch_after':after,'keyboard_touch_state':keyboard,'keyboard_touch_opened':keyboard['keyboard'],
 'touch_scrolled':after.get('scrollY',0)>before.get('scrollY',0)+30 and after.get('route')=='home' and after['page']=='settings'}
print(json.dumps(result,indent=2))
assert all(s=='active' for s in services.values()) and result['wifi_connected'] and result['bluetooth_powered'] and result['xfwm4_running'] and result['touch_scrolled'] and result['keyboard_touch_opened']
'''.replace('STAGE', repr(deployment['stage']))
process = subprocess.run(SSH + ['python3 -c ' + shlex.quote(source)], capture_output=True, timeout=90)
if process.stdout:
    result = json.loads(process.stdout)
    (ROOT / 'evidence/settings2-regression.json').write_text(json.dumps(result, indent=2) + '\n')
    print(json.dumps(result, indent=2))
if process.returncode:
    raise RuntimeError(process.stderr.decode('utf-8', errors='replace'))
for route in ['home', 'network', 'wifi', 'appearance', 'input', 'mobile', 'keyboard']:
    name = 'settings2-live-' + route + '.png'
    image = subprocess.run(SSH + ['cat /home/mobian/.config/ethershell/validation/' + name], capture_output=True, check=True, timeout=30).stdout
    assert image.startswith(b'\x89PNG')
    (ROOT / 'evidence' / name).write_bytes(image)
