"""Read-only sharing audit. Never dump connection secrets or Wi-Fi SSIDs."""
from pathlib import Path
import json, runpy, subprocess

ROOT = Path(__file__).resolve().parent.parent
SSH = runpy.run_path(str(ROOT / 'scripts/deploy-ethermobile.py'))['SSH']
REMOTE = r'''
import glob,gzip,json,os,pathlib,shutil,subprocess
assert pathlib.Path('/etc/etherpocket/disk-identity').read_text().strip()=='GM1920-548cb338-mobian-sda21'
commands={
 'links':['ip','-j','-d','link'], 'addresses':['ip','-j','addr'],
 'routes':['ip','-j','route'], 'routes6':['ip','-j','-6','route'],
 'rules':['ip','rule'], 'devices':['nmcli','-t','-f','DEVICE,TYPE,STATE','device'],
 'profiles':['nmcli','-t','-f','UUID,TYPE,DEVICE','connection'],
 'iw_list':['iw','list'], 'rfkill':['rfkill','list'],
 'services':['systemctl','is-active','NetworkManager','ModemManager','ethermobile-data','bluetooth','systemd-networkd','dnsmasq','nftables','hostapd','ssh'],
 'iptables':['/usr/sbin/iptables-save'], 'ip6tables':['/usr/sbin/ip6tables-save'],
 'nft':['/usr/sbin/nft','list','ruleset'],
 'bluez':['busctl','introspect','org.bluez','/org/bluez/hci0','org.bluez.NetworkServer1'],
 'nm_version':['nmcli','--version'],
 'nm_shared':['NetworkManager','--print-config'],
 'usbservices':['systemctl','list-units','--all','--no-pager','*usb*','*gadget*','*rndis*'],
 'python':['python3','-c','import dbus;from gi.repository import GLib;print("dbus+glib ready")'],
}
out={}
for key,args in commands.items():
 try:
  r=subprocess.run(args,capture_output=True,text=True,timeout=12)
  out[key]={'code':r.returncode,'output':r.stdout[:45000],'error':r.stderr[:1000]}
 except Exception as e:out[key]={'error':str(e)}
out['sysfs']={}
for pattern in ['/sys/class/udc/*/state','/sys/class/usb_role/*/role','/sys/class/typec/*/data_role','/sys/class/power_supply/*/uevent','/sys/class/net/*/device/uevent','/sys/class/net/*/statistics/*','/proc/sys/net/ipv4/ip_forward']:
 for p in glob.glob(pattern):
  try:out['sysfs'][p]=pathlib.Path(p).read_text()[:3000]
  except OSError:pass
out['gadgets']={}
for p in glob.glob('/sys/kernel/config/usb_gadget/**/*',recursive=True):
 q=pathlib.Path(p)
 if q.is_symlink():out['gadgets'][p]=os.readlink(p)
 elif q.name in ['UDC','idVendor','idProduct','bDeviceClass','dev_addr','host_addr','ifname']:out['gadgets'][p]=q.read_text().strip()
out['kernel']={}
p=pathlib.Path('/proc/config.gz')
if p.exists():
 for line in gzip.decompress(p.read_bytes()).decode().splitlines():
  if any(k in line for k in ['CONFIG_USB_CONFIGFS','CONFIG_USB_F_','CONFIG_BT_BNEP','CONFIG_NF_TABLES','CONFIG_NF_NAT','CONFIG_IP_NF','CONFIG_NETFILTER_XT','CONFIG_BRIDGE']):out['kernel'][line.split('=')[0]]=line
out['tools']={k:shutil.which(k) for k in ['dnsmasq','iptables','iptables-legacy','nft','iw','curl','bluetoothctl','NetworkManager']}
out['usb_paths']=glob.glob('/sys/class/udc/*')
print(json.dumps(out,indent=2))
'''

if __name__ == '__main__':
    result = subprocess.run(SSH + ['python3 -'], input=REMOTE.encode(), capture_output=True, timeout=110, check=True)
    data = json.loads(result.stdout)
    target = ROOT / 'evidence/ethershare-audit-2026-10-19.json'
    target.write_text(json.dumps(data, indent=2) + '\n', encoding='utf-8')
    print(target)
    for key in ['devices','routes','rules','services','iw_list','gadgets','kernel','tools','iptables','nft','bluez','usbservices','python']:
        print(key, json.dumps(data.get(key), indent=2))
