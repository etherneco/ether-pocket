"""Deploy built native-touch support and restart only EtherShell/Firefox.

Run locally after deploy-ethershell.py --build. Keeps a device-side backup of
configuration, binaries and Firefox session recovery files before restarting.
"""
from pathlib import Path
import subprocess

root = Path(__file__).resolve().parent.parent
ssh = ['ssh', '-i', str(root / 'build/etherpocket_ed25519'),
       '-o', 'UserKnownHostsFile=' + str(root / 'build/mobian-known-hosts'),
       '-o', 'BatchMode=yes', 'root@10.77.0.2']

REMOTE = r'''
from pathlib import Path
import datetime
import os
import shutil
import signal
import subprocess
import time

home = Path('/home/mobian')
source = home / 'ethershell-src/ethershell/packaging'
backup = Path('/var/backups/etherpocket-touch-' + datetime.datetime.now(datetime.timezone.utc).strftime('%Y%m%dT%H%M%SZ'))
backup.mkdir(mode=0o700)

def save(path):
    if path.exists():
        dest = backup / str(path).lstrip('/')
        dest.parent.mkdir(parents=True, exist_ok=True)
        if path.is_dir():
            shutil.copytree(path, dest)
        else:
            shutil.copy2(path, dest)

def install(src, dest, mode=0o644):
    save(dest)
    dest.parent.mkdir(parents=True, exist_ok=True)
    # Replace rather than truncate a running executable.
    temp = dest.with_name(dest.name + '.touch-new')
    shutil.copyfile(src, temp)
    temp.chmod(mode)
    temp.replace(dest)

install(source / '80-ethershell-touch', Path('/etc/X11/Xsession.d/80-ethershell-touch'))
install(source / 'etherpocket-touch.js', Path('/etc/firefox-esr/etherpocket-touch.js'))
install(source / 'ethershell-session', Path('/usr/bin/ethershell-session'), 0o755)
install(home / 'ethershell-build/ethershell', Path('/usr/bin/ethershell'), 0o755)

# Existing XFCE launchers have inherited the old login environment. A desktop
# override makes their Firefox launches use XI2 immediately as well.
desktop = home / '.local/share/applications/firefox-esr.desktop'
save(desktop)
desktop.parent.mkdir(parents=True, exist_ok=True)
original = desktop.read_text() if desktop.exists() else Path('/usr/share/applications/firefox-esr.desktop').read_text()
lines = [line.replace('Exec=', 'Exec=env MOZ_USE_XINPUT2=1 ', 1)
         if line.startswith('Exec=') and 'MOZ_USE_XINPUT2=1' not in line else line
         for line in original.splitlines()]
desktop.write_text('\n'.join(lines) + '\n')
os.chown(desktop.parent, 1000, 1000)
os.chown(desktop, 1000, 1000)

env = dict(os.environ, HOME=str(home), DISPLAY=':0', XAUTHORITY=str(home / '.Xauthority'),
           XDG_RUNTIME_DIR='/run/user/1000', DBUS_SESSION_BUS_ADDRESS='unix:path=/run/user/1000/bus',
           MOZ_USE_XINPUT2='1', QT_QUICK_CONTROLS_MOBILE='1')
for key in ('GDK_CORE_DEVICE_EVENTS', 'QT_XCB_NO_XI2', 'QT_XCB_NO_TOUCH'):
    env.pop(key, None)
subprocess.run(['runuser', '-u', 'mobian', '--', 'dbus-update-activation-environment', '--systemd',
                'MOZ_USE_XINPUT2', 'QT_QUICK_CONTROLS_MOBILE'], env=env, check=True)

def pids(name):
    result = subprocess.run(['pgrep', '-u', '1000', '-x', name], text=True, capture_output=True)
    return [int(pid) for pid in result.stdout.split()]

def stop(name):
    for pid in pids(name):
        os.kill(pid, signal.SIGTERM)
    for n in range(100):
        if not pids(name):
            return
        time.sleep(.2)
    raise RuntimeError(name + ' did not exit gracefully; left running, no forced kill')

def start(args, logname):
    with open('/tmp/' + logname, 'a') as log:
        subprocess.Popen(['runuser', '-u', 'mobian', '--'] + args, env=env,
            stdin=subprocess.DEVNULL, stdout=log, stderr=log, start_new_session=True)

# Discover the actual active profile from Firefox's profile lock.
profiles = home / '.config/mozilla/firefox'
active = [p.parent for p in profiles.glob('*/lock') if p.is_symlink()]
running = pids('firefox-esr')
if running:
    if len(active) != 1:
        raise RuntimeError('Cannot identify a single active Firefox profile; configuration installed without browser restart')
    profile = active[0]
    for name in ('sessionstore-backups', 'sessionstore.jsonlz4', 'prefs.js', 'user.js'):
        save(profile / name)
    userjs = profile / 'user.js'
    previous = userjs.read_bytes() if userjs.exists() else None
    userjs.write_bytes((previous or b'') + b'\nuser_pref("browser.sessionstore.resume_session_once", true);\n')
    os.chown(userjs, 1000, 1000)
    stop('firefox-esr')
    start(['firefox-esr', '--profile', str(profile)], 'etherpocket-firefox-touch.log')
    time.sleep(5)
    if not pids('firefox-esr'):
        raise RuntimeError('Firefox did not restart; recovery files retained at ' + str(backup))
    # resume_session_once is a one-time migration, not a permanent user setting.
    if previous is None:
        userjs.unlink()
    else:
        userjs.write_bytes(previous)
        os.chown(userjs, 1000, 1000)

stop('ethershell')
start(['/usr/bin/ethershell'], 'ethershell-touch.log')
time.sleep(3)
assert pids('ethershell'), 'EtherShell did not restart'
print('Native touch installed; Firefox and EtherShell running. Backup: ' + str(backup))
'''

if __name__ == '__main__':
    subprocess.run(ssh + ['python3 -'], input=REMOTE.encode(), check=True, timeout=90)
