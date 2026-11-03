#!/bin/sh
set -eu
root=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
build_dir=${ETHERPHONE_BUILD_DIR:-/opt/etherpocket/etherphone-arm64}
python3 -m unittest discover -s "$root/etherphone/tests" -v
cmake -S "$root/etherphone" -B "$build_dir" -G Ninja -DCMAKE_TOOLCHAIN_FILE="$root/ethershell/cmake/debian-arm64.cmake" -DCMAKE_BUILD_TYPE=Release -DCMAKE_INSTALL_PREFIX=/usr -DBUILD_TESTING=ON
cmake --build "$build_dir" --parallel 3
cd "$build_dir"
cpack -G DEB
cp etherphone_0.1.0_arm64.deb "$root/build/"
