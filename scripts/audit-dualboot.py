#!/usr/bin/env python3
"""Read-only GM1920 GPT audit and redundant-table backup. Never writes phone disks."""
import base64
import argparse
import hashlib
import json
from pathlib import Path
import struct
import subprocess
import uuid
import zlib

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / 'recovery/dualboot-audit'
SSH = ['ssh', '-i', str(ROOT / 'build/etherpocket_ed25519'), '-o',
       'UserKnownHostsFile=' + str(ROOT / 'build/mobian-known-hosts'),
       '-o', 'BatchMode=yes', '-o', 'ConnectTimeout=6', 'root@10.77.0.2']
REMOTE = r'''
import base64, json, os
from pathlib import Path
assert 'etherpocket.ramboot=1' in Path('/proc/cmdline').read_text()
assert 'androidboot.serialno=548cb338' in Path('/proc/cmdline').read_text().split()
result = {}
for name in ['sda','sdb','sdc','sdd','sde','sdf']:
    sys = Path('/sys/class/block') / name
    sector = int((sys/'queue/logical_block_size').read_text())
    size = int((sys/'size').read_text()) * 512
    with open('/dev/'+name, 'rb', buffering=0) as f:
        head = f.read(128*1024)
        f.seek(size - 128*1024)
        tail = f.read(128*1024)
    result[name] = dict(size=size, sector=sector,
        head=base64.b64encode(head).decode(), tail=base64.b64encode(tail).decode())
print(json.dumps(result))
'''


def header(data, sector, expected_lba):
    if data[:8] != b'EFI PART':
        raise ValueError('Missing GPT signature')
    length, checksum = struct.unpack_from('<II', data, 12)
    if not 92 <= length <= sector:
        raise ValueError('Invalid GPT header length')
    checked = bytearray(data[:length])
    checked[16:20] = bytes(4)
    if zlib.crc32(checked) != checksum:
        raise ValueError('GPT header CRC mismatch')
    current, backup, first, last = struct.unpack_from('<QQQQ', data, 24)
    entries_lba, count, entry_size, entries_crc = struct.unpack_from('<QIII', data, 72)
    if current != expected_lba or count > 4096 or entry_size < 128:
        raise ValueError('Unexpected GPT layout')
    return dict(current=current, backup=backup, first=first, last=last,
                entries_lba=entries_lba, count=count, entry_size=entry_size,
                entries_crc=entries_crc, guid=str(uuid.UUID(bytes_le=data[56:72])))


def main():
    global OUT
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output',type=Path)
    parser.add_argument('--menu',action='store_true',help='Audit from the stock menu with Mobian mounted read-only at /mobian.')
    args = parser.parse_args()
    if args.output:
        OUT = args.output.resolve()
        assert OUT.is_relative_to((ROOT/'recovery').resolve())
    if OUT.exists():
        raise SystemExit('Audit directory already exists; refusing to overwrite original GPT copies.')
    connection = SSH.copy()
    command = 'python3 -'
    if args.menu:
        connection[connection.index('UserKnownHostsFile='+str(ROOT/'build/mobian-known-hosts'))] = 'UserKnownHostsFile='+str(ROOT/'build/mini-known-hosts')
        command = ('test "$(cat /mobian/etc/etherpocket/disk-identity)" = GM1920-548cb338-mobian-sda21 && '
                   'PYTHONHOME=/mobian/usr LD_LIBRARY_PATH=/mobian/usr/lib/aarch64-linux-gnu /mobian/usr/bin/python3 -')
    remote = subprocess.run(connection + [command], input=REMOTE.encode(),
                            capture_output=True, timeout=60)
    if remote.returncode:
        raise SystemExit(remote.stderr.decode(errors='replace'))
    raw = json.loads(remote.stdout)
    report = {'serial': '548cb338', 'method': 'read-only raw GPT primary/backup reads over pinned SSH',
              'personal_data_backup': False, 'disks': {}}
    for name, disk in raw.items():
        sector, size = disk['sector'], disk['size']
        head, tail = base64.b64decode(disk['head']), base64.b64decode(disk['tail'])
        primary = header(head[sector:2*sector], sector, 1)
        secondary = header(tail[-sector:], sector, size//sector-1)
        if primary['backup'] != secondary['current'] or secondary['backup'] != 1:
            raise ValueError('GPT reciprocal LBA mismatch')
        if any(primary[k] != secondary[k] for k in ['first', 'last', 'guid', 'count', 'entry_size', 'entries_crc']):
            raise ValueError('Primary/backup GPT mismatch')
        offset = primary['entries_lba'] * sector
        length = primary['count'] * primary['entry_size']
        entries = head[offset:offset+length]
        backup_offset = secondary['entries_lba'] * sector - (size-len(tail))
        if len(entries) != length or backup_offset < 0 or entries != tail[backup_offset:backup_offset+length]:
            raise ValueError('GPT entries not equal or outside backup bounds')
        if zlib.crc32(entries) != primary['entries_crc']:
            raise ValueError('GPT entry CRC mismatch')
        parts = []
        for i in range(primary['count']):
            entry = entries[i*primary['entry_size']:(i+1)*primary['entry_size']]
            if entry[:16] == bytes(16):
                continue
            start, end, flags = struct.unpack_from('<QQQ', entry, 32)
            if not primary['first'] <= start <= end <= primary['last']:
                raise ValueError('Partition outside usable disk')
            parts.append(dict(number=i+1, label=entry[56:128].decode('utf-16-le').rstrip('\0'),
                              start=start, end=end, size=(end-start+1)*sector,
                              guid=str(uuid.UUID(bytes_le=entry[16:32])), flags=flags))
        ordered = sorted(parts, key=lambda p: p['start'])
        if any(a['end'] >= b['start'] for a, b in zip(ordered, ordered[1:])):
            raise ValueError('Overlapping GPT partitions')
        report['disks'][name] = dict(size=size, sector=sector, gpt=primary, partitions=parts,
            head_sha256=hashlib.sha256(head).hexdigest(), tail_sha256=hashlib.sha256(tail).hexdigest())
    userdata = [p for p in report['disks']['sda']['partitions'] if p['label'] == 'userdata']
    if len(userdata) != 1 or userdata[0]['number'] != 20:
        raise ValueError('Unexpected GM1920 userdata partition')
    disk = report['disks']['sda']
    android_bytes = 32 * 1024**3
    boundary = userdata[0]['start'] + android_bytes // disk['sector']
    alignment = 1024*1024 // disk['sector']
    boundary = (boundary + alignment-1) // alignment * alignment
    report['candidate_only_not_applied'] = dict(
        android_userdata_bytes=android_bytes, android_userdata_GiB=32,
        mobian_start_lba=boundary, mobian_end_lba=userdata[0]['end'],
        mobian_bytes=(userdata[0]['end']-boundary+1)*disk['sector'],
        warning='32 GiB here means userdata only; fixed Android/firmware partitions remain additional. '
                'Encrypted userdata resize and standalone boot selection are not validated.')
    existing = [p for p in disk['partitions'] if p['label'] == 'mobian']
    if existing:
        report.pop('candidate_only_not_applied')
        report['existing_mobian'] = existing[0]
    OUT.mkdir(parents=True)
    for name, disk in raw.items():
        for side in ['head', 'tail']:
            (OUT / (name+'-'+side+'.bin')).write_bytes(base64.b64decode(disk[side]))
    (OUT/'report.json').write_text(json.dumps(report, indent=2)+'\n')
    print('All six UFS GPTs: primary/backup CRCs and entries verified; saved to', OUT)
    print(json.dumps(report.get('existing_mobian',report.get('candidate_only_not_applied')), indent=2))


if __name__ == '__main__':
    main()
