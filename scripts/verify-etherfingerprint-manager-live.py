"""Verify live navigation and diagnostic-service recovery; never starts biometrics."""
import json
from pathlib import Path
import runpy
import shlex
import subprocess

ROOT=Path(__file__).resolve().parents[1]
SSH=runpy.run_path(str(ROOT/'scripts/deploy-ethermobile.py'))['SSH']
SOURCE=r'''
import json,pathlib,socket,subprocess,time
P=pathlib.Path
assert P('/etc/etherpocket/disk-identity').read_text().strip()=='GM1920-548cb338-mobian-sda21'
pids=subprocess.check_output(['pgrep','-u','1000','-x','ethershell'],text=True).split();assert len(pids)==1
proc=P('/proc')/pids[0]
env=dict(x.split('=',1) for x in (proc/'environ').read_bytes().decode().split('\0') if '=' in x)
endpoint='/run/user/1000/ethershell-control-experience-'+env['DISPLAY'].replace(':','').replace('.','-')
def request(data):
 with socket.socket(socket.AF_UNIX) as s:
  s.settimeout(10);s.connect(endpoint);s.sendall(json.dumps(data).encode()+b'\n');return s.recv(32768).decode().strip()
def capture(name):
 assert request({'command':'settings-screenshot'})=='ok'
 folder=P('/home/mobian/.config/ethershell/validation')
 target=folder/('fingerprint-manager-'+name+'.png')
 target.write_bytes((folder/'settings2-screen.png').read_bytes())
 return str(target)
assert request({'command':'settings-page','route':'fingerprints'})=='ok';time.sleep(1)
assert json.loads(request({'command':'settings-state'}))['route']=='fingerprints'
assert request({'command':'diagnose'})=='ok'
ui=json.loads(P('/home/mobian/.config/ethershell/validation/pocket.json').read_text())['ui']
assert not ui['homeLocked'],'Existing lock is active; no bypass attempted'
out={'before':capture('live')}
try:
 subprocess.run(['systemctl','stop','etherfingerprintd'],check=True,timeout=20);time.sleep(1)
 out['serviceUnavailable']=capture('service-unavailable')
finally:
 subprocess.run(['systemctl','start','etherfingerprintd'],check=True,timeout=20)
time.sleep(1)
out['recovered']=capture('recovered')
assert request({'command':'settings-page','route':'security'})=='ok'
assert json.loads(request({'command':'settings-state'}))['route']=='security'
assert request({'command':'settings-page','route':'fingerprints'})=='ok'
out['sameShellPid']=proc.exists()
out['backend']=json.loads(subprocess.check_output(['/usr/bin/etherfingerprint'],text=True))
assert out['backend']['canVerify'] is False and out['backend']['enrolledCount'] is None
print(json.dumps(out,indent=2))
'''
if __name__=='__main__':
    p=subprocess.run(SSH+['python3 -c '+shlex.quote(SOURCE)],capture_output=True,timeout=90)
    if p.returncode:raise SystemExit(p.stderr.decode(errors='replace'))
    result=json.loads(p.stdout)
    for key in ['before','serviceUnavailable','recovered']:
        image=subprocess.run(SSH+['cat '+shlex.quote(result[key])],capture_output=True,check=True,timeout=20).stdout
        target=ROOT/'evidence'/('etherfingerprint-manager-'+key+'.png')
        target.write_bytes(image)
    (ROOT/'evidence/etherfingerprint-manager-live.json').write_text(json.dumps(result,indent=2)+'\n')
    print('Live navigation and diagnostic service recovery completed')
