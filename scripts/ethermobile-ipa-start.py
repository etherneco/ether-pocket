#!/usr/bin/python3
"""Initialize the verified GM1920 IPA firmware once per boot."""
import fcntl
import hashlib
import json
import os
from pathlib import Path
import platform
import subprocess
import time


def wait_for(predicate, description):
    deadline = time.monotonic() + 60
    while not predicate():
        if time.monotonic() >= deadline:
            raise RuntimeError('Timed out waiting for ' + description)
        time.sleep(0.5)


def modem_online():
    return any((p / 'name').read_text().strip() == 'modem'
               and (p / 'state').read_text().strip() == 'ONLINE'
               for p in Path('/sys/bus/msm_subsys/devices').glob('*'))


def main():
    if Path('/etc/etherpocket/disk-identity').read_text().strip() != 'GM1920-548cb338-mobian-sda21':
        raise RuntimeError('Unsupported disk identity')
    if platform.release() != '4.14.117-perf' or Path('/proc/device-tree/model').read_bytes().rstrip(b'\0') != b'SDX50M MTP 18827 15':
        raise RuntimeError('Unsupported board or kernel')
    with open('/run/ethermobile-ipa-start.lock', 'w') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        interface = Path('/sys/class/net/rmnet_ipa0')
        if not interface.exists():
            wait_for(lambda: Path('/dev/ipa').is_char_device() and modem_online(), 'modem and IPA device')
            manifest = json.loads(Path('/usr/local/lib/ethermobile/ipa-firmware.json').read_text())
            for name, meta in manifest.items():
                if Path(name).name != name:
                    raise RuntimeError('Invalid firmware filename')
                payload = (Path('/lib/firmware') / name).read_bytes()
                if len(payload) != meta['bytes'] or hashlib.sha256(payload).hexdigest() != meta['sha256']:
                    raise RuntimeError('IPA firmware verification failed: ' + name)
            # Share the marker with the existing manual initializer. Never repeat
            # the firmware write, including after a failed or interrupted start.
            marker = os.open('/run/ethermobile-ipa-attempted', os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
            os.close(marker)
            fd = os.open('/dev/ipa', os.O_WRONLY | os.O_NOFOLLOW)
            try:
                if os.write(fd, b'1') != 1:
                    raise RuntimeError('Short IPA startup write')
            finally:
                os.close(fd)
            print('IPA firmware initialization requested once for this boot', flush=True)
            wait_for(interface.exists, 'rmnet_ipa0')
        if (interface / 'type').read_text().strip() != '519':
            raise RuntimeError('Unexpected IPA interface type')
        subprocess.run(['udevadm', 'trigger', '--action=change', str(interface)], check=True, timeout=15)
        subprocess.run(['udevadm', 'settle', '--timeout=10'], check=True, timeout=15)
        print('IPA network port ready: rmnet_ipa0', flush=True)


if __name__ == '__main__':
    main()
