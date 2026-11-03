#!/bin/bash
set -euo pipefail
cd /opt/etherpocket/kexec-packages/kexec-tools-2.0.29
./configure --host=aarch64-linux-gnu CC=aarch64-linux-gnu-gcc-12 \
 CFLAGS='-O2' --without-xen --without-lzma --without-zstd --without-zlib
make -j4
cp build/sbin/kexec /mnt/c/projects.local/mobiam/build/kexec-arm64
readelf -d build/sbin/kexec | grep NEEDED
