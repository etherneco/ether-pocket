#!/bin/sh
set -eu
export LANG=C.UTF-8 LC_ALL=C.UTF-8
root=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
build_dir=${ETHERBLUETOOTH_BUILD_DIR:-/opt/etherpocket/etherbluetooth-build}
cmake -S "$root/etherbluetooth" -B "$build_dir" -G Ninja \
    -DCMAKE_TOOLCHAIN_FILE="$root/ethershell/cmake/debian-arm64.cmake" \
    -DCMAKE_BUILD_TYPE=Release -DCMAKE_INSTALL_PREFIX=/usr
cmake --build "$build_dir" --parallel 2
cd "$build_dir"
cpack -G DEB
