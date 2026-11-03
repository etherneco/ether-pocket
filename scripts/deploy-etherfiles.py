"""Install only EtherFiles and its declared userspace dependencies on EtherPocket.

No reboot, service restart, shell replacement or default-file-manager change.
The GUI is never started as root. SSH uses the existing pinned host key.
"""
from pathlib import Path
import hashlib
import shlex
import subprocess

ROOT = Path(__file__).resolve().parent.parent
PACKAGE = ROOT/'build/etherfiles_0.1.1_arm64.deb'
SSH = ['ssh', '-i', str(ROOT/'build/etherpocket_ed25519'), '-o',
       'UserKnownHostsFile='+str(ROOT/'build/mobian-known-hosts'), '-o',
       'BatchMode=yes', '-o', 'ConnectTimeout=8', 'root@10.77.0.2']


def remote(source, payload=None):
    return subprocess.run(SSH+['python3 -c '+shlex.quote(source)], input=payload, check=True)


if __name__ == '__main__':
    data = PACKAGE.read_bytes()
    digest = hashlib.sha256(data).hexdigest()
    remote('''import hashlib,pathlib,sys
data=sys.stdin.buffer.read()
assert hashlib.sha256(data).hexdigest()==DIGEST
pathlib.Path('/tmp/etherfiles_0.1.1_arm64.deb').write_bytes(data)
'''.replace('DIGEST', repr(digest)), data)
    remote('''import hashlib,json,pathlib,re,subprocess
def run(args):return subprocess.run(args,check=True,capture_output=True,text=True).stdout.strip()
def baseline():return {
 'kernel':run(['uname','-r']),
 'thunar_sha256':hashlib.sha256(pathlib.Path('/usr/bin/thunar').read_bytes()).hexdigest(),
 'thunar_version':run(['dpkg-query','-W','-f=${Version}','thunar']),
 'ssh':run(['systemctl','is-active','ssh']),
 'network_manager':run(['systemctl','is-active','NetworkManager'])}
before=baseline()
plan=run(['apt-get','--simulate','--no-install-recommends','install','/tmp/etherfiles_0.1.1_arm64.deb','poppler-utils'])
for line in plan.splitlines():
 if line.startswith('Remv '):raise RuntimeError('Refusing package removals: '+line)
 if re.match(r'Inst (linux-|thunar |xfce4|openssh|network-manager |xserver-xorg)',line):
  raise RuntimeError('Unexpected protected-environment package change: '+line)
pathlib.Path('/tmp/etherfiles-install-plan.txt').write_text(plan)
subprocess.run(['apt-get','-y','--no-remove','--no-install-recommends','--reinstall','install','/tmp/etherfiles_0.1.1_arm64.deb'],check=True)
subprocess.run(['apt-get','-y','--no-remove','--no-install-recommends','install','poppler-utils'],check=True)
after=baseline()
assert before==after, 'Baseline changed; inspect before/after evidence'
result={'before':before,'after':after,'package_sha256':DIGEST,'installed_version':run(['dpkg-query','-W','-f=${Version}','etherfiles'])}
pathlib.Path('/tmp/etherfiles-install-result.json').write_text(json.dumps(result,indent=2))
print(json.dumps(result,indent=2))
'''.replace('DIGEST', repr(digest)))
