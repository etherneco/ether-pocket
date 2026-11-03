#!/bin/bash
# Uses the pinned kernel/rootfs/qbootctl build trees prepared in EtherPocketBuild.
set -euo pipefail
workspace=/mnt/c/projects.local/mobiam
test -f "$workspace/build/bootmenu/option-0.xrgb"
test -f "$workspace/build/bootmenu/option-1.xrgb"
bash "$workspace/scripts/build-phone-slotctl.sh"
aarch64-linux-gnu-gcc-12 -O2 -static -Wall -Wextra \
    "$workspace/scripts/android-verity-root.c" -o "$workspace/build/android-verity-root"
bash "$workspace/scripts/build-bootmenu-image.sh"
bash "$workspace/scripts/build-stock-menu-test.sh"
