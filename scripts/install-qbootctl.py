"""Validate and install the signed-repository Debian qbootctl package on disk Mobian."""
from pathlib import Path
import hashlib
import subprocess
from importlib.machinery import SourceFileLoader
root = Path(__file__).resolve().parent.parent
audit = SourceFileLoader('gpt_audit', str(root/'scripts/audit-dualboot.py')).load_module()
package = root/'build/qbootctl_0.2.2-1_arm64.deb'
assert hashlib.sha256(package.read_bytes()).hexdigest() == '76b9be97107f14a79641bc274a00010aade3362b5099df5ae8b85603cbb6eb22'
def run(command, **kwargs):
    return subprocess.run(audit.SSH+[command],check=True,timeout=60,**kwargs)
run('test "$(cat /etc/etherpocket/disk-identity)" = GM1920-548cb338-mobian-sda21 && '
    'test "$(findmnt -rn -o SOURCE /)" = /dev/sda21')
with package.open('rb') as f:
    run('cat > /run/qbootctl.deb',stdin=f)
run('mkdir -p /run/qbootctl-probe && dpkg-deb -x /run/qbootctl.deb /run/qbootctl-probe && '
    '/run/qbootctl-probe/usr/bin/qbootctl')
run('dpkg -i /run/qbootctl.deb && systemctl status qbootctl.service --no-pager; /usr/bin/qbootctl')
