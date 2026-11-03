"""Send the static reboot helper over pinned-key SSH; no persistent writes."""
from pathlib import Path
import subprocess

w = Path(__file__).resolve().parent.parent
binary = w / 'build/reboot-bootloader'
ssh = ['ssh', '-i', str(w / 'build/etherpocket_ed25519'),
       '-o', 'UserKnownHostsFile=' + str(w / 'build/mini-known-hosts'),
       '-o', 'BatchMode=yes', '-o', 'ConnectTimeout=6', 'root@10.77.0.2']
result = subprocess.run(ssh + ['cat > /run/reboot-bootloader && chmod 700 /run/reboot-bootloader'],
                        input=binary.read_bytes())
if result.returncode:
    raise SystemExit('RAM helper transfer failed')
raise SystemExit(subprocess.run(ssh + ['/run/reboot-bootloader']).returncode)
