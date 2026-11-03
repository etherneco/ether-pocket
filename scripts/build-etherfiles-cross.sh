#!/bin/sh
set -eu
export PATH=/usr/sbin:/usr/bin:/sbin:/bin
export LANG=C.UTF-8 LC_ALL=C.UTF-8
source_root=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
build_dir=${ETHERFILES_BUILD_DIR:-/opt/etherpocket/etherfiles-arm64}
cmake -S "$source_root/etherfiles" -B "$build_dir" -G Ninja \
  -DCMAKE_TOOLCHAIN_FILE="$source_root/ethershell/cmake/debian-arm64.cmake" \
  -DCMAKE_BUILD_TYPE=Release -DCMAKE_INSTALL_PREFIX=/usr -DBUILD_TESTING=OFF
cmake --build "$build_dir" --parallel "${ETHERFILES_BUILD_JOBS:-2}"
cd "$build_dir"
cpack -G DEB
