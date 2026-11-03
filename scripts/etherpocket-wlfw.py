#!/usr/bin/python3
"""Provide board data to the downstream Qualcomm WLAN firmware over QMI."""
import ctypes as C
from pathlib import Path
import struct
import subprocess
import time

lib = C.CDLL('libqrtr.so.1', use_errno=True)
lib.qrtr_sendto.argtypes = [C.c_int, C.c_uint32, C.c_uint32, C.c_void_p, C.c_uint]
lib.qrtr_recvfrom.argtypes = [C.c_int, C.c_void_p, C.c_uint, C.POINTER(C.c_uint32), C.POINTER(C.c_uint32)]

def tlv(kind, data):
    return struct.pack('<BH', kind, len(data)) + data

def fields(data):
    result = {}
    while data:
        kind, length = struct.unpack_from('<BH', data)
        if len(data) < length + 3:
            raise ValueError('Truncated QMI TLV')
        result[kind] = data[3:3 + length]
        data = data[3 + length:]
    return result

deadline = time.monotonic() + 90
while True:
    rows = subprocess.run(['qrtr-lookup'], capture_output=True, text=True, timeout=5).stdout.splitlines()
    matches = [row.split() for row in rows if row.split()[:1] == ['69']]
    if matches:
        node, port = map(int, matches[0][3:5])
        break
    if time.monotonic() > deadline:
        raise TimeoutError('WLAN QMI service did not appear')
    time.sleep(1)
fd = lib.qrtr_open(0)
if fd < 0:
    raise OSError(C.get_errno(), 'qrtr_open')
transaction = 0

def request(message, payload=b''):
    global transaction
    transaction += 1
    packet = struct.pack('<BHHH', 0, transaction, message, len(payload)) + payload
    if lib.qrtr_sendto(fd, node, port, packet, len(packet)) < 0:
        raise OSError(C.get_errno(), 'qrtr_sendto')
    end = time.monotonic() + 15
    while time.monotonic() < end:
        buf = C.create_string_buffer(65536)
        source, source_port = C.c_uint32(), C.c_uint32()
        size = lib.qrtr_recvfrom(fd, buf, len(buf), C.byref(source), C.byref(source_port))
        if size < 7:
            continue
        flag, txn, msg, length = struct.unpack_from('<BHHH', buf.raw)
        if flag != 2 or txn != transaction or msg != message:
            continue
        reply = fields(buf.raw[7:7 + length])
        if reply.get(2) != b'\0\0\0\0':
            raise RuntimeError(f'QMI {message:#x} rejected: {reply.get(2)!r}')
        return reply
    raise TimeoutError(f'QMI {message:#x}')

try:
    # Client 0 is the firmware service daemon; the kernel uses client 1.
    status = request(0x20, tlv(0x15, struct.pack('<I', 0)) + tlv(0x10, b'\1'))
    cap = request(0x24)
    board = struct.unpack('<I', cap.get(0x11, struct.pack('<I', 0xff)))[0]
    print(f'WLAN board ID: {board:#x}', flush=True)
    firmware = Path('/lib/firmware')
    name = 'bdwlan.bin' if board == 0xff else f'bdwlan.b{board:02x}'
    path = firmware / name
    if not path.is_file():
        raise FileNotFoundError(path)
    data = path.read_bytes()
    for segment, offset in enumerate(range(0, len(data), 6144)):
        chunk = data[offset:offset + 6144]
        payload = tlv(1, b'\1') + tlv(0x10, struct.pack('<I', 0))
        payload += tlv(0x11, struct.pack('<I', len(data))) + tlv(0x12, struct.pack('<I', segment))
        payload += tlv(0x13, struct.pack('<H', len(chunk)) + chunk)
        payload += tlv(0x14, bytes([offset + len(chunk) == len(data)]))
        request(0x25, payload)
    request(0x26, tlv(1, b'\0'))
    print('WLAN board data and calibration report accepted.', flush=True)
    # Keep the firmware daemon client alive for the active firmware session.
    while True:
        time.sleep(3600)
finally:
    lib.qrtr_close(fd)
