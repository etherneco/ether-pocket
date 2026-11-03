#!/usr/bin/env python3
"""Read-only Bluetooth evidence collection. No firmware, power or driver writes."""
import argparse
import datetime
import gzip
import json
import platform
from pathlib import Path
import re
import shutil
import subprocess


def read(path, limit=16384):
    try:
        return Path(path).read_bytes()[:limit].replace(b'\0', b' ').decode(errors='replace').strip()
    except OSError:
        return None


def command(args):
    if not shutil.which(args[0]):
        return {'status': 'Missing', 'command': args, 'output': 'Tool not installed'}
    try:
        p = subprocess.run(args, capture_output=True, timeout=12)
        return {'status': 'Working' if p.returncode == 0 else 'Unknown',
                'command': args, 'exit': p.returncode,
                'output': (p.stdout + p.stderr)[:24000].decode(errors='replace')}
    except (OSError, subprocess.TimeoutExpired) as e:
        return {'status': 'Unknown', 'command': args, 'output': str(e)}


def classify(config, hci, bluez, rfkill, dt=None, uart_paths=None, firmware=None, dbus=None, external=None):
    dt, uart_paths, firmware, dbus = dt or [], uart_paths or [], firmware or [], dbus or {}
    uart = config.get('CONFIG_BT_HCIUART', 'unknown')
    external = external or {}
    native_uart = bool(external.get('loaded') and hci)
    return [
        {'stage': 'Bluetooth hardware', 'status': 'Working' if hci else 'Partially working' if dt else 'Unknown',
         'evidence': dt or 'No Bluetooth device-tree node found; USB and ACPI controllers may still exist.',
         'repair': 'Device-tree compatibility identifies the declared platform, not a verified ROM revision.'},
        {'stage': 'Controller transport', 'status': 'Working' if hci else 'Partially working' if uart_paths else 'Unknown',
         'evidence': uart_paths, 'repair': 'Verify UART binding and board power sequence. Do not assume USB transport.'},
        {'stage': 'Bluetooth kernel core', 'status': 'Working' if hci else 'Partially working' if config.get('CONFIG_BT') in ('y', 'm') else 'Missing' if config.get('CONFIG_BT') == 'n' else 'Unknown',
         'evidence': 'CONFIG_BT=' + config.get('CONFIG_BT', 'unknown'), 'repair': 'Enabled kernel core alone does not register a controller.'},
        {'stage': 'Kernel transport', 'status': 'Working' if native_uart else 'Missing' if uart == 'n' else 'Unknown' if uart == 'unknown' else 'Partially working',
         'evidence': external if native_uart else 'CONFIG_BT_HCIUART=' + uart,
         'repair': 'For a UART controller, build against the exact running kernel and verify ABI, protocol and firmware compatibility before loading.'},
        {'stage': 'Firmware availability', 'status': 'Partially working' if native_uart and external.get('runtime') else 'Unknown' if firmware else 'Missing',
         'evidence': 'Controller-resident firmware responded to validated HCI requests. No host TLV was uploaded. ROM/patch evidence: ' + str(external.get('runtime')) if native_uart and external.get('runtime') else firmware or 'No candidates found in inspected Linux firmware directories. Other names and Android partitions require separate investigation.',
         'repair': 'Identify controller ROM and required filenames before selecting firmware. Filename presence does not establish compatibility.'},
        {'stage': 'Bluetooth power', 'status': 'Blocked' if any(x['soft'] == '1' or x['hard'] == '1' for x in rfkill) else 'Working' if rfkill else 'Unknown',
         'evidence': rfkill, 'repair': 'Software unblock requires an explicit action; hardware block cannot be cleared in software.'},
        {'stage': 'Controller initialization', 'status': 'Partially working' if hci else 'Blocked',
         'evidence': 'HCI registered; powered operation still needs verification.' if hci else 'No HCI registered; no firmware load success established.',
         'repair': 'Inspect protocol support and kernel logs before any power or shared-subsystem reset.'},
        {'stage': 'HCI registration', 'status': 'Working' if hci else 'Missing',
         'evidence': ', '.join(hci) or 'No controller registered in /sys/class/bluetooth',
         'repair': 'Investigate transport and vendor initialization before restarting BlueZ.'},
        {'stage': 'BlueZ service', 'status': 'Working' if bluez.get('output', '').strip() == 'active' else 'Unknown',
         'evidence': bluez.get('output', ''), 'repair': 'Inspect bounded service journal; restarting interrupts all Bluetooth connections.'},
        {'stage': 'D-Bus access', 'status': dbus.get('status', 'Unknown'),
         'evidence': dbus.get('output', 'Not inspected'), 'repair': 'Check system bus permissions; graphical application must run as the desktop user.'},
        {'stage': 'Discovery capability', 'status': 'Unknown' if hci else 'Blocked',
         'evidence': 'Adapter capabilities and powered state must be checked through BlueZ.', 'repair': 'Use Add Device only when a powered adapter is available.'},
        {'stage': 'Discovery test', 'status': 'Blocked' if not hci else 'Unknown',
         'evidence': 'Not performed: read-only audit. Use an explicitly initiated, bounded scan when a powered adapter exists.', 'repair': 'Resolve preceding stages first.'}]


def audit():
    config_text = ''
    config_source = None
    for path in ['/proc/config.gz', '/boot/config-' + platform.release()]:
        try:
            config_text = gzip.open(path, 'rt').read() if path.endswith('.gz') else Path(path).read_text()
            config_source = path
            break
        except OSError:
            pass
    config = {}
    for line in config_text.splitlines():
        m = re.match(r'(CONFIG_\w+)=(.*)', line) or re.match(r'# (CONFIG_\w+) is not set', line)
        if m and re.search(r'BT|SERIAL.*(MSM|QCOM)|SERIAL_DEV|UHID|HID_GENERIC|MODVERSIONS|MODULE_SIG', m[1]):
            config[m[1]] = m[2] if m.lastindex == 2 else 'n'
    rfkill = []
    for p in Path('/sys/class/rfkill').glob('rfkill*'):
        if read(p/'type') == 'bluetooth':
            rfkill.append(dict(path=str(p), **{k: read(p/k) for k in ['name', 'type', 'soft', 'hard']}))
    dt = []
    root = Path('/sys/firmware/devicetree/base')
    if root.exists():
        for p in root.rglob('*'):
            if p.is_dir() and re.search(r'bluetooth|bt_wcn|btpower', p.name, re.I):
                dt.append({'path': str(p), **{k: read(p/k) for k in ['compatible', 'status', 'reg', 'qcom,bt-chip-pwd']}})
    firmware = []
    for base in ['/lib/firmware', '/vendor/firmware', '/vendor/firmware_mnt/image']:
        p = Path(base)
        if p.exists():
            for f in p.rglob('*'):
                if f.is_file() and re.search(r'(btfw|btnv|crbt|crnv|rampatch|nvm_|cherokee)', f.name, re.I):
                    firmware.append(str(f))
                    if len(firmware) >= 200:
                        break
    hci = [p.name for p in Path('/sys/class/bluetooth').glob('hci*')]
    bluez = command(['systemctl', 'is-active', 'bluetooth'])
    dbus = command(['busctl', '--system', 'tree', 'org.bluez'])
    external = {'loaded': Path('/sys/module/ether_hci_uart').exists(),
                'runtime': None, 'kernel_uart_config': config.get('CONFIG_BT_HCIUART', 'unknown')}
    manifest = read('/run/etherbluetooth/controller.json')
    if manifest:
        try:
            external['runtime'] = json.loads(manifest)
        except ValueError:
            pass
    logs = command(['journalctl', '-k', '-b', '-n', '1500', '--no-pager', '-o', 'cat'])
    logs['output'] = '\n'.join(line for line in logs['output'].splitlines() if re.search(r'bluetooth|bt_power|btpower|cherokee|hci|ttyHS|wcn399', line, re.I))[-16000:]
    return {'schema': 1, 'time': datetime.datetime.now(datetime.timezone.utc).isoformat(),
            'system': platform.uname()._asdict(), 'os': read('/etc/os-release'),
            'device_tree': dt, 'model': read(root/'model'), 'compatible': read(root/'compatible'),
            'config_source': config_source, 'config': config, 'hci': hci, 'rfkill': rfkill,
            'uart': [str(p) for pattern in ['ttyHS*', 'ttyMSM*'] for p in Path('/dev').glob(pattern)],
            'firmware_candidates': firmware,
            'firmware_compatibility': 'Unknown: filenames alone do not identify controller ROM or prove a successful load.',
            'bluez': bluez, 'kernel_log': logs,
            'tools': {name: shutil.which(name) for name in ['bluetoothctl', 'btattach', 'hciattach', 'rfkill', 'btmon', 'modinfo', 'pactl', 'wpctl']},
            'checks': classify(config, hci, bluez, rfkill, dt, [str(p) for p in Path('/dev').glob('ttyHS*')], firmware, dbus, external),
            'external_transport': external,
            'bluez_objects': dbus,
            'service_log': command(['journalctl', '-u', 'bluetooth', '-b', '-n', '65', '--no-pager']),
            'packages': command(['dpkg-query', '-W', 'bluez', 'firmware-atheros', 'pipewire', 'wireplumber', 'libspa-0.2-bluetooth']),
            'modules': command(['lsmod']),
            'discovery_performed': False}


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path)
    args = parser.parse_args()
    data = json.dumps(audit(), indent=2)
    if args.output:
        import os
        fd = os.open(args.output, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
        os.fchmod(fd, 0o600)
        with os.fdopen(fd, 'w') as stream:
            stream.write(data + '\n')
    else:
        print(data)
