#!/usr/bin/env python3
"""GM1920 OS selector: canonical boot type GUIDs plus slot flags.

The unused OEM A slot starts with a generic inactive type GUID. This
device's Fastboot set_active changes flags without fixing that type.
The host then completes the global slot activation in Fastboot.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import struct
import uuid
import zlib

p = argparse.ArgumentParser(description=__doc__)
p.add_argument('system',choices=['Android','Mobian'])
p.add_argument('--apply',action='store_true')
args = p.parse_args()
assert os.geteuid() == 0
assert 'androidboot.serialno=548cb338' in Path('/proc/cmdline').read_text().split()
assert Path('/etc/etherpocket/disk-identity').read_text().strip() == 'GM1920-548cb338-mobian-sda21'
sector, size = 4096, 4294967296
assert int(Path('/sys/class/block/sde/size').read_text())*512 == size


def validate(header, lba):
    assert header[:8] == b'EFI PART'
    length, checksum = struct.unpack_from('<II',header,12)
    assert 92 <= length <= sector
    checked = bytearray(header[:length])
    checked[16:20] = bytes(4)
    assert zlib.crc32(checked) == checksum
    assert struct.unpack_from('<Q',header,24)[0] == lba
    table, count, width, crc = struct.unpack_from('<QIII',header,72)
    assert 1 <= count <= 1024 and width == 128
    return table*sector,count*width,crc


def update_header(header, entries):
    out = bytearray(header)
    struct.pack_into('<I',out,88,zlib.crc32(entries))
    struct.pack_into('<I',out,16,0)
    length = struct.unpack_from('<I',out,12)[0]
    struct.pack_into('<I',out,16,zlib.crc32(out[:length]))
    return bytes(out)


fd = os.open('/dev/sde',os.O_RDONLY)
try:
    primary = os.pread(fd,sector,sector)
    secondary = os.pread(fd,sector,size-sector)
    a, b = validate(primary,1), validate(secondary,size//sector-1)
    assert a[1:] == b[1:]
    entries = os.pread(fd,a[1],a[0])
    assert entries == os.pread(fd,b[1],b[0]) and zlib.crc32(entries) == a[2]
finally:
    os.close(fd)
labels = {}
for offset in range(0,len(entries),128):
    name = entries[offset+56:offset+128].decode('utf-16-le').rstrip('\0')
    if name:
        assert name not in labels
        labels[name] = offset
assert labels['boot_a'] == 10*128 and labels['boot_b'] == 38*128
inactive = uuid.UUID('77036cd4-03d5-42bb-8ed1-37e5a88baa34').bytes_le
boot_type = uuid.UUID('20117f86-e985-4357-b9ee-374bc1d8487d').bytes_le
assert {entries[labels[n]:labels[n]+16] for n in ['boot_a','boot_b']} == {inactive,boot_type}
installed = Path('/etc/etherpocket/boot-images.json')
if installed.exists():
    images = json.loads(installed.read_text())
    assert images['serial'] == '548cb338'
    for label,path in [('boot_a','/dev/sde11'),('boot_b','/dev/sde39')]:
        record = images[label]
        assert 0 < record['size'] <= 0x6000000
        assert len(record['sha256']) == 64 and all(c in '0123456789abcdef' for c in record['sha256'])
        with open(path,'rb') as f:
            data = f.read(record['size'])
        assert len(data) == record['size'] and hashlib.sha256(data).hexdigest() == record['sha256']
else:
    with open('/dev/sde11','rb') as f:
        assert hashlib.sha256(f.read(45527040)).hexdigest() == '2ea1c9f1de7a15b78ad29bb650a7819f00476456306bcd899733eb76a8fbb15c'
    with open('/dev/sde39','rb') as f:
        assert hashlib.file_digest(f,'sha256').hexdigest() == '12f5ceb09558339c5d395078f7b0675374b4fd2b7c6d6900d2939badec11440d'
if args.system == 'Mobian':
    assert labels['vbmeta_a'] == 16*128 and labels['dtbo_a'] == 17*128
    for path,digest in [('/dev/sde17','27baa59973666d15bda4f690a4b55231f290b50097e609c8c3d9fbaa3c3f6368'),
                        ('/dev/sde18','6c319d579555e5f09de443db832c1659a0ee0763c59f64ebbca2ed11a3f921ef')]:
        with open(path,'rb') as f:
            assert hashlib.file_digest(f,'sha256').hexdigest() == digest
target = 'a' if args.system == 'Mobian' else 'b'
other = 'b' if target == 'a' else 'a'
modified = bytearray(entries)
modified[labels['boot_'+target]:labels['boot_'+target]+16] = boot_type
modified[labels['boot_'+other]:labels['boot_'+other]+16] = inactive
modified[labels['boot_'+target]+54] = 0x3f
modified[labels['boot_'+other]+54] = 0x7b
for offset in range(0,len(entries),128):
    if offset not in [labels['boot_a'],labels['boot_b']]:
        assert modified[offset:offset+128] == entries[offset:offset+128]
    else:
        assert modified[offset+16:offset+54] == entries[offset+16:offset+54]
        assert modified[offset+55:offset+128] == entries[offset+55:offset+128]
print('Prepare',args.system,'with canonical boot type GUIDs; finish activation in Fastboot.',flush=True)
if not args.apply:
    print('Inspection only; --apply is required for a change.',flush=True)
    raise SystemExit(0)
backup_dir = Path('/var/lib/etherpocket/boot-switch-backups')
backup_dir.mkdir(parents=True,exist_ok=True,mode=0o700)
backup = backup_dir/(hashlib.sha256(entries).hexdigest()+'.bin')
if not backup.exists():
    with backup.open('xb') as f:
        os.chmod(backup,0o600)
        f.write(primary+secondary+entries)
        f.flush()
        os.fsync(f.fileno())
writes = [(b[0],entries,bytes(modified)),(size-sector,secondary,update_header(secondary,modified)),
          (a[0],entries,bytes(modified)),(sector,primary,update_header(primary,modified))]
fd = os.open('/dev/sde',os.O_RDWR|os.O_SYNC)
try:
    for offset,before,after in writes:
        assert os.pread(fd,len(before),offset) == before
    for offset,before,after in writes:
        assert os.pwrite(fd,after,offset) == len(after)
        os.fsync(fd)
        assert os.pread(fd,len(after),offset) == after
finally:
    os.close(fd)
print('Primary and backup GPT verified.',flush=True)
