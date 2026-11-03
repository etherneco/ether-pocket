"""Enable the existing IPA data owner after home-network registration."""
from pathlib import Path
import base64
import json
import runpy
import shlex
import subprocess
import sys

ROOT = Path(__file__).resolve().parent.parent
SSH = runpy.run_path(str(ROOT / 'scripts/deploy-ethermobile.py'))['SSH']


def main():
    files = {
        '/usr/local/lib/ethermobile/ethermobile-data-wait.py': (ROOT / 'scripts/ethermobile-data-wait.py').read_bytes(),
        '/etc/systemd/system/ethermobile-data.service': (ROOT / 'config/ethermobile-data.service').read_bytes(),
    }
    source = r'''
import base64,json,pathlib,subprocess,time
assert pathlib.Path('/etc/etherpocket/disk-identity').read_text().strip()=='GM1920-548cb338-mobian-sda21'
backup=pathlib.Path('/root/ethermobile-data-start-backup-'+str(time.time_ns()))
backup.mkdir(mode=0o700)
for name,data in FILES.items():
    path=pathlib.Path(name)
    assert not path.is_symlink()
    if path.exists():
        old=backup/name.lstrip('/')
        old.parent.mkdir(parents=True,exist_ok=True)
        old.write_bytes(path.read_bytes())
    path.parent.mkdir(parents=True,exist_ok=True)
    temporary=path.with_name(path.name+'.new')
    assert not temporary.is_symlink()
    temporary.write_bytes(base64.b64decode(data))
    temporary.chmod(0o644)
    temporary.replace(path)
subprocess.run(['systemctl','daemon-reload'],check=True)
subprocess.run(['systemd-analyze','verify','/etc/systemd/system/ethermobile-data.service'],check=True)
subprocess.run(['systemctl','enable','--now','ethermobile-data.service'],check=True)
print(json.dumps({'backup':str(backup),'boot':pathlib.Path('/proc/sys/kernel/random/boot_id').read_text().strip(),'installed':list(FILES)}))
'''.replace('FILES', repr({k: base64.b64encode(v).decode() for k, v in files.items()}))
    result = subprocess.run(SSH + ['python3 -c ' + shlex.quote(source)], capture_output=True, timeout=180)
    sys.stderr.buffer.write(result.stderr)
    result.check_returncode()
    report = json.loads(result.stdout)
    (ROOT / 'evidence/ethermobile-data-start-install-2026-10-29.json').write_text(json.dumps(report, indent=2) + '\n')
    print(json.dumps(report, indent=2))


if __name__ == '__main__':
    main()
