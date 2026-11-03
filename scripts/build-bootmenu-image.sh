#!/bin/bash
set -euo pipefail
workspace=/mnt/c/projects.local/mobiam
menu_root=/opt/etherpocket/bootmenu-v2-miniroot
bash "$workspace/scripts/build-bootmenu.sh"
mkdir -p "$menu_root"
cp -a /opt/etherpocket/disk-miniroot/. "$menu_root/"
mkdir -p "$menu_root/usr/share/etherpocket/bootmenu"
cp "$workspace"/build/bootmenu/option-?.xrgb "$menu_root/usr/share/etherpocket/bootmenu/"
cp -L /usr/lib/aarch64-linux-gnu/libdrm.so.2 "$menu_root/lib/aarch64-linux-gnu/"
cp "$workspace/build/etherpocket-bootmenu" "$menu_root/usr/bin/"
cp "$workspace/build/etherpocket-slotctl" "$menu_root/usr/sbin/"
cp "$workspace/scripts/etherpocket-boot-handoff.sh" "$menu_root/usr/local/sbin/"
python3 - "$workspace" "$menu_root" <<'PY'
import sys
from pathlib import Path
w, dest = map(Path, sys.argv[1:])
init = (w/'config/etherpocket-disk-init').read_text()
anchor = 'mount --move /dev /newroot/dev'
assert init.count(anchor) == 1
init = init.replace(anchor, '''# Explicit opt-in rescue access; normal USB belongs to the selected OS.
if [ -f /newroot/etc/etherpocket/bootmenu-debug ]; then
    /usr/local/sbin/etherpocket-usb-debug > /run/usb-debug.log 2>&1 &
    usb_debug_pid=$!
    /usr/sbin/dropbear -E -s -r /etc/dropbear/dropbear_ed25519_host_key
fi
/usr/local/sbin/etherpocket-boot-handoff.sh
if [ -n "${usb_debug_pid:-}" ]; then
    kill "$usb_debug_pid" 2>/dev/null || true
    killall dropbear udhcpd 2>/dev/null || true
fi
'''+anchor)
(dest/'init').write_text(init)
PY
chmod 755 "$menu_root/init" "$menu_root/usr/local/sbin/etherpocket-boot-handoff.sh" \
          "$menu_root/usr/bin/etherpocket-bootmenu" "$menu_root/usr/sbin/etherpocket-slotctl"
cd "$menu_root"
find . -print0 | cpio --null -o --format=newc 2> "$workspace/evidence/bootmenu-cpio.log" \
    | gzip -1 > /opt/etherpocket/artifacts/native-bootmenu-rootfs.cpio.gz
python3 "$workspace/scripts/pack-native-mini-boot.py" --disk-root --bootmenu --name native-bootmenu-test
