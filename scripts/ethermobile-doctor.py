#!/usr/bin/env python3
"""Bounded, read-only cellular audit. Never powers radios or starts sessions.

No SIM identifiers, APNs, PINs, phone numbers or credentials are queried.
Connectivity is deliberately untested: Wi-Fi success cannot prove cellular access.
"""
import argparse
import datetime
import gzip
import json
import platform
import re
import shutil
import subprocess
from pathlib import Path


def redact(text):
    text = re.sub(r'(?i)(serialno=|serial(?: number)?[=:]\s*)\S+', r'\1[masked]', text)
    text = re.sub(r'(?i)((?:imei|imsi|iccid|meid|msisdn|password|pin|puk)\s*[=:]\s*)\S+', r'\1[masked]', text)
    text = re.sub(r'\b(?:[0-9a-fA-F]{2}:){5}[0-9a-fA-F]{2}\b', '[MAC masked]', text)
    return re.sub(r'(?<!\d)\d{14,22}(?!\d)', '[identifier masked]', text)


def read(path, limit=32768):
    try:
        return redact(Path(path).read_bytes()[:limit].replace(b'\0', b' ').decode(errors='replace').strip())
    except OSError:
        return None


def run(args, timeout=12):
    if not shutil.which(args[0]):
        return {'status': 'Missing', 'exit': None, 'output': 'Tool not installed'}
    try:
        p = subprocess.run(args, capture_output=True, timeout=timeout)
        return {'status': 'Working' if p.returncode == 0 else 'Unknown', 'exit': p.returncode,
                'output': redact((p.stdout + p.stderr).decode(errors='replace')[-32768:])}
    except (OSError, subprocess.TimeoutExpired):
        return {'status': 'Unknown', 'exit': None, 'output': 'Query failed or timed out'}


def kernel_config():
    try:
        data = gzip.decompress(Path('/proc/config.gz').read_bytes()).decode()
    except (OSError, EOFError):
        data = read('/boot/config-' + platform.release()) or ''
    selected = {}
    for line in data.splitlines():
        if re.search(r'QRTR|QMI|RMNET|IPA|MHI|WWAN|SMD|GLINK|REMOTEPROC|MSM_SUBSYSTEM', line):
            if line.startswith('CONFIG_') and '=' in line:
                key, value = line.split('=', 1)
                selected[key] = value
            elif line.startswith('# CONFIG_') and line.endswith(' is not set'):
                selected[line.split()[1]] = 'n'
    return selected


def stages(e):
    def item(name, status, evidence):
        return {'stage': name, 'status': status, 'evidence': evidence}
    q = e['qmi']
    transport = bool(q.get('revision', {}).get('exit') == 0)
    interfaces = e['cellular_interfaces']
    card = q.get('card', {}).get('output', '')
    mode = q.get('mode', {}).get('output', '')
    registration = q.get('registration', {}).get('output', '')
    packet = q.get('packet', {}).get('output', '')
    return [
        item('Modem hardware discovery', 'Working' if transport else 'Unknown', e['hardware']),
        item('Kernel support', 'Partially working' if transport and not interfaces else 'Working' if transport and interfaces else 'Unknown', e['kernel']),
        item('Firmware verification', 'Partially working' if transport else 'Unknown', {'revision': q.get('revision'), 'ipa_files': e['ipa_firmware'], 'note': 'Firmware response verifies control firmware; filenames alone do not verify the packet path.'}),
        item('Modem subsystem boot', 'Working' if any(s['name'] == 'modem' and s['state'] == 'ONLINE' for s in e['subsystems']) else 'Unknown', e['subsystems']),
        item('Control transport', 'Working' if transport else 'Unknown', {'qrtr': e['qrtr'], 'queries': q}),
        item('SIM detection', 'Working' if "Card state: 'present'" in card else 'Blocked' if 'no-atr-received' in card else 'Unknown', {'result': card, 'note': 'No ATR is not proof of an absent SIM. Zero uninitialized retry counters are not valid remaining attempts.'}),
        item('Radio power state', 'Working' if "Mode: 'online'" in mode else 'Blocked' if mode else 'Unknown', mode),
        item('Network registration', 'Working' if "Registration state: 'registered'" in registration else 'Blocked' if registration else 'Unknown', {'registration': registration, 'system_info': q.get('system', {}), 'note': 'A readable SIM and received signal do not establish carrier registration. Check explicit reject reasons in system_info.'}),
        item('Packet data capability', 'Partially working' if transport else 'Unknown', {'capabilities': q.get('capabilities'), 'session': packet, 'note': 'Advertised technology is not tested network support.'}),
        item('IP interface availability', 'Partially working' if interfaces else 'Blocked', {'interfaces': interfaces, 'links': e['links'], 'addresses': e['addresses'], 'routes': e['routes']}),
        item('Cellular DNS configuration', 'Unknown' if interfaces else 'Blocked', 'Not verified against a cellular interface; host resolv.conf may belong to Wi-Fi.'),
        item('End-to-end cellular connectivity', 'Unknown' if interfaces else 'Blocked', 'Not tested. Requires a SIM, established bearer, cellular IP/route and interface-bound DNS and external checks. No Wi-Fi fallback test is accepted.'),
    ]


def audit():
    if platform.system() != 'Linux':
        raise SystemExit('Run on the actual Linux phone; this host is not modem evidence.')
    links = list(Path('/sys/class/net').glob('*'))
    qrtr = run(['qrtr-lookup'])
    # Query only a node advertising DMS, NAS, WDS and UIM. Do not assume node 0.
    services = {}
    for line in qrtr['output'].splitlines():
        cols = line.split()
        if len(cols) >= 5 and all(x.isdigit() for x in cols[:5]):
            services.setdefault(int(cols[3]), set()).add(int(cols[0]))
    candidates = [node for node, svc in services.items() if {1, 2, 3, 11} <= svc]
    qmi = {}
    if candidates:
        node = min(candidates)
        for name, option in [('model', 'dms-get-model'), ('revision', 'dms-get-revision'), ('capabilities', 'dms-get-capabilities'), ('mode', 'dms-get-operating-mode'), ('card', 'uim-get-card-status'), ('registration', 'nas-get-serving-system'), ('system', 'nas-get-system-info'), ('packet', 'wds-get-packet-service-status'), ('signal', 'nas-get-signal-strength')]:
            qmi[name] = run(['qmicli', '-d', 'qrtr://' + str(node), '--' + option])
    subsystems = [{'name': read(p/'name'), 'state': read(p/'state')} for p in Path('/sys/bus/msm_subsys/devices').glob('*')]
    e = {
        'schema': 1, 'time_utc': datetime.datetime.now(datetime.timezone.utc).isoformat(),
        'read_only': True, 'hardware': {'kernel': platform.release(), 'architecture': platform.machine(), 'machine': read('/sys/devices/soc0/machine'), 'soc_id': read('/sys/devices/soc0/soc_id'), 'device_tree_model': read('/proc/device-tree/model'), 'cmdline': read('/proc/cmdline')},
        'kernel': kernel_config(), 'modules': run(['lsmod']), 'qrtr': qrtr, 'qmi': qmi,
        'subsystems': subsystems, 'ipa_firmware': [str(p) for pattern in ('ipa_fws*', 'ipa_uc*') for p in Path('/lib/firmware').glob(pattern)],
        'firmware': [p.name for p in Path('/lib/firmware').glob('modem.*')],
        'endpoints': sorted({str(p) for pattern in ('cdc-wdm*', 'wwan*', 'smd*', 'mhi*', 'ipa*', 'subsys*') for p in Path('/dev').glob(pattern)}),
        'cellular_interfaces': [p.name for p in links if re.match(r'^(rmnet|wwan|mhi|qmi)', p.name)],
        'links': run(['ip', '-br', 'link']), 'addresses': run(['ip', '-br', 'address']), 'routes': run(['ip', 'route']), 'routes6': run(['ip', '-6', 'route']),
        'rfkill': run(['rfkill', 'list']), 'modems': run(['mmcli', '-L']),
        'packages': run(['dpkg-query', '-W', '-f=${Package} ${Version}\n', 'modemmanager', 'network-manager', 'libqmi-utils', 'libmbim-utils', 'libqrtr1', 'ofono', 'dbus', 'udev', 'rmtfs', 'qrtr-tools', 'tqftpserv', 'protection-domain-mapper']),
        'services': run(['systemctl', 'is-active', 'ModemManager', 'NetworkManager', 'dbus', 'systemd-udevd', 'qrtr-ns', 'rmtfs', 'pd-mapper', 'tqftpserv', 'etherpocket-modem', 'bluetooth', 'ssh']),
        'modemmanager_log': run(['journalctl', '-b', '-u', 'ModemManager', '--no-pager', '-n', '60']),
        'firmware_services': run(['systemctl', 'cat', 'etherpocket-modem', 'rmtfs', 'pd-mapper', 'tqftpserv']),
    }
    # Retain only relevant kernel lines and redact before the report leaves memory.
    log = run(['dmesg'])
    e['kernel_log'] = '\n'.join(line for line in log['output'].splitlines() if re.search(r'modem|rmnet|ipa|qrtr|firmware|mhi|glink', line, re.I))[-16000:]
    e['stages'] = stages(e)
    return e


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path)
    args = parser.parse_args()
    data = json.dumps(audit(), indent=2) + '\n'
    if args.output:
        # Avoid following existing symlinks and keep local diagnostic evidence private.
        import os
        fd = os.open(args.output, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        with os.fdopen(fd, 'w') as stream:
            stream.write(data)
    else:
        print(data, end='')
