"""Administrator attestation, never invoked automatically by package installation."""
import argparse
import json
import os
import pathlib
import syslog
from core import CHECKS, fingerprints
p = argparse.ArgumentParser(description='Record only checks personally completed on this boot/build. Does not enable locking.')
for check in CHECKS: p.add_argument('--'+check, action='store_true')
a = p.parse_args()
if os.getuid() != 0: raise SystemExit('Administrator trusted recovery channel required')
if not a.recovery: raise SystemExit('Independent recovery must be verified first')
data = vars(a)
data.update(bootId=pathlib.Path('/proc/sys/kernel/random/boot_id').read_text().strip(), hashes=fingerprints())
folder = pathlib.Path('/etc/etherlock'); folder.mkdir(mode=0o755, exist_ok=True)
if folder.is_symlink() or folder.stat().st_uid != 0 or folder.stat().st_mode & 0o022:
    raise SystemExit('Unsafe attestation directory')
path = folder/'validation.json'
fd = os.open(folder/'validation.new', os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o644)
with os.fdopen(fd, 'w') as f: json.dump(data, f, indent=2)
(folder/'validation.new').replace(path)
syslog.openlog('etherlock-validation', facility=syslog.LOG_AUTHPRIV)
syslog.syslog(syslog.LOG_NOTICE, 'Administrator attested checks: '+','.join(k for k in CHECKS if data[k]))
print('Attestation saved for this boot/build. Automatic locking remains a separate policy setting.')
