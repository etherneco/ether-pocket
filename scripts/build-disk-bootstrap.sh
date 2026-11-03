#!/bin/bash
set -euo pipefail
workspace=/mnt/c/projects.local/mobiam
source_root=/opt/etherpocket/miniroot
disk_root=/opt/etherpocket/disk-miniroot
mkdir -p "$disk_root"
cp -a "$source_root/." "$disk_root/"
cp "$workspace/config/etherpocket-disk-init" "$disk_root/init"
chmod 755 "$disk_root/init"
cd "$disk_root"
find . -print0 | cpio --null -o --format=newc 2> "$workspace/evidence/disk-init-cpio.log" \
 | gzip -1 > /opt/etherpocket/artifacts/native-disk-rootfs.cpio.gz
cd "$workspace"
python3 scripts/pack-native-mini-boot.py --name native-disk-dp-fixed --disk-root
