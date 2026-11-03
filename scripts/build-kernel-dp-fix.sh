#!/bin/bash
set -euo pipefail
python3 /mnt/c/projects.local/mobiam/scripts/fix-dp-backlight.py
cd /opt/etherpocket/kernel
make -j8 O=/opt/etherpocket/out ARCH=arm64 CROSS_COMPILE=aarch64-linux-gnu- \
 CC=aarch64-linux-gnu-gcc-12 HOSTCFLAGS=-fcommon \
 KCFLAGS="-Wno-error=format -Wno-error=strict-prototypes" Image
