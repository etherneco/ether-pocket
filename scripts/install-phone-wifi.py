#!/usr/bin/env python3
"""Deploy the already built native Wi-Fi helpers and their boot services."""
from pathlib import Path
import subprocess

root = Path(__file__).resolve().parent.parent
ssh = ['ssh', '-i', str(root / 'build/etherpocket_ed25519'), '-o',
       'UserKnownHostsFile=' + str(root / 'build/mobian-known-hosts'),
       '-o', 'BatchMode=yes', '-o', 'ConnectTimeout=8', 'root@10.77.0.2']

def run(command, data=None):
    return subprocess.run(ssh + [command], input=data, check=True, timeout=60)

def put(path, data, mode='644'):
    run(f'cat > {path}.new && chmod {mode} {path}.new && mv {path}.new {path}', data)

run("test $(cat /etc/etherpocket/disk-identity) = GM1920-548cb338-mobian-sda21 && "
    "mkdir -p /usr/local/lib/etherpocket /usr/local/sbin /etc/polkit-1/rules.d")
put('/etc/polkit-1/rules.d/49-etherpocket-wifi.rules',
    (root / 'config/49-etherpocket-wifi.rules').read_bytes())
for name in ['etherpocket-wifi-prepare.py', 'etherpocket-modem.py', 'etherpocket-wlfw.py']:
    put('/usr/local/sbin/' + name, (root / 'scripts' / name).read_bytes(), '755')
for name in ['pd-mapper-downstream', 'tqftpserv-downstream']:
    put('/usr/local/sbin/' + name, (root / 'build' / name).read_bytes(), '755')
put('/usr/local/lib/etherpocket/qrtr-downstream-publish.so',
    (root / 'build/qrtr-downstream-publish.so').read_bytes(), '755')

units = {
    'etherpocket-wifi-prepare.service': '''[Unit]
Description=Prepare Qualcomm downstream Wi-Fi firmware services
After=local-fs.target systemd-udev-trigger.service
Before=pd-mapper.service tqftpserv.service rmtfs.service
[Service]
Type=oneshot
ExecStart=/usr/bin/python3 /usr/local/sbin/etherpocket-wifi-prepare.py
RemainAfterExit=yes
[Install]
WantedBy=multi-user.target
''',
    'etherpocket-modem.service': '''[Unit]
Description=Qualcomm modem subsystem for WLAN firmware
Requires=etherpocket-wifi-prepare.service rmtfs.service pd-mapper.service tqftpserv.service
After=etherpocket-wifi-prepare.service rmtfs.service pd-mapper.service tqftpserv.service
[Service]
ExecStart=/usr/bin/python3 /usr/local/sbin/etherpocket-modem.py
Restart=on-failure
RestartSec=5
[Install]
WantedBy=multi-user.target
''',
    'etherpocket-wlfw.service': '''[Unit]
Description=Qualcomm WLAN board data initialization
Requires=etherpocket-modem.service
After=etherpocket-modem.service
[Service]
ExecStart=/usr/bin/python3 -u /usr/local/sbin/etherpocket-wlfw.py
Restart=on-failure
RestartSec=5
[Install]
WantedBy=multi-user.target
''',
    'etherpocket-wifi.service': '''[Unit]
Description=Enable the native Qualcomm Wi-Fi driver
Requires=etherpocket-modem.service
Wants=etherpocket-wlfw.service NetworkManager.service
After=etherpocket-modem.service etherpocket-wlfw.service
[Service]
Type=oneshot
ExecStart=/usr/sbin/modprobe wlan
ExecStart=/bin/sh -c 'echo ON > /dev/wlan'
ExecStart=/usr/bin/test -d /sys/class/net/wlan0
ExecStop=-/usr/bin/nmcli --wait 10 device disconnect wlan0
ExecStop=/usr/sbin/modprobe -r wlan
RemainAfterExit=yes
TimeoutStartSec=120
[Install]
WantedBy=multi-user.target
''',
}
for name, data in units.items():
    put('/etc/systemd/system/' + name, data.encode())
for unit, exe in [('rmtfs', '/usr/bin/rmtfs -r -P'),
                  ('pd-mapper', '/usr/local/sbin/pd-mapper-downstream'),
                  ('tqftpserv', '/usr/local/sbin/tqftpserv-downstream')]:
    directory = '/etc/systemd/system/' + unit + '.service.d'
    run('mkdir -p ' + directory)
    data = f'''[Unit]
ConditionPathExists=
Requires=etherpocket-wifi-prepare.service qrtr-ns.service
After=etherpocket-wifi-prepare.service qrtr-ns.service
[Service]
ExecStart=
ExecStart={exe}
Environment=LD_PRELOAD=/usr/local/lib/etherpocket/qrtr-downstream-publish.so
'''
    put(directory + '/etherpocket.conf', data.encode())
run('systemctl daemon-reload && systemd-analyze verify ' +
    ' '.join('/etc/systemd/system/' + name for name in units))
run('systemctl enable ' + ' '.join(units) +
    ' qrtr-ns.service rmtfs.service pd-mapper.service tqftpserv.service NetworkManager.service')
print('Native Wi-Fi boot services installed and enabled.')
