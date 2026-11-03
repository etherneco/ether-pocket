#!/usr/bin/env python3
"""Bounded WCN3990 UART boot/version probe; no firmware writes or HCI attach.

Requires explicit --apply. Power uses the existing Bluetooth rfkill driver.
The pulse sequence follows upstream Linux v4.19 hci_qca.c. No WLAN reset.
"""
import argparse
import array
import fcntl
import json
import os
from pathlib import Path
import select
import subprocess
import termios
import time


def configure(fd, speed, flow=False):
    a = termios.tcgetattr(fd)
    a[0] = 0
    a[1] = 0
    a[2] = termios.CLOCAL | termios.CREAD | termios.CS8 | (termios.CRTSCTS if flow else 0)
    a[3] = 0
    a[4] = a[5] = speed
    a[6][termios.VMIN] = 0
    a[6][termios.VTIME] = 0
    termios.tcsetattr(fd, termios.TCSANOW, a)


def drain(fd):
    until = time.monotonic() + 2
    while time.monotonic() < until:
        queued = array.array('i', [0])
        fcntl.ioctl(fd, termios.TIOCOUTQ, queued, True)
        if not queued[0]:
            time.sleep(.02)
            return
        time.sleep(.01)
    raise TimeoutError('UART transmit queue did not drain')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--apply', action='store_true')
    args = parser.parse_args()
    if not args.apply:
        raise SystemExit('Use --apply to power Bluetooth, send the documented boot pulses and read its ROM version.')
    if os.geteuid() != 0:
        raise SystemExit('Root is required for this hardware probe.')
    assert Path('/sys/firmware/devicetree/base/vendor/bt_wcn3990/compatible').read_bytes().rstrip(b'\0') == b'qca,wcn3990'
    assert not list(Path('/sys/class/bluetooth').glob('hci*')), 'Controller already exists; refusing a second initializer'
    subprocess.run(['rfkill', 'unblock', 'bluetooth'], check=True, timeout=5)
    fd = os.open('/dev/ttyHS0', os.O_RDWR | os.O_NOCTTY | os.O_NONBLOCK)
    clock = False
    try:
        fcntl.ioctl(fd, termios.TIOCEXCL)
        fcntl.ioctl(fd, 0x544d)  # TIOCPMGET, matched vendor GENI ABI
        clock = True
        configure(fd, termios.B2400)
        termios.tcflush(fd, termios.TCIOFLUSH)
        os.write(fd, b'\xc0')
        drain(fd)
        configure(fd, termios.B115200)
        os.write(fd, b'\xfc')
        drain(fd)
        time.sleep(.15)
        fcntl.ioctl(fd, 0x544e)
        clock = False
        os.close(fd)
        fd = os.open('/dev/ttyHS0', os.O_RDWR | os.O_NOCTTY | os.O_NONBLOCK)
        fcntl.ioctl(fd, termios.TIOCEXCL)
        fcntl.ioctl(fd, 0x544d)
        clock = True
        configure(fd, termios.B115200, True)
        fcntl.ioctl(fd, termios.TIOCMBIS, array.array('i', [termios.TIOCM_RTS]))
        termios.tcflush(fd, termios.TCIOFLUSH)
        os.write(fd, bytes.fromhex('01 00 fc 01 19'))
        response = bytearray()
        until = time.monotonic() + 4
        while time.monotonic() < until and len(response) < 512:
            if select.select([fd], [], [], .2)[0]:
                response.extend(os.read(fd, 512 - len(response)))
        print(json.dumps({'command': 'Qualcomm EDL version request', 'uart': '/dev/ttyHS0', 'response_hex': response.hex(' '), 'bytes': len(response)}, indent=2))
    finally:
        if clock:
            fcntl.ioctl(fd, 0x544e)
        os.close(fd)


if __name__ == '__main__':
    main()
