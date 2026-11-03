"""Install the native ARM64 app without restarting the shell or Bluetooth."""
from pathlib import Path
import hashlib
import shlex
import subprocess
ROOT = Path(__file__).resolve().parent.parent
SSH = ['ssh', '-i', str(ROOT/'build/etherpocket_ed25519'), '-o',
       'UserKnownHostsFile='+str(ROOT/'build/mobian-known-hosts'), '-o', 'BatchMode=yes',
       '-o', 'ConnectTimeout=8', 'root@10.77.0.2']
if __name__ == '__main__':
    package = ROOT/'build/etherbluetooth_0.1.0_arm64.deb'
    subprocess.run(SSH+['cat > /tmp/etherbluetooth_0.1.0_arm64.deb'], input=package.read_bytes(), check=True)
    digest = hashlib.sha256(package.read_bytes()).hexdigest()
    script = '''import hashlib,pathlib,subprocess
package=pathlib.Path('/tmp/etherbluetooth_0.1.0_arm64.deb')
assert hashlib.sha256(package.read_bytes()).hexdigest()==DIGEST, 'Package transfer hash mismatch'
subprocess.run(['dpkg','--dry-run','--install',str(package)],check=True)
subprocess.run(['dpkg','--install',str(package)],check=True)
'''.replace('DIGEST', repr(digest))
    subprocess.run(SSH+['python3 -c '+shlex.quote(script)], check=True)
