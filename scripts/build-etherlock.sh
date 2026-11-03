#!/bin/sh
set -eu
export LANG=C.UTF-8 LC_ALL=C.UTF-8
root=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
python3 -m unittest discover -s "$root/etherlock/tests" -v
build_dir=${ETHERLOCK_BUILD_DIR:-/opt/etherpocket/etherlock-arm64}
cmake -S "$root/etherlock" -B "$build_dir" -G Ninja -DCMAKE_TOOLCHAIN_FILE="$root/ethershell/cmake/debian-arm64.cmake" -DCMAKE_BUILD_TYPE=Release -DCMAKE_INSTALL_PREFIX=/usr
cmake --build "$build_dir" --parallel 2
cd "$build_dir"
cpack -G DEB
cp etherlock_0.1.0_arm64.deb "$root/build/"
