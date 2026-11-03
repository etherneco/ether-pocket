#!/bin/sh
set -eu
root=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
build_dir=${ETHERNOTIFICATIONS_BUILD_DIR:-/opt/etherpocket/ethernotifications-arm64}
python3 -m unittest discover -s "$root/ethernotifications/tests" -p 'test_*.py' -v
cmake -S "$root/ethernotifications" -B "$build_dir" -G Ninja -DCMAKE_TOOLCHAIN_FILE="$root/ethershell/cmake/debian-arm64.cmake" -DCMAKE_BUILD_TYPE=Release -DCMAKE_INSTALL_PREFIX=/usr -DBUILD_TESTING=ON
cmake --build "$build_dir" --parallel 3
cd "$build_dir"
cpack -G DEB
cp ethernotifications_0.1.0_arm64.deb "$root/build/"
