#!/usr/bin/env python3
"""Restore original, known-working slot-B GPT types/flags; preserve all geometry and data."""
import argparse
import base64
import hashlib
import json
from pathlib import Path
import struct
import subprocess
import zlib
from importlib.machinery import SourceFileLoader

root = Path(__file__).resolve().parent.parent
audit = SourceFileLoader('gpt_audit',str(root/'scripts/audit-dualboot.py')).load_module()
p = argparse.ArgumentParser(description=__doc__)
p.add_argument('--apply',action='store_true')
p.add_argument('--before',type=Path,default=root/'recovery/dualboot-audit')
p.add_argument('--current',type=Path,default=root/'recovery/dualboot-after-switch')
args = p.parse_args()
original_dir = args.before
current_dir = args.current
original = json.loads((original_dir/'report.json').read_text())
current = json.loads((current_dir/'report.json').read_text())
assert original['serial'] == current['serial'] == '548cb338'
writes = []
for name, disk in original['disks'].items():
    now = current['disks'][name]
    assert disk['size'] == now['size'] and disk['sector'] == now['sector'] == 4096
    sector = disk['sector']
    old_head = (original_dir/(name+'-head.bin')).read_bytes()
    head = (current_dir/(name+'-head.bin')).read_bytes()
    tail = (current_dir/(name+'-tail.bin')).read_bytes()
    assert hashlib.sha256(old_head).hexdigest() == disk['head_sha256']
    assert hashlib.sha256(head).hexdigest() == now['head_sha256']
    assert hashlib.sha256(tail).hexdigest() == now['tail_sha256']
    ph, bh = audit.header(head[sector:2*sector],sector,1), audit.header(tail[-sector:],sector,now['size']//sector-1)
    length = ph['count']*ph['entry_size']
    offset = ph['entries_lba']*sector
    entries = head[offset:offset+length]
    modified = bytearray(entries)
    for part in disk['partitions']:
        if not part['label'].endswith(('_a','_b')):
            continue
        live = next(x for x in now['partitions'] if x['label'] == part['label'])
        assert all(part[k] == live[k] for k in ['number','guid','start','end','size'])
        old_offset = disk['gpt']['entries_lba']*sector+(part['number']-1)*128
        live_offset = (live['number']-1)*128
        expected_type = old_head[old_offset:old_offset+16]
        actual_type = entries[live_offset:live_offset+16]
        if expected_type != actual_type or part['flags'] != live['flags']:
            print(name,part['label'], 'type differs:',expected_type != actual_type,
                  'flags:',hex(live['flags']),'->',hex(part['flags']),flush=True)
        modified[live_offset:live_offset+16] = expected_type
        struct.pack_into('<Q',modified,live_offset+48,part['flags'])
    if modified == entries:
        continue
    def update(header):
        out = bytearray(header)
        struct.pack_into('<I',out,88,zlib.crc32(modified))
        struct.pack_into('<I',out,16,0)
        n = struct.unpack_from('<I',out,12)[0]
        struct.pack_into('<I',out,16,zlib.crc32(out[:n]))
        return bytes(out)
    for pos,before,after in [(bh['entries_lba']*sector,entries,bytes(modified)),
                             (now['size']-sector,tail[-sector:],update(tail[-sector:])),
                             (offset,entries,bytes(modified)),
                             (sector,head[sector:2*sector],update(head[sector:2*sector]))]:
        writes.append((name,pos,base64.b64encode(before).decode(),base64.b64encode(after).decode()))
if not args.apply:
    raise SystemExit('Inspection only. Original slot-B metadata restore plan prepared.')
remote = '''import base64, os
from pathlib import Path
assert 'androidboot.serialno=548cb338' in Path('/proc/cmdline').read_text().split()
assert Path('/etc/etherpocket/disk-identity').read_text().strip() == 'GM1920-548cb338-mobian-sda21'
'''
remote += 'writes = '+repr(writes)+'\n'
remote += '''
# Validate all preconditions before writing the first disk.
for name,offset,before,after in writes:
    with open('/dev/'+name,'rb',buffering=0) as f:
        f.seek(offset)
        assert f.read(len(base64.b64decode(before))) == base64.b64decode(before)
for name,offset,before,after in writes:
    fd = os.open('/dev/'+name,os.O_RDWR|os.O_SYNC)
    try:
        data = base64.b64decode(after)
        assert os.pwrite(fd,data,offset) == len(data)
        os.fsync(fd)
        assert os.pread(fd,len(data),offset) == data
    finally:
        os.close(fd)
print('Original working slot-B type GUIDs and flags restored; geometry and image contents preserved.')
'''
subprocess.run(audit.SSH+['python3 -'],input=remote.encode(),check=True,timeout=45)
