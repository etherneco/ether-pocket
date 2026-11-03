#!/bin/sh
set -eu
export PATH=/usr/sbin:/usr/bin:/sbin:/bin
export LANG=C.UTF-8 LC_ALL=C.UTF-8
source_root=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
cd "$source_root"
python3 -m unittest discover -s etherlocation/tests -v
build_dir=${ETHERLOCATION_BUILD_DIR:-/opt/etherpocket/etherlocation-arm64}
cmake -S etherlocation -B "$build_dir" -G Ninja -DCMAKE_TOOLCHAIN_FILE="$source_root/ethershell/cmake/debian-arm64.cmake" -DCMAKE_BUILD_TYPE=Release -DCMAKE_INSTALL_PREFIX=/usr
cmake --build "$build_dir" --target package
cp "$build_dir/etherlocation_0.1.1_arm64.deb" build/
