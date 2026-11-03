"""Verify the active user shell, read-only capability queries and existing services."""
from pathlib import Path
import json
import runpy
import shlex
import subprocess
ROOT = Path(__file__).resolve().parent.parent
SSH = runpy.run_path(str(ROOT / 'scripts/deploy-ethermobile.py'))['SSH']

if __name__ == '__main__':
    deployment = json.loads((ROOT / 'evidence/etherhardware-shell-deployment.json').read_text())
    source = r'''
import hashlib,json,pathlib,socket,subprocess,time
stage=pathlib.Path(STAGE)
pids=subprocess.check_output(['pgrep','-u','1000','-x','ethershell'],text=True).split();assert len(pids)==1
proc=pathlib.Path('/proc')/pids[0];assert (proc/'exe').resolve()==stage/'usr/bin/ethershell'
assert proc.stat().st_uid==1000
env=dict(x.split('=',1) for x in (proc/'environ').read_bytes().decode().split('\0') if '=' in x)
assert env.get('ETHERSHELL_SOFT_BLANK')=='1'
endpoint='/run/user/1000/ethershell-control-experience-'+env['DISPLAY'].replace(':','').replace('.','-')
def request(data):
 with socket.socket(socket.AF_UNIX,socket.SOCK_STREAM) as s:
  s.settimeout(10);s.connect(endpoint);s.sendall(json.dumps(data).encode()+b'\n');return s.recv(8192).decode().strip()
for route in ['system','hardware']:
 assert request({'command':'settings-page','route':route})=='ok';time.sleep(1)
 assert json.loads(request({'command':'settings-state'}))['route']==route
assert request({'command':'settings-screenshot'})=='ok'
services=['NetworkManager','ModemManager','bluetooth','ssh','ethershare','etherpocket-modem','ethermobile-data','etherhardware','etherpocket-usb-debug','etherpocket-usb-storage']
states={s:subprocess.run(['systemctl','is-active',s],capture_output=True,text=True).stdout.strip() for s in services}
assert all(v=='active' for k,v in states.items() if k!='ethermobile-data')
assert states['ethermobile-data']=='failed' # Pre-existing failure stays accurately reported.
caps=json.loads(subprocess.check_output(['runuser','-u','mobian','--','etherhardware','capabilities'],text=True))
caps={c['id']:c for c in caps['capabilities']}
assert caps['wifi.client']['operational'] and caps['bluetooth.adapter']['operational']
assert caps['wifi.ap']['operational'] is False and caps['cellular.data']['operational'] is False
wifi=subprocess.run(['curl','--interface','wlan0','--max-time','15','--silent','--output','/dev/null','--write-out','%{http_code}','https://deb.debian.org/debian/README'],capture_output=True,text=True)
assert wifi.returncode==0 and wifi.stdout=='200'
print(json.dumps({'stage':str(stage),'uid':proc.stat().st_uid,'binarySha256':hashlib.sha256((proc/'exe').read_bytes()).hexdigest(),
 'softBlank':True,'settings':json.loads(request({'command':'settings-state'})),'services':states,
 'wifiBoundHttps':{'exit':wifi.returncode,'http':wifi.stdout},'capabilities':list(caps.values()),
 'ipv4Forwarding':pathlib.Path('/proc/sys/net/ipv4/ip_forward').read_text().strip(),
 'bootId':pathlib.Path('/proc/sys/kernel/random/boot_id').read_text().strip()},indent=2))
'''.replace('STAGE', repr(deployment['stage']))
    p = subprocess.run(SSH + ['python3 -c ' + shlex.quote(source)], capture_output=True, timeout=60)
    if p.returncode:
        raise RuntimeError(p.stderr.decode(errors='replace')[-5000:])
    data = json.loads(p.stdout)
    (ROOT / 'evidence/etherhardware-shell-regression.json').write_text(json.dumps(data, indent=2) + '\n', encoding='utf-8')
    capture = subprocess.run(SSH + ['cat /home/mobian/.config/ethershell/validation/settings2-screen.png'], capture_output=True, check=True, timeout=20).stdout
    assert capture.startswith(b'\x89PNG')
    (ROOT / 'evidence/etherhardware-live.png').write_bytes(capture)
    print(json.dumps({k: data[k] for k in ('stage', 'uid', 'wifiBoundHttps', 'services')}, indent=2))
