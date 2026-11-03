"""Read-only release and periodic-refresh checks. Never opens audio PCMs."""
from pathlib import Path
import hashlib,json,runpy,shlex,subprocess
ROOT=Path(__file__).resolve().parent.parent
SSH=runpy.run_path(str(ROOT/'scripts/deploy-ethermobile.py'))['SSH']
SOURCE=r'''
import hashlib,json,pathlib,subprocess,time
user=['runuser','-u','mobian','--','env','XDG_RUNTIME_DIR=/run/user/1000','DBUS_SESSION_BUS_ADDRESS=unix:path=/run/user/1000/bus']
def run(args):return subprocess.check_output(args,text=True,timeout=12).strip()
def state():return json.loads(run(user+['etheraudio','state']))
samples=[]
for delay in [0,35,35]:
 if delay:time.sleep(delay)
 s=state();assert s['ready'];samples.append({'sampledAt':time.time(),'timestamp':s['timestamp'],'pid':run(user+['systemctl','--user','show','etheraudio','-p','MainPID','--value'])})
assert len({r['pid'] for r in samples})==1 and samples[-1]['timestamp']>samples[0]['timestamp'],samples
units=['NetworkManager','ssh','bluetooth','etherpower','etherhardware','etherpocket-modem','ModemManager','ethershare','ethermobile-data','etherpocket-usb-debug','etherpocket-usb-storage']
services={u:subprocess.run(['systemctl','is-active',u],capture_output=True,text=True).stdout.strip() for u in units}
wifi=subprocess.run(['curl','--interface','wlan0','--max-time','15','--silent','--show-error','--output','/dev/null','--write-out','%{http_code}','https://deb.debian.org/debian/README'],capture_output=True,text=True,timeout=20)
assert wifi.returncode==0 and wifi.stdout=='200'
source_hashes={f:hashlib.sha256((pathlib.Path('/usr/share/etheraudio')/f).read_bytes()).hexdigest() for f in ['core.py','service.py','cli.py','tests/test_audio.py']}
power=json.loads(run(['etherpower','state']));assert power['profileState']['effective']=='balanced'
shell=run(['pgrep','-u','1000','-x','ethershell']).split();assert len(shell)==1
print(json.dumps({'periodicRefresh':samples,'state':s,'sourceHashes':source_hashes,'bootId':run(['cat','/proc/sys/kernel/random/boot_id']),
 'services':services,'wifiBoundHttps':wifi.stdout,'audioServers':{u:run(user+['systemctl','--user','show',u,'-p','MainPID','--value']) for u in ['pipewire','pipewire-pulse','wireplumber']},
 'enabled':run(user+['systemctl','--user','is-enabled','etheraudio']),
 'nRestarts':run(user+['systemctl','--user','show','etheraudio','-p','NRestarts','--value']),
 'shellExecutable':str((pathlib.Path('/proc')/shell[0]/'exe').resolve()),'powerProfile':power['profileState'],
 'microphoneCapturedDuringAcceptance':False,'physicalSuspendAttempted':False,'newServiceRebootVerified':False},indent=2))
'''
if __name__=='__main__':
    p=subprocess.run(SSH+['python3 -c '+shlex.quote(SOURCE)],capture_output=True,timeout=120)
    if p.returncode:raise RuntimeError(p.stderr.decode(errors='replace')[-6000:])
    data=json.loads(p.stdout)
    data['sourceMatchesInstalled']={f:hashlib.sha256((ROOT/'etheraudio'/f).read_bytes()).hexdigest()==digest for f,digest in data['sourceHashes'].items()}
    original=json.loads((ROOT/'evidence/etheraudio-install.json').read_text())['before']
    data['existingServicesPreserved']=data['services']==original['services']
    data['existingAudioServersPreserved']=data['audioServers']==original['audioPids']
    data['packages']={name:hashlib.sha256((ROOT/'build'/name).read_bytes()).hexdigest() for name in ['etheraudio_0.1.0_arm64.deb','ethershell-audio_2.1.0_arm64.deb','ethersms-audio_0.1.0_arm64.deb','etherbluetooth-audio_0.1.0_arm64.deb','etherhardware_0.1.0_arm64.deb']}
    assert all(data['sourceMatchesInstalled'].values()) and data['existingServicesPreserved'] and data['existingAudioServersPreserved']
    (ROOT/'evidence/etheraudio-final-regression.json').write_text(json.dumps(data,indent=2)+'\n',encoding='utf-8')
    print(json.dumps({k:data[k] for k in ['periodicRefresh','sourceMatchesInstalled','enabled','nRestarts','existingServicesPreserved','existingAudioServersPreserved','wifiBoundHttps','shellExecutable']},indent=2))
