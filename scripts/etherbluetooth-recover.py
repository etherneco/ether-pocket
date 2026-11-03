#!/usr/bin/env python3
"""Narrow privileged recovery entry point. Never loads modules or firmware."""
import argparse
import os
import shutil
import subprocess

ACTIONS = {'restart-service': ['systemctl', 'restart', 'bluetooth.service'],
           'unblock-bluetooth': ['rfkill', 'unblock', 'bluetooth']}
if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', choices=ACTIONS)
    parser.add_argument('--apply', action='store_true')
    args = parser.parse_args()
    command = ACTIONS[args.action]
    # Resolve only root-controlled system directories, never the caller's PATH.
    executable = shutil.which(command[0], path='/usr/sbin:/usr/bin:/sbin:/bin')
    if not executable:
        raise SystemExit('Required system tool is missing: ' + command[0])
    command[0] = executable
    if not args.apply:
        print('Preview: ' + ' '.join(command))
    elif os.geteuid() != 0:
        raise SystemExit('Use PolicyKit for this explicitly confirmed recovery action.')
    else:
        subprocess.run(command, check=True, timeout=30)
