"""Place the official Debian gdbserver binary in the phone's RAM root."""
from pathlib import Path
import subprocess
w = Path(__file__).resolve().parent.parent
ssh = ['ssh', '-i', str(w / 'build/etherpocket_ed25519'),
       '-o', 'UserKnownHostsFile=' + str(w / 'build/mobian-known-hosts'),
       '-o', 'BatchMode=yes', '-o', 'ConnectTimeout=8', 'root@10.77.0.2']
with (w / 'build/gdbserver-arm64').open('rb') as binary:
    subprocess.run(ssh + ['cat > /run/gdbserver && chmod 700 /run/gdbserver && systemctl stop lightdm'],
                   stdin=binary, check=True)
