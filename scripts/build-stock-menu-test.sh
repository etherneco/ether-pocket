#!/bin/bash
set -euo pipefail
workspace=/mnt/c/projects.local/mobiam
stock_root=/opt/etherpocket/stock-menu-miniroot
mkdir -p "$stock_root"
cp -a /opt/etherpocket/miniroot/. "$stock_root/"
mkdir -p "$stock_root/usr/share/etherpocket/bootmenu"
cp "$workspace"/build/bootmenu/option-?.xrgb "$stock_root/usr/share/etherpocket/bootmenu/"
cp -L /usr/lib/aarch64-linux-gnu/libdrm.so.2 "$stock_root/lib/aarch64-linux-gnu/"
cp "$workspace/build/etherpocket-bootmenu" "$stock_root/usr/bin/"
cp "$workspace/build/etherpocket-slotctl" "$stock_root/usr/sbin/"
cp "$workspace/build/android-verity-root" "$stock_root/usr/sbin/"
cp "$workspace/config/etherpocket-android-menu-init" "$stock_root/init"
chmod 755 "$stock_root/init" "$stock_root/usr/bin/etherpocket-bootmenu" \
    "$stock_root/usr/sbin/etherpocket-slotctl" "$stock_root/usr/sbin/android-verity-root"
# Do not carry a previous diagnostic executable into a normal boot image.
if [ -f "$stock_root/usr/sbin/guard-android-init" ]; then
    rm "$stock_root/usr/sbin/guard-android-init"
fi
cd "$stock_root"
find . -print0 | cpio --null -o --format=newc 2> "$workspace/evidence/stock-menu-cpio.log" \
    | gzip -1 > /opt/etherpocket/artifacts/stock-menu-rootfs.cpio.gz
python3 - <<'PY'
from pathlib import Path
import hashlib, json, struct, subprocess
w = Path('/mnt/c/projects.local/mobiam')
stock = (w/'recovery/stock-backup/boot_b.img').read_bytes()
assert hashlib.sha256(stock).hexdigest() == '12f5ceb09558339c5d395078f7b0675374b4fd2b7c6d6900d2939badec11440d'
ks, ka, rs, ra, ss, sa, ta, page, version, osver = struct.unpack_from('<10I', stock, 8)
assert page == 4096 and version == 2
kernel = stock[page:page+ks]
# Disable only the skip-initramfs parameter lookup, retaining stock code and
# module ABI. This is a diagnostic image, not a flashed firmware modification.
token = b'skip_initramfs\0'
assert kernel.count(token) == 1
kernel = kernel.replace(token, b'skip_initramfx\0')
kp = w/'build/bootmenu/stock-menu-Image'
kp.write_bytes(kernel)
ds, da = struct.unpack_from('<IQ', stock, 1648)
cmdline = (stock[64:576].split(b'\0')[0]+stock[608:1632].split(b'\0')[0]).decode()
cmdline += ' androidboot.mode=normal etherpocket.ramboot=1 rdinit=/init'
image = w/'build/stock-menu-test.img'
subprocess.run(['mkbootimg', '--kernel', str(kp), '--ramdisk', '/opt/etherpocket/artifacts/stock-menu-rootfs.cpio.gz',
 '--dtb', '/opt/etherpocket/stock-boot/dtb', '--base', '0', '--kernel_offset', hex(ka),
 '--ramdisk_offset', hex(ra), '--second_offset', hex(sa), '--tags_offset', hex(ta), '--dtb_offset', hex(da),
 '--pagesize', str(page), '--header_version', '2', '--os_version', '10.0.0', '--os_patch_level', '2021-11',
 '--cmdline', cmdline, '--output', str(image)], check=True)
assert image.stat().st_size < 0x6000000
(w/'build/stock-menu-test-manifest.json').write_text(json.dumps(dict(purpose='Android 10 stock-kernel menu with verified system_b handoff',
 image_sha256=hashlib.sha256(image.read_bytes()).hexdigest(), patched_token_offset=stock[page:page+ks].index(token)), indent=2)+'\n')
print(image, image.stat().st_size)
PY
