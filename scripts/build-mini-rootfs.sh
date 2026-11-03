#!/bin/bash
set -euo pipefail
workspace=/mnt/c/projects.local/mobiam
buildroot=/opt/etherpocket
root=$buildroot/miniroot
mkdir -p "$buildroot/minipkgs" "$root" "$buildroot/artifacts"
cd "$buildroot/minipkgs"
apt-get download busybox-static:arm64 dropbear-bin:arm64 libc6:arm64 \
 libcrypt1:arm64 libtomcrypt1:arm64 libtommath1:arm64 libgmp10:arm64 zlib1g:arm64
for package in *.deb; do dpkg-deb -x "$package" "$root"; done
mkdir -p "$root/bin" "$root/sbin" "$root/etc/dropbear" "$root/root/.ssh" \
 "$root/dev" "$root/proc" "$root/sys" "$root/run" "$root/newroot" "$root/usr/local/sbin"
if [ ! -e "$root/lib" ]; then ln -s usr/lib "$root/lib"; fi
if [ ! -e "$root/bin/busybox" ]; then ln -s ../usr/bin/busybox "$root/bin/busybox"; fi
qemu-aarch64 -L "$root" "$root/usr/bin/busybox" --list > "$buildroot/mini-applets.txt"
for needed in udhcpd tar switch_root ip; do grep -qx "$needed" "$buildroot/mini-applets.txt"; done
while read -r applet; do
 if [ ! -e "$root/bin/$applet" ]; then ln -s busybox "$root/bin/$applet"; fi
done < "$buildroot/mini-applets.txt"
if [ ! -e "$root/sbin/dropbear" ]; then ln -s ../usr/sbin/dropbear "$root/sbin/dropbear"; fi
cp "$workspace/config/etherpocket-mini-init" "$root/init"
cp "$workspace/scripts/etherpocket-usb-debug.sh" "$root/usr/local/sbin/etherpocket-usb-debug"
chmod 755 "$root/init" "$root/usr/local/sbin/etherpocket-usb-debug"
printf 'root:x:0:0:root:/root:/bin/sh\n' > "$root/etc/passwd"
printf 'root:x:0:\n' > "$root/etc/group"
root_hash=$(openssl passwd -6 -stdin < "$workspace/build/mobile-password.txt")
printf 'root:%s:20000:0:99999:7:::\n' "$root_hash" > "$root/etc/shadow"
chmod 600 "$root/etc/shadow"
cp "$workspace/build/etherpocket_ed25519.pub" "$root/root/.ssh/authorized_keys"
chmod 700 "$root/root/.ssh"
chmod 600 "$root/root/.ssh/authorized_keys"
if [ ! -e "$root/etc/dropbear/dropbear_ed25519_host_key" ]; then
 qemu-aarch64 -L "$root" "$root/usr/bin/dropbearkey" -t ed25519 \
  -f "$root/etc/dropbear/dropbear_ed25519_host_key"
fi
qemu-aarch64 -L "$root" "$root/usr/bin/dropbearkey" -y -f "$root/etc/dropbear/dropbear_ed25519_host_key" \
 | awk '/^ssh-ed25519 / {print "10.77.0.2 " $1 " " $2}' > "$workspace/build/mini-known-hosts"
cp /etc/os-release "$root/etc/os-release"
cd "$root"
find . -print0 | cpio --null -o --format=newc 2> "$workspace/evidence/mini-cpio.log" \
 | gzip -1 > "$buildroot/artifacts/native-mini-rootfs.cpio.gz"
sha256sum "$buildroot/artifacts/native-mini-rootfs.cpio.gz" > "$workspace/evidence/mini-rootfs.sha256"
ls -lh "$buildroot/artifacts/native-mini-rootfs.cpio.gz"
