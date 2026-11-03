#!/usr/bin/env python3
"""Boot the verified disk-root candidate temporarily; perform no flashing."""
import hashlib
from pathlib import Path
import re
import subprocess
import time

ROOT = Path(__file__).resolve().parent.parent
FASTBOOT = [str(Path.home()/'AppData/Local/Android/Sdk/platform-tools/fastboot.exe'), '-s','548cb338']
image = ROOT/'build/native-disk-dp-fixed.img'
with image.open('rb') as f:
    if hashlib.file_digest(f,'sha256').hexdigest() != '2ea1c9f1de7a15b78ad29bb650a7819f00476456306bcd899733eb76a8fbb15c':
        raise SystemExit('Disk boot image digest mismatch')
for label, size in [('userdata',34359738368), ('mobian',208467374080)]:
    result = subprocess.run(FASTBOOT+['getvar','partition-size:'+label],capture_output=True,text=True,timeout=8)
    match = re.search('partition-size:'+label+r':\s*(0x[0-9a-fA-F]+)',result.stdout+result.stderr)
    if result.returncode or not match or int(match[1],16) != size:
        raise SystemExit('Fastboot geometry mismatch: '+label+'\n'+result.stdout+result.stderr)
subprocess.run(FASTBOOT+['boot',str(image)],check=True,timeout=45)
ssh = ['ssh','-i',str(ROOT/'build/etherpocket_ed25519'),'-o',
       'UserKnownHostsFile='+str(ROOT/'build/mobian-known-hosts'),'-o',
       'BatchMode=yes','-o','ConnectTimeout=3','root@10.77.0.2']
deadline = time.monotonic()+100
while time.monotonic() < deadline:
    result = subprocess.run(ssh+['findmnt -rn -o SOURCE,FSTYPE,OPTIONS /; '
                                  'cat /etc/etherpocket/disk-identity; '
                                  'cat /proc/1/comm; uname -a'],capture_output=True,text=True,timeout=6)
    if result.returncode == 0:
        (ROOT/'evidence/dualboot-disk-first-boot.txt').write_text(result.stdout)
        print(result.stdout,flush=True)
        if 'GM1920-548cb338-mobian-sda21' not in result.stdout or '/dev/sda21 ext4 rw' not in result.stdout:
            raise SystemExit('SSH returned but persistent writable root is not validated')
        print('Persistent root boot verified. This test performed no flashing.',flush=True)
        break
    time.sleep(3)
else:
    raise SystemExit('Native disk-root SSH did not return; check phone and rescue host-key identity.')
