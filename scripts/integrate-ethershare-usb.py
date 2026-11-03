"""Board-specific DHCP migration. Verified alternate SSH and timed rollback.

Never unbinds USB. Preserves the original debug initializer and address setup.
The override replaces only its final DHCP exec with reloadable dnsmasq.
"""
from pathlib import Path
import json, runpy, shlex, subprocess
ROOT=Path(__file__).resolve().parent.parent
SSH=runpy.run_path(str(ROOT/'scripts/deploy-ethermobile.py'))['SSH']
WIFI=SSH[:-1]+['-o','HostKeyAlias=10.77.0.2','root@10.1.30.136']

def remote(args,source,timeout=35):
    r=subprocess.run(args+['python3 -c '+shlex.quote(source)],capture_output=True,text=True,timeout=timeout)
    if r.returncode:raise RuntimeError(r.stderr[-5000:])
    return r.stdout

if __name__=='__main__':
    assert remote(WIFI,"import pathlib;assert pathlib.Path('/etc/etherpocket/disk-identity').read_text().strip()=='GM1920-548cb338-mobian-sda21';print('verified')").strip()=='verified'
    source=r"""
import hashlib,json,os,pathlib,subprocess
P=pathlib.Path
g=P('/sys/kernel/config/usb_gadget/etherpocket')
assert (g/'configs/c.1/rndis.usb0').is_symlink() and (g/'configs/c.1/mass_storage.usb0').is_symlink()
assert subprocess.run(['systemctl','is-active','ethershare'],capture_output=True).returncode==0
folder=P('/var/lib/ethershare/usb-migration');folder.mkdir(parents=True,exist_ok=True,mode=0o700)
original=P('/usr/local/sbin/etherpocket-usb-debug').read_bytes()
assert b'exec /bin/busybox udhcpd -f /run/etherpocket-udhcpd.conf' in original
backup=folder/'original-debug';
if not backup.exists():backup.write_bytes(original)
assert backup.read_bytes()==original
drop=P('/etc/systemd/system/etherpocket-usb-debug.service.d/50-ethershare.conf')
assert not drop.exists(), 'Migration already installed; do not restart recovery unnecessarily'
state={'UDC':(g/'UDC').read_text().strip(),'product':(g/'idProduct').read_text().strip(),'links':sorted(p.name for p in (g/'configs/c.1').iterdir() if p.is_symlink()),'original_sha256':hashlib.sha256(original).hexdigest()}
(folder/'before.json').write_text(json.dumps(state,indent=2))
rollback='''import pathlib,subprocess
p=pathlib.Path('/etc/systemd/system/etherpocket-usb-debug.service.d/50-ethershare.conf')
if p.exists():p.unlink()
subprocess.run(['systemctl','daemon-reload'])
subprocess.run(['systemctl','restart','etherpocket-usb-debug'])
subprocess.run(['systemctl','start','etherpocket-usb-storage'])
'''
(folder/'rollback.py').write_text(rollback)
subprocess.run(['systemd-run','--unit=ethershare-usb-rollback','--on-active=90s','/usr/bin/python3',str(folder/'rollback.py')],check=True,capture_output=True)
runtime=P('/run/ethershare');runtime.mkdir(exist_ok=True,mode=0o700)
(runtime/'usb.options').write_text('option:router\noption:dns-server\n')
(runtime/'usb.servers').write_text('')
config='''user=root
bind-dynamic
interface=usb0
listen-address=10.77.0.2
except-interface=lo
no-resolv
domain-needed
bogus-priv
dhcp-range=10.77.0.1,10.77.0.1,255.255.255.0,1h
dhcp-leasefile=/run/etherpocket-dnsmasq.leases
pid-file=/run/etherpocket-dnsmasq.pid
dhcp-optsfile=/run/ethershare/usb.options
servers-file=/run/ethershare/usb.servers
'''
(folder/'dnsmasq.conf').write_text(config)
subprocess.run(['/usr/sbin/dnsmasq','--test','--conf-file='+str(folder/'dnsmasq.conf')],check=True,capture_output=True)
replacement=b'exec /usr/sbin/dnsmasq --keep-in-foreground --conf-file=/var/lib/ethershare/usb-migration/dnsmasq.conf'
script=original.replace(b'exec /bin/busybox udhcpd -f /run/etherpocket-udhcpd.conf',replacement)
# Runtime option files are recreated without enabling routing on boot.
script=script.replace(replacement,b'mkdir -p /run/ethershare\n[ -f /run/ethershare/usb.options ] || printf "option:router\\noption:dns-server\\n" > /run/ethershare/usb.options\n[ -f /run/ethershare/usb.servers ] || touch /run/ethershare/usb.servers\n'+replacement)
(folder/'usb-debug-with-dnsmasq').write_bytes(script);(folder/'usb-debug-with-dnsmasq').chmod(0o700)
drop.parent.mkdir(exist_ok=True)
drop.write_text('[Service]\nExecStart=\nExecStart=/var/lib/ethershare/usb-migration/usb-debug-with-dnsmasq\n')
subprocess.run(['systemctl','daemon-reload'],check=True)
subprocess.run(['systemctl','restart','etherpocket-usb-debug'],check=True)
subprocess.run(['systemctl','start','etherpocket-usb-storage'],check=True)
print(json.dumps(state))
"""
    before=json.loads(remote(WIFI,source))
    verify=r'''
import json,pathlib,subprocess
p=pathlib.Path;g=p('/sys/kernel/config/usb_gadget/etherpocket')
assert (g/'UDC').read_text().strip()==BEFORE['UDC']
assert (g/'idProduct').read_text().strip()==BEFORE['product']
assert sorted(x.name for x in (g/'configs/c.1').iterdir() if x.is_symlink())==BEFORE['links']
pid=int(p('/run/etherpocket-dnsmasq.pid').read_text());assert p('/proc',str(pid),'comm').read_text().strip()=='dnsmasq'
services=subprocess.check_output(['systemctl','is-active','etherpocket-usb-debug','etherpocket-usb-storage','ssh','NetworkManager'],text=True).splitlines()
assert all(x=='active' for x in services)
assert '10.77.0.2/24' in subprocess.check_output(['ip','-4','addr','show','usb0'],text=True)
print(json.dumps({'verified':True,'services':services,'gadget_unchanged':True,'recovery_address_preserved':True}))
'''.replace('BEFORE',repr(before))
    result=json.loads(remote(SSH,verify))
    # Cancel rollback only after independent USB and Wi-Fi SSH verification.
    remote(WIFI,"import subprocess;subprocess.run(['systemctl','stop','ethershare-usb-rollback.timer'],check=True);print('rollback timer cancelled')")
    result['before']=before
    (ROOT/'evidence/ethershare-usb-integration.json').write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps(result,indent=2))
