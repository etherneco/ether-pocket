"""Stage a reviewed, opt-in runtime recovery. This script DOES NOT execute it."""
from pathlib import Path
import json,runpy,shlex,subprocess
ROOT=Path(__file__).resolve().parent.parent
SSH=runpy.run_path(str(ROOT/'scripts/deploy-ethermobile.py'))['SSH']
RECOVERY=r'''#!/usr/bin/python3
"""Explicitly approved runtime recovery only; default invocation is read-only."""
import hashlib,json,pathlib,shutil,subprocess,sys,time
P=pathlib.Path
folder=P('/var/lib/ethershare/radio-recovery')
manifest=json.loads((folder/'manifest.json').read_text())
if '--execute-reviewed-runtime-recovery' not in sys.argv:
 print(json.dumps(manifest,indent=2));sys.exit(0)
assert P('/etc/etherpocket/disk-identity').read_text().strip()=='GM1920-548cb338-mobian-sda21'
assert subprocess.check_output(['uname','-r'],text=True).strip()==manifest['kernel']
assert P('/proc/sys/kernel/random/boot_id').read_text().strip()==manifest['boot_id']
assert P('/var/lib/ethershare/radio-recovery-required').exists()
module=P(manifest['module'])
assert hashlib.sha256(module.read_bytes()).hexdigest()==manifest['module_sha256']
assert '10.77.0.2' in subprocess.check_output(['ip','-4','addr','show','usb0'],text=True)
assert '10.77.0.1' in subprocess.check_output(['ss','-tn','state','established'],text=True)
import dbus
api=dbus.Interface(dbus.SystemBus().get_object('com.etherneco.EtherShare1','/com/etherneco/EtherShare1'),'com.etherneco.EtherShare1')
api.Stop('all',timeout=60)
(folder/'attempt.started').touch(exist_ok=False)
(folder/'attempt.started').chmod(0o600)
report={}
def command(key,args,timeout=25):
 r=subprocess.run(args,capture_output=True,text=True,timeout=timeout)
 report[key]={'exit':r.returncode} # Never log credentials or arbitrary command output.
 (folder/'attempt.json').write_text(json.dumps(report,indent=2))
 if r.returncode:raise RuntimeError(key+' failed; USB recovery remains the recovery path')
 return r
shutil.copy2(module,folder/'wlan.ko.before-recovery')
marker=P('/run/ethermobile-ipa-pipes.json')
if marker.exists():shutil.copy2(marker,folder/'ipa-pipes.before-recovery.json')
was_active=subprocess.run(['systemctl','is-active','ethermobile-data'],capture_output=True).returncode==0
command('stop_existing_data',['systemctl','stop','ethermobile-data'],45)
command('unload_wlan',['/usr/sbin/modprobe','-r','wlan'],20)
command('reload_existing_wlan',['/usr/sbin/modprobe','wlan'],25)
time.sleep(2)
command('restore_saved_wifi',['nmcli','--wait','25','connection','up','uuid',manifest['saved_wifi_uuid'],'ifname','wlan0'],30)
# The kernel reports invalid IPA endpoints following recovery. Invalidate only
# this existing adapter's owned per-boot marker, so its normal owner performs
# the previously reviewed ingress/egress allocation once after the fault.
assert not P('/sys/class/net/epcell0').exists()
if marker.exists():marker.rename(marker.with_name('ethermobile-ipa-pipes.before-ethershare-recovery.json'))
if was_active:
 command('restart_existing_data',['systemctl','start','ethermobile-data'])
 until=time.monotonic()+50
 while time.monotonic()<until:
  p=P('/run/ethermobile-data.json')
  if p.exists() and P('/sys/class/net/epcell0').exists():break
  time.sleep(1)
 command('verify_lte',['curl','-4','--interface','epcell0','--noproxy','*','--fail','--silent','--max-time','8','--output','/dev/null','https://1.1.1.1/cdn-cgi/trace'],12)
command('verify_wifi',['curl','-4','--interface','wlan0','--noproxy','*','--fail','--silent','--max-time','8','--output','/dev/null','https://1.1.1.1/cdn-cgi/trace'],12)
# Do not clear the AP quarantine automatically: source recovery does not certify
# that repeated hotspot cycles are safe on the current driver.
report['complete']=True
(folder/'attempt.json').write_text(json.dumps(report,indent=2))
print(json.dumps(report))
'''
if __name__=='__main__':
    source=r'''
import pathlib,subprocess,json,sys,hashlib
P=pathlib.Path
assert P('/etc/etherpocket/disk-identity').read_text().strip()=='GM1920-548cb338-mobian-sda21'
folder=P('/var/lib/ethershare/radio-recovery');folder.mkdir(mode=0o700,parents=True,exist_ok=True)
module=P(subprocess.check_output(['/usr/sbin/modinfo','-n','wlan'],text=True).strip())
manifest=dict(kernel=subprocess.check_output(['uname','-r'],text=True).strip(),boot_id=P('/proc/sys/kernel/random/boot_id').read_text().strip(),module=str(module),module_sha256=hashlib.sha256(module.read_bytes()).hexdigest(),saved_wifi_uuid='c2e570fc-738f-59c7-898f-78b2ec58388e',actions=['Stop sharing and the existing data session','Reload the exact installed WLAN module','Restore the existing Wi-Fi profile on wlan0','Invalidate only the stale IPA pipe marker and start the existing data owner','Verify both uplinks; retain AP quarantine'],risk='Kernel/firmware recovery may stall; USB SSH is the independently verified recovery channel. No partition flashing or automatic reboot.')
(folder/'manifest.json').write_text(json.dumps(manifest,indent=2));(folder/'manifest.json').chmod(0o600)
p=folder/'recover.py';p.write_bytes(sys.stdin.buffer.read());p.chmod(0o700)
subprocess.run(['python3','-m','py_compile',str(p)],check=True)
print(json.dumps({'script':str(p),'manifest':str(folder/'manifest.json'),'script_sha256':hashlib.sha256(p.read_bytes()).hexdigest(),'executed':False,'plan':manifest}))
'''
    r=subprocess.run(SSH+['python3 -c '+shlex.quote(source)],input=RECOVERY.encode(),capture_output=True,check=True,timeout=25)
    data=json.loads(r.stdout)
    (ROOT/'evidence/ethershare-radio-recovery-plan.json').write_text(json.dumps(data,indent=2)+'\n',encoding='utf-8')
    (ROOT/'build/ethershare-radio-recovery.py').write_text(RECOVERY,encoding='utf-8',newline='\n')
    print(json.dumps({k:v for k,v in data.items() if k!='plan'},indent=2))
