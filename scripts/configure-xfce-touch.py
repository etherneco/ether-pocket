"""Install persistent touch cursor behavior and XFCE gesture-safe settings."""
from pathlib import Path
import subprocess

root = Path(__file__).resolve().parent.parent
ssh = ['ssh', '-i', str(root / 'build/etherpocket_ed25519'),
       '-o', 'UserKnownHostsFile=' + str(root / 'build/mobian-known-hosts'),
       '-o', 'BatchMode=yes', 'root@10.77.0.2']

REMOTE = r'''
from pathlib import Path
import datetime
import json
import os
import shutil
import subprocess

home = Path('/home/mobian')
source = home / 'ethershell-src/ethershell/packaging'
backup = Path('/var/backups/etherpocket-xfce-touch-' + datetime.datetime.now(datetime.timezone.utc).strftime('%Y%m%dT%H%M%SZ'))
backup.mkdir(mode=0o700)
env = dict(os.environ, HOME=str(home), DISPLAY=':0', XAUTHORITY=str(home / '.Xauthority'),
           XDG_RUNTIME_DIR='/run/user/1000', DBUS_SESSION_BUS_ADDRESS='unix:path=/run/user/1000/bus')

def user(*args, **kwargs):
    return subprocess.run(['runuser', '-u', 'mobian', '--'] + list(args), env=env, check=True, **kwargs)

settings = {
    'xfwm4': {'/general/scroll_workspaces': ('bool', 'false'),
              '/general/mousewheel_rollup': ('bool', 'false'),
              '/general/double_click_distance': ('int', '24'),
              '/general/double_click_time': ('int', '500')},
    'xsettings': {'/Net/DndDragThreshold': ('int', '24'),
                  '/Net/DoubleClickDistance': ('int', '24'),
                  '/Net/DoubleClickTime': ('int', '500')},
    'xfce4-desktop': {'/desktop-icons/single-click': ('bool', 'true')},
    'thunar': {'/misc-single-click': ('bool', 'true')},
}
before = {}
for channel, values in settings.items():
    before[channel] = {}
    for key, (kind, value) in values.items():
        old = subprocess.run(['runuser', '-u', 'mobian', '--', 'xfconf-query', '-c', channel, '-p', key],
                             env=env, text=True, capture_output=True)
        before[channel][key] = {'type': kind, 'value': old.stdout.strip() if old.returncode == 0 else None}
(backup / 'xfconf-before.json').write_text(json.dumps(before, indent=2))
for channel, values in settings.items():
    for key, (kind, value) in values.items():
        if before[channel][key]['value'] is None:
            user('xfconf-query', '-c', channel, '-p', key, '--create', '-t', kind, '-s', value)
        else:
            user('xfconf-query', '-c', channel, '-p', key, '-s', value)

subprocess.run(['apt-get', 'install', '-y', '--no-install-recommends', 'unclutter-xfixes', 'util-linux'], check=True)
for name, dest, mode in [
    ('ethershell-touch-cursor', Path('/usr/bin/ethershell-touch-cursor'), 0o755),
    ('ethershell-touch-cursor.desktop', Path('/etc/xdg/autostart/ethershell-touch-cursor.desktop'), 0o644),
    ('ethershell-session', Path('/usr/bin/ethershell-session'), 0o755),
]:
    if dest.exists():
        shutil.copy2(dest, backup / dest.name)
    dest.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(source / name, dest)
    dest.chmod(mode)

# Replace a diagnostic cursor process, if present, then start the managed one.
subprocess.run(['pkill', '-u', '1000', '-f', r'^(/usr/bin/)?unclutter-xfixes( |$)'], check=False)
with open('/tmp/ethershell-touch-cursor.log', 'a') as log:
    subprocess.Popen(['runuser', '-u', 'mobian', '--', '/usr/bin/ethershell-touch-cursor'], env=env,
                     stdin=subprocess.DEVNULL, stdout=log, stderr=log, start_new_session=True)
print('XFCE touch settings saved; cursor manager started. Backup: ' + str(backup))
'''

if __name__ == '__main__':
    subprocess.run(['python', str(root / 'scripts/deploy-ethershell.py')], check=True)
    subprocess.run(ssh + ['python3 -'], input=REMOTE.encode(), check=True, timeout=90)
