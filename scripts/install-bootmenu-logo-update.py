"""Install the asset-only menu update, verify both images and return to the menu."""
from pathlib import Path
import hashlib
import json
import subprocess
import sys
import time

root = Path(__file__).resolve().parent.parent
sdk = Path.home()/'AppData/Local/Android/Sdk/platform-tools'
adb = [str(sdk/'adb.exe'),'-s','548cb338']
fb = [str(sdk/'fastboot.exe'),'-s','548cb338']
ssh = ['ssh','-i',str(root/'build/etherpocket_ed25519'),'-o',
       'UserKnownHostsFile='+str(root/'build/mobian-known-hosts'),'-o',
       'BatchMode=yes','-o','ConnectTimeout=2','root@10.77.0.2']
subprocess.run([sys.executable,str(root/'scripts/check-bootmenu-logo-update.py')],check=True)
previous = json.loads((root/'recovery/bootmenu-before-header-logo/dualboot-installed.json').read_text())
for label,name in [('boot_a','native-bootmenu-test.img'),('boot_b','stock-menu-test.img')]:
    assert hashlib.sha256((root/'recovery/bootmenu-before-header-logo'/name).read_bytes()).hexdigest() == previous[label+'_sha256']
bridge = root/'build/native-disk-dp-fixed.img'
assert hashlib.sha256(bridge.read_bytes()).hexdigest() == previous['bridge_image_sha256']
r = subprocess.run(adb+['shell','getprop sys.boot_completed; getprop ro.boot.slot_suffix'],
                   check=True,capture_output=True,text=True,timeout=8)
assert r.stdout.split() == ['1','_b']
subprocess.run(adb+['reboot','bootloader'],check=True,timeout=10)
for _ in range(40):
    r = subprocess.run([fb[0],'devices'],capture_output=True,text=True,timeout=5)
    if '548cb338' in r.stdout:
        break
    time.sleep(2)
else:
    raise SystemExit('Fastboot did not appear; no image was written')
r = subprocess.run(fb+['getvar','current-slot'],check=True,capture_output=True,text=True,timeout=8)
assert 'current-slot: b' in r.stdout+r.stderr
for label,name in [('boot_a','native-bootmenu-test.img'),('boot_b','stock-menu-test.img')]:
    subprocess.run(fb+['flash',label,str(root/'build'/name)],check=True,timeout=45)
subprocess.run(fb+['boot',str(bridge)],check=True,timeout=45)
for _ in range(50):
    r = subprocess.run(ssh+['cat /etc/etherpocket/disk-identity'],capture_output=True,text=True,timeout=5)
    if r.returncode == 0 and r.stdout.strip() == 'GM1920-548cb338-mobian-sda21':
        break
    time.sleep(2)
else:
    raise SystemExit('Readback bridge SSH unavailable; installed menus and backups retained')
subprocess.run([sys.executable,str(root/'scripts/stage-bootmenu-identities.py'),'--installed'],check=True)
r = subprocess.run(ssh+['cat /etc/etherpocket/boot-images.json; '
                        'python3 /usr/local/sbin/etherpocket-select-system Android; '
                        'test ! -e /var/lib/etherpocket/next-system'],
                   check=True,capture_output=True,text=True,timeout=30)
(root/'evidence/bootmenu-header-logo-installed.txt').write_text(r.stdout)
records = json.loads((root/'build/bootmenu/installed-images.json').read_text())
manifest = json.loads((root/'build/dualboot-installed.json').read_text())
for label in ['boot_a','boot_b']:
    manifest[label+'_sha256'] = records[label]['sha256']
    manifest[label+'_size'] = records[label]['size']
assets = json.loads((root/'build/bootmenu/manifest.json').read_text())
manifest['bootmenu'].update(logo_sha256=assets['logo_sha256'],logo_asset=assets['logo_asset'],
    logo_size=assets['logo_size'],logo_alpha_composited=True,asset_only_update_verified=True)
manifest['final_running_system'] = 'boot menu (Android slot B)'
(root/'build/dualboot-installed.json').write_text(json.dumps(manifest,indent=2)+'\n')
subprocess.run(ssh+['systemctl reboot'],timeout=10)
print('Both logo images installed and read back successfully; returning to the Android-slot menu',flush=True)
