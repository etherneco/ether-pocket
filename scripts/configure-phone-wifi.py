#!/usr/bin/env python3
"""Install a root-only autoconnect profile from wifi.txt without logging secrets."""
import json
from pathlib import Path
import subprocess

root = Path(__file__).resolve().parent.parent
lines = (root / 'wifi.txt').read_text(encoding='utf-8-sig').splitlines()
if len(lines) != 2:
    raise SystemExit('wifi.txt must contain SSID and password on separate lines')
ssid, password = lines
if not 1 <= len(ssid.encode()) <= 32 or not (8 <= len(password) <= 63):
    raise SystemExit('Invalid WPA personal credentials')
ssh = ['ssh', '-i', str(root / 'build/etherpocket_ed25519'),
       '-o', 'UserKnownHostsFile=' + str(root / 'build/mobian-known-hosts'),
       '-o', 'BatchMode=yes', '-o', 'ConnectTimeout=8', 'root@10.77.0.2']
remote = r'''
import hashlib, json, os, pathlib, subprocess, sys, uuid
assert pathlib.Path('/etc/etherpocket/disk-identity').read_text().strip() == 'GM1920-548cb338-mobian-sda21'
ssid, password = json.load(sys.stdin)
psk = hashlib.pbkdf2_hmac('sha1', password.encode(), ssid.encode(), 4096, 32).hex()
path = pathlib.Path('/etc/NetworkManager/system-connections/etherpocket-wifi.nmconnection')
os.umask(0o077)
path.write_text('[connection]\nid=etherpocket-wifi\nuuid=' + str(uuid.uuid5(uuid.NAMESPACE_DNS, 'etherpocket.local.wifi')) +
    '\ntype=wifi\nautoconnect=true\nautoconnect-retries=0\n\n[wifi]\nmode=infrastructure\nssid=' +
    ';'.join(str(b) for b in ssid.encode()) + ';\n\n[wifi-security]\nkey-mgmt=wpa-psk\npsk=' + psk +
    '\npsk-flags=0\n\n[ipv4]\nmethod=auto\n\n[ipv6]\nmethod=auto\n')
path.chmod(0o600)
subprocess.run(['systemctl', 'enable', 'NetworkManager'], check=True)
subprocess.run(['nmcli', 'connection', 'reload'], check=True)
subprocess.run(['nmcli', 'radio', 'wifi', 'on'], check=True)
print('Installed root-only Wi-Fi autoconnect profile.')
'''
import shlex
subprocess.run(ssh + ['python3 -c ' + shlex.quote(remote)],
               input=json.dumps([ssid, password]).encode(), check=True, timeout=30)
