#!/usr/bin/env python3
"""Switch GM1920 systems with canonical boot type GUIDs and verified firmware B."""
import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import time

root = Path(__file__).resolve().parent.parent
p = argparse.ArgumentParser(description=__doc__)
p.add_argument('system',choices=['Android','Mobian'])
p.add_argument('--finish-installation',action='store_true',help=argparse.SUPPRESS)
args = p.parse_args()
manifest = json.loads((root/'build/dualboot-installed.json').read_text())
assert manifest['serial'] == '548cb338'
assert manifest['boot_a_verified'] or (args.finish_installation and args.system == 'Mobian')
sdk = Path.home()/'AppData/Local/Android/Sdk/platform-tools'
adb = [str(sdk/'adb.exe'),'-s','548cb338']
fb = [str(sdk/'fastboot.exe'),'-s','548cb338']
ssh = ['ssh','-i',str(root/'build/etherpocket_ed25519'),'-o',
       'UserKnownHostsFile='+str(root/'build/mobian-known-hosts'),'-o','BatchMode=yes',
       '-o','ConnectTimeout=2','-o','ConnectionAttempts=1','root@10.77.0.2']


def probe(command, timeout=6):
    try:
        return subprocess.run(command,capture_output=True,text=True,timeout=timeout)
    except subprocess.TimeoutExpired:
        return None


def native_ready():
    r = probe(ssh+['cat /etc/etherpocket/disk-identity; cat /proc/cmdline'])
    return r if r and r.returncode == 0 and 'GM1920-548cb338-mobian-sda21' in r.stdout else None


def android_ready():
    d = probe([adb[0],'devices'])
    if not d or '548cb338\tdevice' not in d.stdout:
        return None
    r = probe(adb+['shell','getprop sys.boot_completed; getprop ro.boot.slot_suffix'])
    return r if r and r.returncode == 0 and r.stdout.split() == ['1','_b'] else None


def wait_for(check, seconds, label):
    deadline = time.monotonic()+seconds
    while time.monotonic() < deadline:
        result = check()
        if result:
            return result
        time.sleep(2)
    raise SystemExit('Timed out waiting for '+label)


current = native_ready()
if not current:
    android = android_ready()
    if android and args.system == 'Android':
        print('Android is already running in slot B.',flush=True)
        raise SystemExit(0)
    if android:
        print('Entering Fastboot from Android...',flush=True)
        subprocess.run(adb+['reboot','bootloader'],check=True,timeout=10)
    def fastboot_ready():
        r = probe([fb[0],'devices'])
        return r if r and '548cb338' in r.stdout else None
    wait_for(fastboot_ready,60,'Fastboot')
    image = root/'build/native-disk-dp-fixed.img'
    assert hashlib.sha256(image.read_bytes()).hexdigest() == manifest.get('bridge_image_sha256',manifest['boot_a_sha256'])
    print('Starting native disk-root bridge; no flashing...',flush=True)
    subprocess.run(fb+['boot',str(image)],check=True,timeout=45)
    current = wait_for(native_ready,100,'native bridge SSH')
print('Selecting '+args.system+' with canonical boot partition types...',flush=True)
helper = root/'scripts/etherpocket-select-system.py'
subprocess.run(ssh+['cat > /run/etherpocket-select-system.py && '
                   'install -m755 /run/etherpocket-select-system.py /usr/local/sbin/etherpocket-select-system'],
               input=helper.read_bytes(),check=True,timeout=15)
subprocess.run(ssh+['python3 /usr/local/sbin/etherpocket-select-system '+args.system+' --apply'],
               check=True,timeout=30)
probe(ssh+['systemctl reboot --reboot-argument=bootloader'],timeout=8)
time.sleep(4)
def fastboot_activation_ready():
    r = probe([fb[0],'devices'])
    return r if r and '548cb338' in r.stdout else None
wait_for(fastboot_activation_ready,60,'Fastboot activation')
slot = 'a' if args.system == 'Mobian' else 'b'
subprocess.run(fb+['--set-active='+slot],check=True,timeout=10)
subprocess.run(fb+['reboot'],check=True,timeout=10)
time.sleep(4)
if args.system == 'Mobian':
    ready = wait_for(native_ready,120,'Mobian boot')
    assert 'androidboot.slot_suffix=_a' in ready.stdout
    evidence = probe(ssh+['findmnt -rn -o SOURCE,FSTYPE,OPTIONS /; qbootctl; '
                          'sha256sum /var/lib/etherpocket/persistence-test; '
                          'systemctl is-active lightdm'],timeout=20)
else:
    ready = wait_for(android_ready,120,'Android boot')
    evidence = probe(adb+['shell','getprop ro.boot.slot_suffix; getprop sys.boot_completed; df -h /data'])
assert evidence and evidence.returncode == 0
print(evidence.stdout,flush=True)
(root/('evidence/dualboot-switch-'+args.system.lower()+'.txt')).write_text(evidence.stdout)
print(args.system+' boot verified.',flush=True)
