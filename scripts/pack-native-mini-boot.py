#!/usr/bin/env python3
"""Pack a RAM-only native test using the backed-up GM1920 boot header and DTB."""
import hashlib
import json
import argparse
from pathlib import Path
import struct
import subprocess

workspace = Path('/mnt/c/projects.local/mobiam')
buildroot = Path('/opt/etherpocket')
parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('--name', default='native-mini-boot')
parser.add_argument('--disk-root', action='store_true',
                    help='Use the guarded persistent Mobian bootstrap instead of the RAM test.')
parser.add_argument('--bootmenu', action='store_true',
                    help='Use the larger menu initramfs with the original Android payload.')
parser.add_argument('--kernel-format', choices=('raw', 'gzip'), default='raw',
                    help='Stock GM1920 uses a raw ARM64 Image; gzip is experimental.')
args = parser.parse_args()
if not args.name.replace('-', '').isalnum():
    raise SystemExit('Use a simple image name without path components.')
stock = (workspace / 'recovery/stock-backup/boot_b.img').read_bytes()
if stock[:8] != b'ANDROID!':
    raise SystemExit('Stock boot image has an unexpected format.')
fields = struct.unpack_from('<10I', stock, 8)
kernel_size, kernel_address, ramdisk_size, ramdisk_address, second_size, second_address, tags_address, page_size, header_version, os_version = fields
if (page_size, header_version) != (4096, 2):
    raise SystemExit('Unexpected GM1920 boot header; review before packing.')
cmdline = (stock[64:576].split(b'\0')[0] + stock[608:1632].split(b'\0')[0]).decode()
cmdline += ' etherpocket.ramboot=1 net.ifnames=0 console=tty0 rdinit=/init'
dtb_size, dtb_address = struct.unpack_from('<IQ', stock, 1648)
new_kernel = buildroot / 'out/arch/arm64/boot' / ('Image' if args.kernel_format == 'raw' else 'Image.gz')
ramdisk = buildroot / 'artifacts/native-mini-rootfs.cpio.gz'
if args.disk_root:
    ramdisk = buildroot / 'artifacts/native-disk-rootfs.cpio.gz'
if args.bootmenu:
    if not args.disk_root:
        raise SystemExit('--bootmenu requires --disk-root')
    ramdisk = buildroot / 'artifacts/native-bootmenu-rootfs.cpio.gz'
dtb = buildroot / 'stock-boot/dtb'
out = workspace / 'build' / (args.name + '.img')
if dtb.stat().st_size != dtb_size or not new_kernel.is_file():
    raise SystemExit('Kernel or stock DTB validation failed.')
if args.kernel_format == 'raw' and new_kernel.read_bytes()[56:60] != b'ARM\x64':
    raise SystemExit('Raw kernel is missing the ARM64 Image magic.')
if ramdisk.stat().st_size > (64 if args.bootmenu else 16) * 1024 * 1024:
    raise SystemExit('Mini ramdisk is larger than the planned initial test.')
command = ['mkbootimg', '--kernel', str(new_kernel), '--ramdisk', str(ramdisk),
           '--dtb', str(dtb), '--base', '0', '--kernel_offset', hex(kernel_address),
           '--ramdisk_offset', hex(ramdisk_address), '--second_offset', hex(second_address),
           '--tags_offset', hex(tags_address), '--dtb_offset', hex(dtb_address),
           '--pagesize', str(page_size), '--header_version', str(header_version),
           '--os_version', '10.0.0', '--os_patch_level', '2021-11',
           '--cmdline', cmdline, '--output', str(out)]
subprocess.run(command, check=True)
if out.stat().st_size > 0x6000000:
    raise SystemExit('Test image exceeds the physical boot partition size; do not boot it.')
manifest = {'purpose': 'RAM-only native kernel and USB test; not a production flash image',
            'stock_header': {'version': header_version, 'page_size': page_size},
            'kernel_format': args.kernel_format,
            'kernel_commit': '31bebb6ffc476f51986bd04502a76ffbd9e2fa7a',
            'vendor_commit': '5fba057468048661d4cbc8cc50303575a42a37da',
            'inputs': {}, 'image_size': out.stat().st_size,
            'image_sha256': hashlib.sha256(out.read_bytes()).hexdigest(),
            'cmdline': cmdline}
if args.disk_root:
    manifest['purpose'] = 'Experimental persistent Mobian bootstrap; boot-test before flashing'
for path in (new_kernel, ramdisk, dtb, buildroot / 'out/.config'):
    manifest['inputs'][str(path)] = hashlib.sha256(path.read_bytes()).hexdigest()
(workspace / 'build' / (args.name + '-manifest.json')).write_text(json.dumps(manifest, indent=2) + '\n')
print(out, manifest['image_size'], manifest['image_sha256'])
