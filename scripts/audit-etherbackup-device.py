"""Read-only storage/backup/recovery audit over the existing pinned SSH channel."""
from pathlib import Path
import json, runpy, subprocess
ROOT=Path(__file__).resolve().parent.parent
SSH=runpy.run_path(str(ROOT/'scripts/deploy-ethermobile.py'))['SSH']
SOURCE=r'''
import datetime,json,pathlib,shutil,subprocess
assert pathlib.Path('/etc/etherpocket/disk-identity').read_text().strip()=='GM1920-548cb338-mobian-sda21'
def run(args):
 if not shutil.which(args[0]):return {'available':False}
 try:
  p=subprocess.run(args,capture_output=True,text=True,timeout=20)
  return dict(exit=p.returncode,stdout=p.stdout[:140000],stderr=p.stderr[:2000])
 except subprocess.TimeoutExpired:return {'error':'timeout'}
commands={k:run(v) for k,v in {
 'identity':['uname','-a'],'os':['cat','/etc/os-release'],
 'storage':['lsblk','-J','-b','-o','NAME,PKNAME,SIZE,FSTYPE,FSVER,LABEL,UUID,PARTLABEL,MOUNTPOINTS,RO,TYPE,TRAN'],
 'mounts':['findmnt','--json'],'blkid':['blkid'],'space':['df','-B1','-T'],
 'timers':['systemctl','list-timers','--all','--no-pager'],
 'engines':['sh','-c','command -v restic borg btrfs lvs fastboot adb; dpkg-query -W restic borgbackup python3-dbus python3-gi'],
 'packages':['apt-cache','policy','restic','borgbackup'],
 'services':['systemctl','is-active','ssh','etherpower','etherhardware','etherupdate','NetworkManager','ModemManager'],
 'power':['busctl','call','com.etherneco.EtherPower1','/com/etherneco/EtherPower1','com.etherneco.EtherPower1','GetState'],
 'network':['nmcli','-t','-f','DEVICE,TYPE,STATE','device'],
 'usb':['lsusb'],'block':['cat','/proc/partitions'],
 'snapshots':['sh','-c','find /etc/cron.d /etc/systemd/system /usr/local/bin /usr/local/sbin -maxdepth 2 -iname "*backup*" -o -iname "*snapshot*"'],
 'recoveryFiles':['sh','-c','find /etc/etherpocket /boot -maxdepth 2 -type f -printf "%p\\n"'],
 'applicationPaths':['sh','-c','find /home /var/lib/etherupdate /var/lib/etherpower /var/lib/etherhardware -maxdepth 4 -type f \\( -name "*.sqlite*" -o -name "*.db" -o -name "*.json" -o -name "*.ini" -o -name "*.conf" \\) -printf "%p\\n" | head -500']}.items()}
print(json.dumps(dict(timestamp=datetime.datetime.now(datetime.timezone.utc).isoformat(),commands=commands,
 scope='Read only; no partition writes, filesystem repair, reboot, mount changes or credential contents',
 recovery={'ssh':'Verified by this audit','bootloader':'Historical evidence only; not rebooted during this task','externalBoot':'Not verified','bareMetalRestoreTested':False}),indent=2))
'''
if __name__=='__main__':
 p=subprocess.run(SSH+['python3 -'],input=SOURCE.encode(),capture_output=True,timeout=180,check=True)
 target=ROOT/'evidence/etherbackup-audit-2026-10-21.json'
 target.write_text(json.dumps(json.loads(p.stdout),indent=2)+'\n',encoding='utf-8')
 print(target)
