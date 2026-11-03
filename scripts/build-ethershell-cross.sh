#!/bin/sh
# Debian 13 amd64 build host with arm64 multiarch Qt and cross g++ installed.
set -eu
export PATH=/usr/sbin:/usr/bin:/sbin:/bin
export LANG=C.UTF-8 LC_ALL=C.UTF-8
source_root=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
build_dir=${ETHERSHELL_BUILD_DIR:-/opt/etherpocket/ethershell2-cross-build}
cmake -S "$source_root/ethershell" -B "$build_dir" -G Ninja \
  -DCMAKE_TOOLCHAIN_FILE="$source_root/ethershell/cmake/debian-arm64.cmake" \
  -DCMAKE_BUILD_TYPE=Release -DCMAKE_INSTALL_PREFIX=/usr
cmake --build "$build_dir" --parallel "${ETHERSHELL_BUILD_JOBS:-2}"
cd "$build_dir"
cpack -G DEB
