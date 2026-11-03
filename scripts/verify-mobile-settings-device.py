"""Verify the deployed normal-user shell and open its integrated Mobile page.

Uses the shell's existing local control endpoint. No cellular/network mutation,
service restart or preference change; only normal UI navigation and diagnostics.
"""
from pathlib import Path
import json
import runpy
import shlex
import subprocess

ROOT=Path(__file__).resolve().parent.parent
SSH=runpy.run_path(str(ROOT/'scripts/deploy-ethermobile.py'))['SSH']
deployment=json.loads((ROOT/'evidence/mobile-settings-deployment.json').read_text())
source=r'''import hashlib,json,os,pathlib,socket,subprocess,time
stage=pathlib.Path(STAGE)
pids=subprocess.check_output(['pgrep','-u','1000','-x','ethershell'],text=True).split();assert len(pids)==1
proc=pathlib.Path('/proc')/pids[0];assert (proc/'exe').resolve()==stage/'usr/bin/ethershell'
env=dict(i.split('=',1) for i in (proc/'environ').read_bytes().decode().split('\0') if '=' in i)
assert env.get('ETHERSHELL_SOFT_BLANK')=='1'
endpoint='/run/user/1000/ethershell-control-experience-'+env['DISPLAY'].replace(':','').replace('.','-')
def request(data):
 with socket.socket(socket.AF_UNIX,socket.SOCK_STREAM) as client:
  client.settimeout(5);client.connect(endpoint);client.sendall(json.dumps(data).encode()+b'\n');return client.recv(64).decode().strip()
def ui():
 assert request({'command':'diagnose'})=='ok';time.sleep(.2)
 return json.loads(pathlib.Path('/home/mobian/.config/ethershell/validation/pocket.json').read_text())['ui']
before=ui()
if not before['homeLocked']:assert request({'command':'home','page':'mobile'})=='ok'
after=ui()
services=['NetworkManager','ModemManager','ssh','bluetooth','etherpocket-modem']
states={s:subprocess.run(['systemctl','is-active',s],capture_output=True,text=True).stdout.strip() for s in services}
devices=subprocess.check_output(['nmcli','-t','-f','DEVICE,TYPE,STATE','device'],text=True)
wm=subprocess.run(['/usr/sbin/runuser','-u','mobian','--','/usr/bin/wmctrl','-m'],env=env,capture_output=True,text=True)
powered=subprocess.run(['busctl','--system','get-property','org.bluez','/org/bluez/hci0','org.bluez.Adapter1','Powered'],capture_output=True,text=True)
result={'stage':str(stage),'uid':proc.stat().st_uid,'binary_sha256':hashlib.sha256((proc/'exe').read_bytes()).hexdigest(),
 'soft_blank':True,'services':states,'wifi_connected':'wlan0:wifi:connected' in devices,'bluetooth_powered':powered.stdout.strip()=='b true',
 'xfwm4_running':'Name: Xfwm4' in wm.stdout,'ui':after,'navigation_verified':not before['homeLocked'] and after['page']=='mobile'}
print(json.dumps(result,indent=2))
assert all(s=='active' for s in states.values()) and result['wifi_connected'] and result['xfwm4_running'] and result['bluetooth_powered']
'''.replace('STAGE',repr(deployment['stage']))
process=subprocess.run(SSH+['python3 -c '+shlex.quote(source)],capture_output=True,timeout=60)
if process.returncode:raise RuntimeError(process.stderr.decode('utf-8',errors='replace'))
result=json.loads(process.stdout)
(ROOT/'evidence/mobile-settings-regression.json').write_text(json.dumps(result,indent=2)+'\n')
print(json.dumps(result,indent=2))
