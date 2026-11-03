"""User-authorized reboot with persistent-state and new-boot acceptance."""
from pathlib import Path
import argparse
import json
import runpy
import shlex
import subprocess

ROOT=Path(__file__).resolve().parent.parent
SSH=runpy.run_path(str(ROOT/'scripts/deploy-ethermobile.py'))['SSH']
SOURCE=r'''
import hashlib,json,pathlib,subprocess
P=pathlib.Path
assert P('/etc/etherpocket/disk-identity').read_text().strip()=='GM1920-548cb338-mobian-sda21'
def sha(path):return hashlib.sha256(P(path).read_bytes()).hexdigest()
def run(args):
 p=subprocess.run(args,capture_output=True,text=True,timeout=25)
 return {'code':p.returncode,'out':p.stdout.strip(),'error':p.stderr.strip()}
state=json.loads(subprocess.check_output(['etherpower','state'],text=True))
config=json.loads(P('/var/lib/etherpower/config.json').read_text())
prefs=json.loads(P('/home/mobian/.config/ethershell/preferences.json').read_text())
stage=STAGE
print(json.dumps({'bootId':P('/proc/sys/kernel/random/boot_id').read_text().strip(),
 'config':config,'originalControlsHash':sha('/var/lib/etherpower/original-controls.json'),
 'powerPreferences':{k:v for k,v in prefs.items() if k.startswith('power')},
 'launcherHash':sha('/home/mobian/.local/bin/ethershell2-start'),
 'binaryHash':sha(stage+'/usr/bin/ethershell'),'state':state,
 'enabled':run(['systemctl','is-enabled','etherpower']),
 'inhibitors':run(['systemd-inhibit','--list','--no-pager']),
 'services':{u:run(['systemctl','is-active',u])['out'] for u in ['etherpower','etherhardware','NetworkManager','ModemManager','bluetooth','ssh','ethershare','ethermobile-data','etherpocket-modem','etherpocket-usb-debug','etherpocket-usb-storage']},
 'shell':run(['ps','-C','ethershell','-o','pid=,uid=,args=']),
 'wifiHttps':run(['curl','--interface','wlan0','--max-time','15','--silent','--show-error','--output','/dev/null','--write-out','%{http_code}','https://deb.debian.org/debian/README'])},indent=2))
'''
if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action',choices=['before','reboot','after'])
    action=parser.parse_args().action
    before_path=ROOT/'evidence/etherpower-reboot-before.json'
    if action=='reboot':
        before=json.loads(before_path.read_text())
        assert before['enabled']['out']=='enabled'
        assert before['state']['profileState']['effective']=='balanced'
        p=subprocess.run(SSH+['etherpower action restart'],capture_output=True,timeout=35)
        print(json.dumps({'exit':p.returncode,'stdout':p.stdout.decode(errors='replace'),'stderr':p.stderr.decode(errors='replace')}))
        # Windows OpenSSH also reports unsigned -1 when reboot closes the peer.
        assert p.returncode in (0,255,4294967295,-1)
    else:
        stage=json.loads((ROOT/'evidence/etherpower-shell-deployment.json').read_text())['stage']
        p=subprocess.run(SSH+['python3 -c '+shlex.quote(SOURCE.replace('STAGE',repr(stage)))],capture_output=True,timeout=60)
        if p.returncode:raise RuntimeError(p.stderr.decode(errors='replace'))
        data=json.loads(p.stdout)
        (ROOT/('evidence/etherpower-reboot-'+action+'.json')).write_text(json.dumps(data,indent=2)+'\n',encoding='utf-8')
        if action=='after':
            before=json.loads(before_path.read_text())
            checks={k:before[k]==data[k] for k in ['config','originalControlsHash','powerPreferences','launcherHash','binaryHash']}
            checks.update(newBoot=before['bootId']!=data['bootId'],enabled=data['enabled']['out']=='enabled',balanced=data['state']['profileState']['effective']=='balanced',wifiHttps=data['wifiHttps']['out']=='200',shellUser='1000 ethershell' in data['shell']['out'],previouslyActiveServicesRestored=all(data['services'][u]=='active' for u,v in before['services'].items() if v=='active'),displayReported=data['state'].get('sessionDisplay',{}).get('uid')==1000)
            differences={u:{'before':v,'after':data['services'][u]} for u,v in before['services'].items() if v!=data['services'][u]}
            (ROOT/'evidence/etherpower-reboot-service-transitions.json').write_text(json.dumps(differences,indent=2)+'\n',encoding='utf-8')
            (ROOT/'evidence/etherpower-reboot-comparison.json').write_text(json.dumps(checks,indent=2)+'\n',encoding='utf-8')
            print(json.dumps(checks,indent=2));assert all(checks.values())
        else:print(json.dumps({k:data[k] for k in ['bootId','enabled','services','shell','wifiHttps','inhibitors']},indent=2))
