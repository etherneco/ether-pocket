#!/bin/sh
set -eu
root=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
build_dir=${ETHERSMS_BUILD_DIR:-/opt/etherpocket/ethersms-arm64}
export LANG=C.UTF-8 LC_ALL=C.UTF-8
cmake -S "$root/ethersms" -B "$build_dir" -G Ninja -DCMAKE_TOOLCHAIN_FILE="$root/ethershell/cmake/debian-arm64.cmake" -DCMAKE_BUILD_TYPE=Release -DCMAKE_INSTALL_PREFIX=/usr -DBUILD_TESTING=ON
cmake --build "$build_dir" --parallel 3
cd "$build_dir"
cpack -G DEB
