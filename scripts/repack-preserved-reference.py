#!/usr/bin/env python3
"""Preserve verified recovery boot metadata while replacing only RAM userspace."""
import hashlib
import json
import shutil
import struct
import subprocess
from pathlib import Path

w = Path('/mnt/c/projects.local/mobiam')
reference = w / 'recovery/twrp-3.4.0-0-guacamole.img'
original = reference.read_bytes()
if hashlib.sha256(original).hexdigest() != '9584d3bd7c5ab5c057bef26357bbddd485b9042d1a170cd62b05a592a8427ef5':
    raise SystemExit('Reference digest mismatch')
tool = Path('/opt/etherpocket/boot-diagnostics/magiskboot')
target = tool.parent / 'preserved-reference'
target.mkdir(exist_ok=True)
subprocess.run([str(tool), 'unpack', '-n', '-h', str(reference)], cwd=target, check=True)
shutil.copyfile('/opt/etherpocket/artifacts/native-mini-rootfs.cpio.gz', target / 'ramdisk.cpio')
header = target / 'header'
lines = header.read_text().splitlines()
header.write_text('\n'.join(line + ' etherpocket.ramboot=1 net.ifnames=0 rdinit=/init'
                            if line.startswith('cmdline=') else line for line in lines) + '\n')
output = w / 'build/native-reference-preserved.img'
subprocess.run([str(tool), 'repack', str(reference), str(output)], cwd=target, check=True)
data = output.read_bytes()
if original[44:48] != data[44:48] or original[12:16] != data[12:16] or original[20:24] != data[20:24]:
    raise SystemExit('Original boot metadata was not preserved')
page = struct.unpack_from('<I', original, 36)[0]
kernel_size = struct.unpack_from('<I', original, 8)[0]
if data[page:page + kernel_size] != original[page:page + kernel_size]:
    raise SystemExit('Reference kernel changed unexpectedly')
if len(data) > 0x6000000:
    raise SystemExit('Boot image exceeds test limit')
manifest = {'purpose': 'RAM-only reference kernel diagnostic with preserved recovery metadata',
            'image_sha256': hashlib.sha256(data).hexdigest(), 'image_size': len(data),
            'original_os_version_field': hex(struct.unpack_from('<I', original, 44)[0]),
            'kernel_unchanged': True, 'not_verified': ['native boot', 'X11', 'GPU']}
output.with_suffix('.json').write_text(json.dumps(manifest, indent=2) + '\n')
print(json.dumps(manifest))
