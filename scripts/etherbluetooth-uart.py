#!/usr/bin/env python3
"""Board-specific Qualcomm UART initialization and native H4 attachment.

Only the inspected SM8150 bt_wcn3990 + GENI ttyHS0 board is supported.
Firmware already resident on the controller is used; no TLV is uploaded.
"""
import argparse
import gzip
import hashlib
import array
import fcntl
import json
import os
from pathlib import Path
import select
import signal
import socket
import struct
import subprocess
import termios
import time
import threading

from importlib.util import module_from_spec, spec_from_file_location
spec = spec_from_file_location('uart_probe', Path(__file__).with_name('etherbluetooth-uart-probe.py'))
probe = module_from_spec(spec)
spec.loader.exec_module(probe)


class HciUart:
    def __init__(self, fd):
        self.fd = fd
        self.buffer = bytearray()

    def event(self, timeout=3):
        end = time.monotonic() + timeout
        while time.monotonic() < end:
            while self.buffer and self.buffer[0] != 4:
                byte = self.buffer.pop(0)
                if byte == 0xfd:  # Qualcomm in-band sleep wake indication
                    os.write(self.fd, b'\xfc')
                elif byte not in (0xfc, 0xfe):
                    raise RuntimeError('Unexpected non-H4 event byte 0x%02x during initialization' % byte)
            if len(self.buffer) >= 3 and len(self.buffer) >= 3 + self.buffer[2]:
                size = 3 + self.buffer[2]
                data = bytes(self.buffer[:size]); del self.buffer[:size]
                return data
            if select.select([self.fd], [], [], max(0, end - time.monotonic()))[0]:
                self.buffer.extend(os.read(self.fd, 1024))
        raise TimeoutError('Controller did not return the expected HCI event')

    def command(self, opcode, payload=b'', vendor=False):
        packet = b'\x01' + struct.pack('<HB', opcode, len(payload)) + payload
        if os.write(self.fd, packet) != len(packet):
            raise RuntimeError('Incomplete HCI command write')
        events = []
        until = time.monotonic() + 4
        while time.monotonic() < until:
            e = self.event(max(.01, until - time.monotonic())); events.append(e)
            if vendor and e[1] == 0xff:
                return events
            if e[1] == 0x0e and len(e) >= 7 and struct.unpack_from('<H', e, 4)[0] == opcode:
                if e[6] != 0:
                    raise RuntimeError('HCI command 0x%04x rejected, status %d' % (opcode, e[6]))
                if vendor and not any(x[1] == 0xff for x in events):
                    continue
                return events
        raise TimeoutError('No matching command completion')


def open_uart(speed=termios.B115200):
    fd = os.open('/dev/ttyHS0', os.O_RDWR | os.O_NOCTTY | os.O_NONBLOCK)
    fcntl.ioctl(fd, termios.TIOCEXCL)
    fcntl.ioctl(fd, 0x544d)
    probe.configure(fd, speed, True)
    return fd


def identity(address_file):
    if not address_file.exists():
        address_file.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
        # A stable locally configured address, never presented as a factory ID.
        address = bytes([0x02]) + os.urandom(5)
        fd = os.open(address_file, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        with os.fdopen(fd, 'w') as out:
            out.write(':'.join('%02X' % b for b in address) + '\n')
    text = address_file.read_text().strip()
    address = bytes.fromhex(text.replace(':', ''))
    if len(address) != 6 or address == bytes(6) or address == b'\xff' * 6:
        raise ValueError('Invalid configured controller address')
    return address


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--apply', action='store_true')
    parser.add_argument('--check-kernel', action='store_true')
    parser.add_argument('--speed', type=int, choices=[115200, 3000000], default=3000000)
    parser.add_argument('--duration', type=int, default=0, help='Stop after this many seconds; 0 means service lifetime')
    args = parser.parse_args()
    if os.uname().release != '4.14.117-perf' or os.uname().version != '#6 SMP PREEMPT Thu Oct 15 02:24:35 BST 2026':
        raise RuntimeError('This kernel build has not been validated')
    if hashlib.sha256(gzip.open('/proc/config.gz', 'rb').read()).hexdigest() != '7f2a8e023daf9912f45086a00b699d7cefaf7746718c24d952c2a4329868a01b':
        raise RuntimeError('Kernel configuration differs from the validated module build')
    if args.check_kernel:
        print('Validated running kernel build and configuration.')
        return
    if not args.apply or os.geteuid() != 0:
        raise SystemExit('This hardware initializer requires root and explicit --apply.')
    os.umask(0o077)
    runtime = Path('/run/etherbluetooth'); runtime.mkdir(mode=0o755, exist_ok=True)
    runtime.chmod(0o755)
    lock = (runtime/'uart.lock').open('w')
    fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
    node = Path('/sys/firmware/devicetree/base/vendor/bt_wcn3990/compatible')
    if node.read_bytes().rstrip(b'\0') != b'qca,wcn3990':
        raise RuntimeError('This board has not been validated')
    if list(Path('/sys/class/bluetooth').glob('hci*')):
        raise RuntimeError('Controller already attached; refusing competing initializer')
    # A bounded boot/version probe has been verified on this exact board.
    subprocess.run(['/usr/bin/python3', str(Path(__file__).with_name('etherbluetooth-uart-probe.py')), '--apply'], check=True, timeout=12)
    fd = open_uart()
    attached = False
    stop = threading.Event()
    def finish(*_):
        stop.set()
    signal.signal(signal.SIGTERM, finish)
    signal.signal(signal.SIGINT, finish)
    try:
        uart = HciUart(fd)
        version_events = uart.command(0xfc00, b'\x19', vendor=True)
        event = next(e for e in version_events if e[1] == 0xff)
        if len(event) != 17 or event[3:5] != b'\x00\x02':
            raise RuntimeError('Unknown version response; no vendor configuration applied')
        product, patch, rom, soc = struct.unpack_from('<IHHI', event, 5)
        if (product, rom, soc) != (0x0a, 0x1001, 0x40010224):
            raise RuntimeError('Unvalidated controller revision; refusing setup')
        address = identity(Path('/var/lib/etherbluetooth/controller-address'))
        uart.command(0xfc0b, b'\x01\x02\x06' + address[::-1], vendor=True)
        # Switch both ends using the documented QCA opcode and baud index 14.
        if args.speed == 3000000:
            probe.configure(fd, termios.B115200, False)
            os.write(fd, bytes.fromhex('01 48 fc 01 0e'))
            probe.drain(fd)
            time.sleep(.3)
            probe.configure(fd, termios.B3000000, True)
            # Consume the vendor baud event/command completion before H4 attach.
            time.sleep(.1)
            while select.select([fd], [], [], .05)[0]:
                os.read(fd, 1024)
        uart.buffer.clear()
        uart.command(0x0c03)  # Standard HCI reset, configuration stays in RAM.
        version = uart.command(0x1001)[-1]
        actual = uart.command(0x1009)[-1]
        if actual[7:13] != address[::-1]:
            raise RuntimeError('Controller did not retain the configured unique address')
        print(json.dumps({'stage':'uart-ready','soc':'0x%08x'%soc,'rom':'0x%04x'%rom,'patch':'0x%04x'%patch,'speed':args.speed,'address_source':'persistent locally configured address','hci_version':version[7]}),flush=True)
        fcntl.ioctl(fd, 0x5423, array.array('i', [15]))
        fcntl.ioctl(fd, 0x400455c8, 8)  # HCIUARTSETPROTO: Qualcomm H4 + IBS
        attached = True
        manifest = runtime/'controller.json'
        manifest.write_text(json.dumps({'schema':1,'transport':'GENI UART / native QCA H4 framing','speed':args.speed,'soc':soc,'rom':rom,'patch':patch,'host_firmware_uploaded':False,'address_source':'local configuration','host_ibs_sleep_enabled':False}))
        manifest.chmod(0o644)
        if os.environ.get('NOTIFY_SOCKET'):
            target = os.environ['NOTIFY_SOCKET']
            with socket.socket(socket.AF_UNIX, socket.SOCK_DGRAM) as notifier:
                notifier.connect('\0'+target[1:] if target.startswith('@') else target)
                notifier.send(b'READY=1\nSTATUS=Qualcomm UART attached at 3000000 baud; native Linux HCI')
        print('Native Qualcomm UART attached; waiting for BlueZ. No background scan.', flush=True)
        stop.wait(args.duration if args.duration else None)
    finally:
        if attached:
            fcntl.ioctl(fd, 0x5423, array.array('i', [0]))
        fcntl.ioctl(fd, 0x544e)
        os.close(fd)
        (runtime/'controller.json').unlink(missing_ok=True)


if __name__ == '__main__':
    main()
