"""Guarded EtherPower installation and saved-policy restart verification.
Never starts radio, audio, camera, sharing, suspend or shutdown operations.
"""
from pathlib import Path
import hashlib
import json
import runpy
import shlex
import subprocess

ROOT = Path(__file__).resolve().parent.parent
SSH = runpy.run_path(str(ROOT / 'scripts/deploy-ethermobile.py'))['SSH']

if __name__ == '__main__':
    payload = (ROOT / 'build/etherpower_0.1.0_arm64.deb').read_bytes()
    source = r'''
import hashlib,json,pathlib,platform,subprocess,sys,tempfile,time
assert platform.machine()=='aarch64'
assert pathlib.Path('/etc/etherpocket/disk-identity').read_text().strip()=='GM1920-548cb338-mobian-sda21'
payload=sys.stdin.buffer.read();assert hashlib.sha256(payload).hexdigest()==DIGEST
services=['NetworkManager','ModemManager','bluetooth','ssh','ethershare','etherpocket-modem','ethermobile-data','etherpocket-usb-debug','etherpocket-usb-storage']
def probe():
 return {'services':{s:subprocess.run(['systemctl','is-active',s],capture_output=True,text=True).stdout.strip() for s in services},
 'wifi':subprocess.check_output(['nmcli','-t','-f','DEVICE,TYPE,STATE','device'],text=True),
 'forwarding':pathlib.Path('/proc/sys/net/ipv4/ip_forward').read_text().strip(),
 'bootId':pathlib.Path('/proc/sys/kernel/random/boot_id').read_text().strip()}
before=probe()
with tempfile.TemporaryDirectory(dir='/var/tmp') as folder:
 p=pathlib.Path(folder)/'power.deb';p.write_bytes(payload)
 subprocess.run(['dpkg','--dry-run','-i',str(p)],check=True,stdout=sys.stderr)
 subprocess.run(['dpkg','-i',str(p)],check=True,stdout=sys.stderr)
def state():
 p=subprocess.run(['runuser','-u','mobian','--','etherpower','state'],capture_output=True,text=True,check=True)
 return json.loads(p.stdout)
for _ in range(40):
 data=state()
 if data.get('ready') and not data.get('busy'):break
 time.sleep(.5)
assert data.get('ready') and data['controls']
assert data['capacity'] is not None and data['voltageV'] > 3
assert not data['suspend']['verified']
test=subprocess.run(['runuser','-u','mobian','--','python3','-m','unittest','discover','-s','/usr/share/etherpower/tests','-v'],capture_output=True,text=True)
assert test.returncode==0,test.stderr
reports={}
report=subprocess.check_output(['runuser','-u','mobian','--','etherpower','report'],text=True)
assert json.loads(report)['state']['ready']
reports={'json':{'bytes':len(report)}}
subprocess.run(['systemctl','restart','etherpower'],check=True)
for _ in range(40):
 restarted=state()
 if restarted.get('ready') and not restarted.get('busy'):break
 time.sleep(.5)
assert restarted['ready']
after=probe();assert before==after,(before,after)
unit=subprocess.check_output(['systemctl','show','etherpower','-p','MainPID','-p','User','-p','MemoryCurrent','-p','CPUUsageNSec'],text=True)
pid=int(next(x.split('=')[1] for x in unit.splitlines() if x.startswith('MainPID=')))
assert (pathlib.Path('/proc')/str(pid)).stat().st_uid==0
print(json.dumps({'packageSha256':DIGEST,'before':before,'after':after,'inventory':restarted,
 'tests':test.stderr,'reports':reports,'service':unit},indent=2))
'''.replace('DIGEST', repr(hashlib.sha256(payload).hexdigest()))
    result = subprocess.run(SSH + ['python3 -c ' + shlex.quote(source)], input=payload,
                            capture_output=True, timeout=100)
    if result.returncode:
        raise RuntimeError(result.stderr.decode(errors='replace')[-9000:])
    data = json.loads(result.stdout)
    (ROOT / 'evidence/etherpower-device.json').write_text(json.dumps(data, indent=2) + '\n', encoding='utf-8')
    print(json.dumps({k: data[k] for k in ('packageSha256', 'service', 'reports')}, indent=2))
