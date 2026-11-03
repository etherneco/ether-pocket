"""Upload and build EtherShell without changing the active session."""
from pathlib import Path
import argparse
import subprocess
import tarfile

root = Path(__file__).resolve().parent.parent
ssh = ['ssh', '-i', str(root/'build/etherpocket_ed25519'),
       '-o', 'UserKnownHostsFile='+str(root/'build/mobian-known-hosts'),
       '-o', 'BatchMode=yes', '-o', 'ConnectTimeout=8', 'root@10.77.0.2']

def remote(command, **kwargs):
    return subprocess.run(ssh+[command], check=True, **kwargs)

if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--build', action='store_true')
    parser.add_argument('--jobs', type=int, choices=range(1,5), default=2,
                        help='Bound native compiler concurrency on the phone (default: 2).')
    args = parser.parse_args()
    archive = root/'build/ethershell-source.tar'
    with tarfile.open(archive, 'w') as tar:
        tar.add(root/'ethershell', arcname='ethershell', filter=lambda item: None if '/build/' in item.name or '/__pycache__' in item.name or item.name.endswith('.pyc') else item)
        tar.add(root/'etherbluetooth', arcname='etherbluetooth', filter=lambda item: None if '/build/' in item.name else item)
        tar.add(root/'scripts/etherair-x11.py', arcname='scripts/etherair-x11.py')
    remote('mkdir -p /home/mobian/ethershell-src && tar xf - -C /home/mobian/ethershell-src && chown -R mobian:mobian /home/mobian/ethershell-src', input=archive.read_bytes())
    if args.build:
        remote("runuser -u mobian -- sh -c 'cmake -S /home/mobian/ethershell-src/ethershell -B /home/mobian/ethershell-build -DCMAKE_BUILD_TYPE=Release -DCMAKE_INSTALL_PREFIX=/usr && cmake --build /home/mobian/ethershell-build -j"+str(args.jobs)+"'", timeout=900)
