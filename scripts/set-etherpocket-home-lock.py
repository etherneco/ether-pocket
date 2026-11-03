"""Persist Home kiosk mode and restart the staged current-session shell."""
import argparse
import importlib.util
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parent.parent
DEPLOY = ROOT/'scripts/deploy-ethershell2-current.py'


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('mode', choices=['lock', 'unlock', 'navigate'])
    args = parser.parse_args()
    spec = importlib.util.spec_from_file_location('deploy_current', DEPLOY)
    deploy = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(deploy)
    subprocess.run([sys.executable, str(DEPLOY), 'stop'], check=True)
    try:
        deploy.remote('''import json,pathlib,shutil
path=pathlib.Path('/home/mobian/.config/ethershell/preferences.json')
backup=path.with_name('preferences.before-home-lock.json')
if path.exists() and not backup.exists():shutil.copy2(path,backup)
data=json.loads(path.read_text()) if path.exists() else {'schema':1}
data['homeLocked']=LOCKED
if NAVIGATION:data['dockAutoHide']=False
path.parent.mkdir(parents=True,exist_ok=True)
path.write_text(json.dumps(data,indent=2)+'\\n')
shutil.chown(path,user='mobian',group='mobian')
autostart=pathlib.Path('/home/mobian/.config/autostart/ethershell.desktop')
saved=path.with_name('autostart.before-home-lock.desktop')
if LOCKED or NAVIGATION:
 if autostart.exists() and not saved.exists():shutil.copy2(autostart,saved)
 autostart.parent.mkdir(parents=True,exist_ok=True)
 autostart.write_text('[Desktop Entry]\\nType=Application\\nName=EtherPocket Home\\nExec=/home/mobian/.local/bin/ethershell2-start\\nTryExec=/home/mobian/.local/bin/ethershell2-start\\nTerminal=false\\nOnlyShowIn=XFCE;\\nHidden=false\\n')
 shutil.chown(autostart,user='mobian',group='mobian')
elif saved.exists():
 shutil.copy2(saved,autostart)
 shutil.chown(autostart,user='mobian',group='mobian')
print('Home lock:',data['homeLocked'])
'''.replace('LOCKED', repr(args.mode == 'lock')).replace('NAVIGATION', repr(args.mode == 'navigate')))
    finally:
        subprocess.run([sys.executable, str(DEPLOY), 'start'], check=True)
