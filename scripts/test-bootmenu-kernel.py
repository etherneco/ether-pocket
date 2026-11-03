"""Temporarily boot a candidate from Fastboot, retaining the installed image."""
import argparse
from pathlib import Path
import subprocess
import time

root = Path(__file__).resolve().parent.parent
p = argparse.ArgumentParser(description=__doc__)
p.add_argument('image', type=Path)
p.add_argument('--menu', action='store_true')
p.add_argument('--from-android', action='store_true')
a = p.parse_args()
ssh = ['ssh', '-i', str(root/'build/etherpocket_ed25519'), '-o',
       'UserKnownHostsFile='+str(root/'build/mobian-known-hosts'), '-o',
       'BatchMode=yes', '-o', 'ConnectTimeout=3', 'root@10.77.0.2']
fb = [str(Path.home()/'AppData/Local/Android/Sdk/platform-tools/fastboot.exe'), '-s', '548cb338']
if a.from_android:
    adb = [str(Path.home()/'AppData/Local/Android/Sdk/platform-tools/adb.exe'), '-s', '548cb338']
    r = subprocess.run(adb+['shell', 'getprop sys.boot_completed; getprop ro.boot.slot_suffix'], capture_output=True, text=True, timeout=6)
    assert r.returncode == 0 and r.stdout.split() == ['1', '_b']
    subprocess.run(adb+['reboot', 'bootloader'], check=True, timeout=10)
else:
    r = subprocess.run(ssh+['cat /etc/etherpocket/disk-identity'], capture_output=True, text=True)
    assert r.returncode == 0 and r.stdout.strip() == 'GM1920-548cb338-mobian-sda21'
    subprocess.run(ssh+['systemctl reboot --reboot-argument=bootloader'], timeout=10)
for _ in range(30):
    r = subprocess.run([fb[0], 'devices'], capture_output=True, text=True, timeout=5)
    if '548cb338' in r.stdout:
        break
    time.sleep(2)
else:
    raise SystemExit('Fastboot did not appear')
subprocess.run(fb+['boot', str(a.image.resolve())], check=True, timeout=45)
if a.menu:
    ssh[ssh.index('UserKnownHostsFile='+str(root/'build/mobian-known-hosts'))] = 'UserKnownHostsFile='+str(root/'build/mini-known-hosts')
for _ in range(45):
    r = subprocess.run(ssh+['uname -a; cat /sys/kernel/kexec_loaded; cat /run/bootmenu.log 2>/dev/null; cat /proc/mounts | head -5'],
                       capture_output=True, text=True, timeout=6)
    if r.returncode == 0:
        print(r.stdout)
        (root/'evidence/bootmenu-kernel-test.txt').write_text(r.stdout)
        break
    time.sleep(2)
else:
    raise SystemExit('Candidate has not returned SSH; installed boot_a is retained')
