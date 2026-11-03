#!/bin/bash
set -euo pipefail
workspace=/mnt/c/projects.local/mobiam
export PKG_CONFIG_LIBDIR=/usr/lib/aarch64-linux-gnu/pkgconfig:/usr/share/pkgconfig
aarch64-linux-gnu-gcc-12 -O2 -Wall -Wextra "$workspace/scripts/etherpocket-bootmenu.c" \
 $(pkg-config --cflags --libs libdrm) -o "$workspace/build/etherpocket-bootmenu"
qemu-aarch64 -L /usr/aarch64-linux-gnu "$workspace/build/etherpocket-bootmenu" --selftest
