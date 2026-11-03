"""Route the active legacy shell's Bluetooth shortcut to EtherBluetooth.

Does not restart the shell, change the system Blueman executable, or touch radio
state. Current shell source already launches etherbluetooth directly.
"""
from pathlib import Path
import hashlib
import shlex
import subprocess

ROOT = Path(__file__).resolve().parent.parent
SSH = ['ssh', '-i', str(ROOT/'build/etherpocket_ed25519'), '-o',
       'UserKnownHostsFile='+str(ROOT/'build/mobian-known-hosts'), '-o', 'BatchMode=yes',
       '-o', 'ConnectTimeout=8', 'root@10.77.0.2']


if __name__ == '__main__':
    payload = (ROOT/'ethershell/packaging/ethershell-bluetooth-compat').read_bytes()
    script = '''from pathlib import Path
import datetime,hashlib,json,os,shutil,subprocess,sys
data=sys.stdin.buffer.read()
assert hashlib.sha256(data).hexdigest()==DIGEST
assert Path('/usr/bin/etherbluetooth').is_file()
pids=subprocess.check_output(['pgrep','-u','1000','-x','ethershell'],text=True).split()
assert len(pids)==1,'Expected exactly one active shell'
proc=Path('/proc')/pids[0]
exe=(proc/'exe').resolve()
stage=exe.parent.parent.parent
assert stage.parent==Path('/opt/ethershell2') and exe==stage/'usr/bin/ethershell'
environment=dict(item.split('=',1) for item in (proc/'environ').read_bytes().decode().split('\\0') if '=' in item)
assert environment['PATH'].split(':')[0]==str(stage/'usr/bin'),'Private stage must lead PATH'
target=stage/'usr/bin/blueman-manager'
backup=Path('/var/backups/etherbluetooth-launcher')/datetime.datetime.now(datetime.timezone.utc).strftime('%Y%m%dT%H%M%SZ')
backup.mkdir(mode=0o700,parents=True)
record={'shell_pid':int(pids[0]),'target':str(target),'previous_exists':target.exists(),'system_blueman_modified':False}
if target.exists():shutil.copy2(target,backup/'blueman-manager')
temporary=target.with_name('blueman-manager.bluetooth-new')
temporary.write_bytes(data);temporary.chmod(0o755);temporary.replace(target)
(backup/'rollback.json').write_text(json.dumps(record,indent=2))
print(json.dumps(dict(record,backup=str(backup),launcher_sha256=hashlib.sha256(data).hexdigest()),indent=2))
'''.replace('DIGEST', repr(hashlib.sha256(payload).hexdigest()))
    result = subprocess.run(SSH+['python3 -c '+shlex.quote(script)],input=payload,
                            capture_output=True,check=True,timeout=15)
    output = result.stdout.decode('utf-8')
    (ROOT/'evidence/bluetooth-shortcut-fix-2026-10-17.json').write_text(output,encoding='utf-8')
    print(output)
