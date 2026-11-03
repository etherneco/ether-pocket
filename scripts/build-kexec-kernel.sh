#!/bin/bash
set -euo pipefail
cd /opt/etherpocket/kernel
python3 /mnt/c/projects.local/mobiam/scripts/fix-kexec-wrapper.py
mkdir -p /opt/etherpocket/known-good
if [ ! -e /opt/etherpocket/known-good/Image-v5 ]; then
 cp /opt/etherpocket/out/arch/arm64/boot/Image /opt/etherpocket/known-good/Image-v5
 cp /opt/etherpocket/out/.config /opt/etherpocket/known-good/config-v5
fi
scripts/config --file /opt/etherpocket/out/.config --enable KEXEC
make O=/opt/etherpocket/out ARCH=arm64 CROSS_COMPILE=aarch64-linux-gnu- olddefconfig
make -j8 O=/opt/etherpocket/out ARCH=arm64 CROSS_COMPILE=aarch64-linux-gnu- \
 CC=aarch64-linux-gnu-gcc-12 HOSTCFLAGS=-fcommon \
 KCFLAGS="-Wno-error=format -Wno-error=strict-prototypes" Image
python3 /mnt/c/projects.local/mobiam/scripts/pack-native-mini-boot.py --name native-kexec-test --disk-root
