"""Final read-only release checks; never reconfigure radios or boot the phone."""
from pathlib import Path
import hashlib
import json
import runpy
import shlex
import subprocess

ROOT = Path(__file__).resolve().parent.parent
SSH = runpy.run_path(str(ROOT / 'scripts/deploy-ethermobile.py'))['SSH']
SOURCE = r'''
import json,pathlib,subprocess
def call(args):
 p=subprocess.run(args,capture_output=True,text=True,timeout=25)
 return {'code':p.returncode,'stdout':p.stdout.strip(),'stderr':p.stderr.strip()}
units=['etherpower','etherhardware','NetworkManager','ModemManager','bluetooth','ssh','ethershare','ethermobile-data','etherpocket-modem','etherpocket-usb-debug','etherpocket-usb-storage']
services={u:call(['systemctl','is-active',u])['stdout'] for u in units}
wifi=call(['curl','--interface','wlan0','--max-time','15','--silent','--show-error','--output','/dev/null','--write-out','%{http_code}','https://deb.debian.org/debian/README'])
state=json.loads(subprocess.check_output(['etherpower','state'],text=True))
assert wifi['code']==0 and wifi['stdout']=='200',wifi
assert services['etherpower']=='active' and services['etherhardware']=='active'
assert state['profileState']['effective']=='balanced'
assert state['sessionDisplay']['uid']==1000
print(json.dumps({'bootId':pathlib.Path('/proc/sys/kernel/random/boot_id').read_text().strip(),'services':services,'wifiBoundHttps':wifi,'forwarding':pathlib.Path('/proc/sys/net/ipv4/ip_forward').read_text().strip(),'shellProcesses':call(['ps','-C','ethershell','-o','pid=,uid=,args=']),'bluetooth':call(['bluetoothctl','show']),'profile':state['profileState'],'sessionDisplay':state['sessionDisplay'],'fullRebootTest':'not performed; requires manual boot-menu selection by user'},indent=2))
'''
if __name__ == '__main__':
    p = subprocess.run(SSH + ['python3 -c ' + shlex.quote(SOURCE)], capture_output=True, check=True, timeout=75)
    result = json.loads(p.stdout)
    reboot_after=ROOT/'evidence/etherpower-reboot-after.json'
    reboot_checks=ROOT/'evidence/etherpower-reboot-comparison.json'
    if reboot_after.exists() and reboot_checks.exists():
        after=json.loads(reboot_after.read_text())
        checks=json.loads(reboot_checks.read_text())
        if result['bootId']==after['bootId'] and all(checks.values()):
            result['fullRebootTest']='passed; new boot verified after user-selected etherPocket, persistent configuration and active services restored'
    result['packages'] = {name: hashlib.sha256((ROOT/'build'/name).read_bytes()).hexdigest() for name in ['etherpower_0.1.0_arm64.deb','ethershell-power_2.1.0_arm64.deb']}
    (ROOT/'evidence/etherpower-regression.json').write_text(json.dumps(result,indent=2)+'\n',encoding='utf-8')
    print(json.dumps(result,indent=2))
