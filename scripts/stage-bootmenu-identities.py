"""Verify the current boot images and stage the new menu identities on Mobian."""
from pathlib import Path
import argparse
import hashlib
import json
import subprocess

root = Path(__file__).resolve().parent.parent
p = argparse.ArgumentParser(description=__doc__)
p.add_argument('--installed', action='store_true', help='Verify the new native image after flashing it.')
args = p.parse_args()
record = {'serial': '548cb338'}
for label, name in [('boot_a', 'native-bootmenu-test.img'), ('boot_b', 'stock-menu-test.img')]:
    image = root/'build'/name
    record[label] = {'size': image.stat().st_size, 'sha256': hashlib.sha256(image.read_bytes()).hexdigest()}
ssh = ['ssh', '-i', str(root/'build/etherpocket_ed25519'), '-o',
       'UserKnownHostsFile='+str(root/'build/mobian-known-hosts'), '-o',
       'BatchMode=yes', '-o', 'ConnectTimeout=3', 'root@10.77.0.2']
remote = '''from pathlib import Path
import hashlib, json
assert Path('/etc/etherpocket/disk-identity').read_text().strip() == 'GM1920-548cb338-mobian-sda21'
assert 'androidboot.serialno=548cb338' in Path('/proc/cmdline').read_text().split()
record = RECORD
expected_a = EXPECTED_A
with open('/dev/sde11','rb') as f:
    assert hashlib.sha256(f.read(expected_a['size'])).hexdigest() == expected_a['sha256']
with open('/dev/sde39','rb') as f:
    assert hashlib.sha256(f.read(record['boot_b']['size'])).hexdigest() == record['boot_b']['sha256']
p = Path('/etc/etherpocket/boot-images.json')
p.write_text(json.dumps(record,indent=2)+'\\n')
p.chmod(0o600)
print('Native A and Android-menu B verified; installed image identities staged')
'''.replace('RECORD', repr(record)).replace('EXPECTED_A', repr(record['boot_a'] if args.installed else {
    'size': 45527040, 'sha256': '2ea1c9f1de7a15b78ad29bb650a7819f00476456306bcd899733eb76a8fbb15c'}))
subprocess.run(ssh+['python3 -'], input=remote.encode(), check=True, timeout=20)
(root/'build/bootmenu/installed-images.json').write_text(json.dumps(record,indent=2)+'\n')
