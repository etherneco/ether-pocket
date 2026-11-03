#!/usr/bin/env python3
"""Prepare and optionally apply the reviewed GM1920 userdata split, preserving other entries."""
import argparse
import base64
import hashlib
import json
from pathlib import Path
import struct
import subprocess
import uuid
import zlib
from importlib.machinery import SourceFileLoader

ROOT = Path(__file__).resolve().parent.parent
audit = SourceFileLoader('gpt_audit', str(ROOT/'scripts/audit-dualboot.py')).load_module()
parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('--apply-authorized-android-data-reset', action='store_true')
args = parser.parse_args()
source = ROOT/'recovery/dualboot-audit'
report = json.loads((source/'report.json').read_text())
disk = report['disks']['sda']
sector, size = disk['sector'], disk['size']
assert sector == 4096 and disk['gpt']['count'] == 32 and disk['gpt']['entry_size'] == 128
head = (source/'sda-head.bin').read_bytes()
tail = (source/'sda-tail.bin').read_bytes()
assert hashlib.sha256(head).hexdigest() == disk['head_sha256']
assert hashlib.sha256(tail).hexdigest() == disk['tail_sha256']
old_entries = head[2*sector:3*sector]
entries = bytearray(old_entries)
userdata = next(p for p in disk['partitions'] if p['label'] == 'userdata')
assert userdata['number'] == 20 and not any(old_entries[20*128:21*128])
android_end = userdata['start'] + (32*1024**3)//sector - 1
linux_start = report['candidate_only_not_applied']['mobian_start_lba']
assert android_end < linux_start < userdata['end']
struct.pack_into('<Q', entries, 19*128+40, android_end)
linux_guid = uuid.UUID('6e8c4f39-c819-4b95-a7ea-548cb3380021')
linux_entry = bytearray(128)
linux_entry[:16] = uuid.UUID('0fc63daf-8483-4772-8e79-3d69d8477de4').bytes_le
linux_entry[16:32] = linux_guid.bytes_le
struct.pack_into('<QQQ', linux_entry, 32, linux_start, userdata['end'], 0)
label = 'mobian'.encode('utf-16-le')
linux_entry[56:56+len(label)] = label
entries[20*128:21*128] = linux_entry
assert entries[:19*128] == old_entries[:19*128] and entries[21*128:] == old_entries[21*128:]

def updated_header(original):
    new = bytearray(original)
    struct.pack_into('<I', new, 88, zlib.crc32(entries))
    struct.pack_into('<I', new, 16, 0)
    length = struct.unpack_from('<I', new, 12)[0]
    struct.pack_into('<I', new, 16, zlib.crc32(new[:length]))
    return bytes(new)

primary = updated_header(head[sector:2*sector])
secondary = updated_header(tail[-sector:])
audit.header(primary, sector, 1)
audit.header(secondary, sector, size//sector-1)
plan = dict(serial='548cb338', android_userdata_bytes=32*1024**3,
            android_start_lba=userdata['start'], android_end_lba=android_end,
            linux_start_lba=linux_start, linux_end_lba=userdata['end'],
            linux_bytes=(userdata['end']-linux_start+1)*sector, linux_partuuid=str(linux_guid),
            alignment_gap_bytes=(linux_start-android_end-1)*sector,
            boot_strategy='Mobian boot_a, Android boot_b; explicit Fastboot slot selection',
            android_data_reset_authorized=True, applied=False)
build = ROOT/'build/dualboot-gpt'
build.mkdir(parents=True, exist_ok=True)
for name, data in [('primary-header',primary), ('backup-header',secondary), ('entries',bytes(entries))]:
    (build/(name+'.bin')).write_bytes(data)
(build/'plan.json').write_text(json.dumps(plan, indent=2)+'\n')
print(json.dumps(plan, indent=2), flush=True)
if not args.apply_authorized_android_data_reset:
    raise SystemExit('Plan prepared only. No phone writes.')

# Write only GPT headers and entry arrays, never the other data in backup windows.
writes = [(size-2*sector, tail[-2*sector:-sector], bytes(entries)),
          (size-sector, tail[-sector:], secondary),
          (2*sector, old_entries, bytes(entries)),
          (sector, head[sector:2*sector], primary)]
payload = [(offset,base64.b64encode(old).decode(),base64.b64encode(new).decode()) for offset,old,new in writes]
remote = '''import base64, json, os, subprocess
from pathlib import Path
assert 'androidboot.serialno=548cb338' in Path('/proc/cmdline').read_text().split()
assert 'etherpocket.ramboot=1' in Path('/proc/cmdline').read_text().split()
assert subprocess.check_output(['stat','-f','-c','%T','/']).strip() == b'tmpfs'
assert int(Path('/sys/class/block/sda/size').read_text())*512 == 251532410880
assert int(Path('/sys/class/power_supply/battery/capacity').read_text()) >= 30
for path in ['/dev/sda17','/dev/sda20','/dev/sda21']:
    assert subprocess.run(['findmnt','-rn','-S',path],stdout=subprocess.DEVNULL).returncode == 1
assert not Path('/dev/sda21').exists()
'''
remote += 'writes = '+repr(payload)+'\n'
remote += '''fd = os.open('/dev/sda', os.O_RDWR | os.O_SYNC)
try:
    for offset, old, new in writes:
        assert os.pread(fd,4096,offset) == base64.b64decode(old), 'Original GPT changed; abort'
    for offset, old, new in writes:
        data = base64.b64decode(new)
        assert os.pwrite(fd,data,offset) == len(data)
        os.fsync(fd)
        assert os.pread(fd,len(data),offset) == data, 'GPT write verification failed'
finally:
    os.close(fd)
subprocess.run(['blockdev','--rereadpt','/dev/sda'],check=True)
assert int(Path('/sys/class/block/sda20/size').read_text())*512 == 34359738368
assert int(Path('/sys/class/block/sda21/size').read_text())*512 == 208467374080
print('New GPT primary and backup verified; kernel sees 32 GiB userdata and Mobian partition.')
'''
result = subprocess.run(audit.SSH+['python3 -'],input=remote.encode(),capture_output=True,timeout=45)
if result.returncode:
    raise SystemExit(result.stderr.decode(errors='replace'))
print(result.stdout.decode(), flush=True)
plan['applied'] = True
(build/'plan.json').write_text(json.dumps(plan, indent=2)+'\n')
