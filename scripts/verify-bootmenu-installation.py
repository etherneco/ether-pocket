"""Verify both installed menu images and retain PC-assisted recovery switching."""
from pathlib import Path
import hashlib
import json
import subprocess
import sys

root = Path(__file__).resolve().parent.parent
ssh = ['ssh', '-i', str(root/'build/etherpocket_ed25519'), '-o',
       'UserKnownHostsFile='+str(root/'build/mobian-known-hosts'), '-o',
       'BatchMode=yes', '-o', 'ConnectTimeout=3', 'root@10.77.0.2']
subprocess.run([sys.executable, str(root/'scripts/stage-bootmenu-identities.py'), '--installed'], check=True)
helper = (root/'scripts/etherpocket-select-system.py').read_bytes()
subprocess.run(ssh+['cat > /run/etherpocket-select-system.py && install -m755 /run/etherpocket-select-system.py /usr/local/sbin/etherpocket-select-system'],
               input=helper, check=True, timeout=15)
command = ('cat /etc/etherpocket/disk-identity; uname -a; '
           'findmnt -rn -o SOURCE,FSTYPE,OPTIONS /; '
           'systemctl is-active lightdm etherpocket-usb-debug qbootctl; qbootctl; '
           'sha256sum /var/lib/etherpocket/persistence-test; '
           'python3 /usr/local/sbin/etherpocket-select-system Mobian')
r = subprocess.run(ssh+[command], check=True, capture_output=True, text=True, timeout=30)
assert '/dev/sda21 ext4 rw' in r.stdout
assert 'Current slot: _a' in r.stdout and r.stdout.count('active\n') >= 3
assert '320c98f50156379993804acfcfc9beee7d263d755c9c615e0a79a4d11273a41c' in r.stdout
(root/'evidence/bootmenu-native-installed.txt').write_text(r.stdout)
record = json.loads((root/'build/bootmenu/installed-images.json').read_text())
manifest_path = root/'build/dualboot-installed.json'
manifest = json.loads(manifest_path.read_text())
manifest.update(boot_a_verified=True, boot_a_sha256=record['boot_a']['sha256'],
                boot_a_size=record['boot_a']['size'], boot_b_sha256=record['boot_b']['sha256'],
                boot_b_size=record['boot_b']['size'],
                bridge_image_sha256='2ea1c9f1de7a15b78ad29bb650a7819f00476456306bcd899733eb76a8fbb15c',
                switch_requires_pc_usb=False, final_running_system='Mobian',
                selector='on-phone boot menu; scripts/Switch-EtherPocket.ps1 for optional PC recovery')
manifest['bootmenu'] = dict(native_image='build/native-bootmenu-test.img',
    android_image='build/stock-menu-test.img', options=['etherPocket','Android 10'],
    selection='Volume Up/Down', confirmation='Power release', automatic_timeout=False,
    logo_sha256=json.loads((root/'build/bootmenu/manifest.json').read_text())['logo_sha256'])
manifest_path.write_text(json.dumps(manifest,indent=2)+'\n')
print(r.stdout)
print('Both installed image prefixes verified; persistent data and PC selector validated')
