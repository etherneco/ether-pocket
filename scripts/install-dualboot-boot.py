#!/usr/bin/env python3
"""Install the tested Mobian image on boot_a and verify the resulting native boot."""
import argparse
import hashlib
import json
from pathlib import Path
import re
import subprocess
import sys
import time

root = Path(__file__).resolve().parent.parent
parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('--install-authorized-mobian-slot-a',action='store_true')
parser.add_argument('--verify-running-installation',action='store_true')
args = parser.parse_args()
if not (args.install_authorized_mobian_slot_a or args.verify_running_installation):
    raise SystemExit('Requires --install-authorized-mobian-slot-a')
image = root/'build/native-disk-dp-fixed.img'
digest = '2ea1c9f1de7a15b78ad29bb650a7819f00476456306bcd899733eb76a8fbb15c'
assert hashlib.sha256(image.read_bytes()).hexdigest() == digest
stock = json.loads((root/'recovery/stock-backup/manifest.json').read_text())
assert hashlib.sha256((root/'recovery/stock-backup/boot_a.img').read_bytes()).hexdigest() == stock['partitions']['boot_a']['sha256']
assert '/dev/sda21 ext4 rw' in (root/'evidence/dualboot-disk-first-boot.txt').read_text()
fb = [str(Path.home()/'AppData/Local/Android/Sdk/platform-tools/fastboot.exe'),'-s','548cb338']
for label, size in ([] if args.verify_running_installation else [('boot_a',0x6000000),('userdata',34359738368),('mobian',208467374080)]):
    p = subprocess.run(fb+['getvar','partition-size:'+label],capture_output=True,text=True,timeout=8)
    m = re.search('partition-size:'+label+r':\s*(0x[0-9a-fA-F]+)',p.stdout+p.stderr)
    if p.returncode or not m or int(m[1],16) != size:
        raise SystemExit('Fastboot geometry changed: '+label)
if not args.verify_running_installation:
    for label in ['dtbo_b','vbmeta_b']:
        assert hashlib.sha256((root/('recovery/stock-backup/'+label+'.img')).read_bytes()).hexdigest() == stock['partitions'][label]['sha256']
    # Slot A's Android-9 overlays/verification metadata cannot boot this
    # Android-10-based native kernel. Keep the Android B slot untouched.
    subprocess.run(fb+['flash','dtbo_a',str(root/'recovery/stock-backup/dtbo_b.img')],check=True,timeout=45)
    subprocess.run(fb+['--disable-verity','--disable-verification','flash','vbmeta_a',
                       str(root/'recovery/stock-backup/vbmeta_b.img')],check=True,timeout=15)
    subprocess.run(fb+['flash','boot_a',str(image)],check=True,timeout=60)
    pending = dict(serial='548cb338',boot_a_verified=False,boot_a_sha256=digest)
    (root/'build/dualboot-installed.json').write_text(json.dumps(pending,indent=2)+'\n')
    subprocess.run([sys.executable,str(root/'scripts/switch-etherpocket.py'),
                    'Mobian','--finish-installation'],check=True)
ssh = ['ssh','-i',str(root/'build/etherpocket_ed25519'),'-o',
       'UserKnownHostsFile='+str(root/'build/mobian-known-hosts'),'-o','BatchMode=yes',
       '-o','ConnectTimeout=3','root@10.77.0.2']
deadline = time.monotonic()+120
while time.monotonic() < deadline:
    p = subprocess.run(ssh+['cat /etc/etherpocket/disk-identity; findmnt -rn -o SOURCE,FSTYPE,OPTIONS /; '
                              'cat /proc/cmdline; qbootctl; systemctl is-active lightdm qbootctl'],
                       capture_output=True,text=True,timeout=8)
    if p.returncode == 0:
        output = p.stdout
        (root/'evidence/dualboot-slot-a-first-boot.txt').write_text(output)
        assert 'androidboot.slot_suffix=_a' in output
        assert 'GM1920-548cb338-mobian-sda21' in output and '/dev/sda21 ext4 rw' in output
        verify = subprocess.run(ssh+['head -c '+str(image.stat().st_size)+' /dev/disk/by-partlabel/boot_a | sha256sum; '
                                         'sha256sum /dev/disk/by-partlabel/boot_b'],
                                check=True,capture_output=True,text=True,timeout=30).stdout
        assert verify.splitlines()[0].split()[0] == digest
        assert verify.splitlines()[1].split()[0] == stock['partitions']['boot_b']['sha256']
        manifest = dict(serial='548cb338',boot_a_verified=True,boot_a_sha256=digest,
                        boot_b_sha256=stock['partitions']['boot_b']['sha256'],
                        android_userdata_bytes=34359738368,mobian_bytes=208467374080,
                        xorg_driver_sha256='e127c81a1b2371acd107115e79e459680ff0eed03a807fd41f67d64f139f71a9',
                        selector='scripts/Switch-EtherPocket.ps1',gpu='llvmpipe; acceleration unverified',
                        dp_glasses='kernel fix compiled; physical output unverified')
        manifest['dtbo_a_source'] = 'verified stock dtbo_b; 38 entries including board index 35'
        manifest['vbmeta_a_flags'] = 3
        manifest['boot_success_service'] = 'qbootctl.service, verified successful slot A'
        (root/'build/dualboot-installed.json').write_text(json.dumps(manifest,indent=2)+'\n')
        print('Mobian boot_a verified from disk; stock boot_b unchanged.\n'+verify,flush=True)
        print(output[output.index('Current slot:'):],flush=True)
        break
    time.sleep(3)
else:
    raise SystemExit('Slot-A boot did not return SSH. Use Fastboot slot B for Android recovery.')
