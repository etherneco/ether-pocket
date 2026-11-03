#!/bin/sh
set -eu
export PATH=/usr/sbin:/usr/bin:/sbin:/bin
export LANG=C.UTF-8 LC_ALL=C.UTF-8
source_root=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
cd "$source_root"
if [ ! -s build/ethermap-westminster-osm.mbtiles ]; then
 python3 scripts/prepare-ethermap-osm-region.py
fi
PYTHONPATH="$source_root/etherlocation:$source_root/ethermap" python3 -m unittest discover -s ethermap/tests -v
build_dir=${ETHERMAP_BUILD_DIR:-/opt/etherpocket/ethermap-arm64}
cmake -S ethermap -B "$build_dir" -G Ninja -DCMAKE_TOOLCHAIN_FILE="$source_root/ethershell/cmake/debian-arm64.cmake" -DCMAKE_BUILD_TYPE=Release -DCMAKE_INSTALL_PREFIX=/usr
cmake --build "$build_dir" --target package
cp "$build_dir/ethermap_0.1.0_arm64.deb" build/
