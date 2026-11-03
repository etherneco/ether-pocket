"""Upload a local file into /run on the native phone's verified RAM root."""
import argparse
import subprocess
from pathlib import Path
w = Path(__file__).resolve().parent.parent
p = argparse.ArgumentParser()
p.add_argument('file', type=Path)
p.add_argument('--executable', action='store_true')
a = p.parse_args()
name = a.file.name
if not all(c.isalnum() or c in '._-+' for c in name):
    raise SystemExit('Unsupported filename')
ssh = ['ssh', '-i', str(w / 'build/etherpocket_ed25519'),
       '-o', 'UserKnownHostsFile=' + str(w / 'build/mobian-known-hosts'),
       '-o', 'BatchMode=yes', '-o', 'ConnectTimeout=8', 'root@10.77.0.2']
command = ('test $(stat -f -c %T /run) = tmpfs && '
           '{ test $(stat -f -c %T /) = tmpfs || '
           'test "$(cat /etc/etherpocket/disk-identity 2>/dev/null)" = GM1920-548cb338-mobian-sda21; } && '
           'cat > /run/' + name)
if a.executable:
    command += ' && chmod 700 /run/' + name
with a.file.open('rb') as stream:
    subprocess.run(ssh + [command], stdin=stream, check=True)
