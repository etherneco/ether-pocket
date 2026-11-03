#!/bin/bash
# Run inside the task's WSL cross-build host, not on the phone.
set -euo pipefail
workspace=/mnt/c/projects.local/mobiam
buildroot=/opt/etherpocket
recipes=$buildroot/mobian-recipes
test -d "$workspace/sources/mobian-recipes/.git"
mkdir -p "$recipes" "$buildroot/artifacts"
rsync -a "$workspace/sources/mobian-recipes/" "$recipes/"
# Windows Git can check scripts out with CRLF; normalize only the build copy.
python3 - "$recipes" <<'PY'
from pathlib import Path
import sys
for path in Path(sys.argv[1]).rglob('*'):
    if path.is_file() and path.suffix in ('.sh', '.yaml'):
        path.write_bytes(path.read_bytes().replace(b'\r\n', b'\n'))
PY
cp "$workspace/config/packages-xfce.yaml" "$recipes/include/packages-xfce.yaml"
cp "$workspace/scripts/setup-rootfs-user.sh" "$recipes/scripts/setup-user.sh"
chmod 755 "$recipes/scripts/setup-user.sh"
overlay=$recipes/overlays/etherpocket
mkdir -p "$overlay/etc/lightdm/lightdm.conf.d" "$overlay/etc/xdg/autostart" \
  "$overlay/usr/local/bin" "$overlay/usr/share/applications" "$overlay/etc/etherpocket"
cp "$workspace/config/90-etherpocket.conf" "$overlay/etc/lightdm/lightdm.conf.d/90-etherpocket.conf"
cp "$workspace/config/etherair-x11.desktop" "$overlay/etc/xdg/autostart/etherair-x11.desktop"
cp "$workspace/config/etherpocket-launcher.desktop" "$overlay/usr/share/applications/etherpocket-launcher.desktop"
cp "$workspace/scripts/etherair-x11.py" "$overlay/usr/local/bin/etherair-x11"
test -s "$workspace/build/mobile-password.txt"
openssl passwd -6 -stdin < "$workspace/build/mobile-password.txt" > "$overlay/etc/etherpocket/user-password.hash"
chmod 600 "$overlay/etc/etherpocket/user-password.hash"
bash "$workspace/scripts/stage-ramboot-rootfs.sh"
/usr/lib/systemd/systemd-binfmt /usr/lib/binfmt.d/qemu-aarch64.conf
cd "$recipes"
git rev-parse HEAD > "$workspace/evidence/mobian-recipes-commit.txt"
debos --disable-fakemachine --artifactdir="$buildroot/artifacts" \
  -t architecture:arm64 -t environment:xfce -t username:mobian \
  -t password:build-time-locked -t hostname:etherpocket \
  -t debian_suite:trixie -t suite:trixie \
  -t rootfs:mobian-arm64-xfce-rootfs.tar.xz rootfs.yaml
