#!/usr/bin/env python3
"""Use the verified temporary recovery kernel to isolate native RAM init issues."""
import hashlib
import json
from pathlib import Path
import struct
import subprocess

workspace = Path('/mnt/c/projects.local/mobiam')
reference = workspace / 'recovery/twrp-3.4.0-0-guacamole.img'
expected = '9584d3bd7c5ab5c057bef26357bbddd485b9042d1a170cd62b05a592a8427ef5'
data = reference.read_bytes()
if hashlib.sha256(data).hexdigest() != expected or data[:8] != b'ANDROID!':
    raise SystemExit('Reference image verification failed')
fields = struct.unpack_from('<10I', data, 8)
ksize, kaddr, rsize, raddr, ssize, saddr, tags, page, version, osver = fields
if (page, version, ssize) != (4096, 0, 0):
    raise SystemExit('Unexpected recovery header')
kernel = Path('/opt/etherpocket/artifacts/reference-recovery-kernel')
kernel.write_bytes(data[page:page + ksize])
ramdisk = Path('/opt/etherpocket/artifacts/native-mini-rootfs.cpio.gz')
if ramdisk.stat().st_size > 16 * 1024 * 1024:
    raise SystemExit('Mini ramdisk size exceeds test limit')
cmdline = (data[64:576].split(b'\0')[0] + data[608:1632].split(b'\0')[0]).decode()
cmdline += ' etherpocket.ramboot=1 net.ifnames=0 rdinit=/init'
output = workspace / 'build/native-reference-kernel-test.img'
subprocess.run(['mkbootimg', '--kernel', str(kernel), '--ramdisk', str(ramdisk),
                '--base', '0', '--kernel_offset', hex(kaddr),
                '--ramdisk_offset', hex(raddr), '--second_offset', hex(saddr),
                '--tags_offset', hex(tags), '--pagesize', str(page),
                '--header_version', '0', '--cmdline', cmdline,
                '--output', str(output)], check=True)
if output.stat().st_size > 0x6000000:
    raise SystemExit('Image exceeds boot size limit')
manifest = {'purpose': 'RAM-only diagnostic: known recovery kernel with native Linux initramfs',
            'reference_sha256': expected, 'header_version': 0,
            'image_size': output.stat().st_size,
            'image_sha256': hashlib.sha256(output.read_bytes()).hexdigest(),
            'kernel_sha256': hashlib.sha256(kernel.read_bytes()).hexdigest(),
            'ramdisk_sha256': hashlib.sha256(ramdisk.read_bytes()).hexdigest(),
            'cmdline': cmdline,
            'limitation': 'Does not validate custom kernel, Xorg, or Freedreno'}
output.with_suffix('.json').write_text(json.dumps(manifest, indent=2) + '\n')
print(output, manifest['image_size'], manifest['image_sha256'])
