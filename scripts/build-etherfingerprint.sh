#!/bin/sh
set -eu
source_root=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
cd "$source_root"
python3 -m unittest discover -s etherfingerprint/tests -v
build_dir=${ETHERFINGERPRINT_BUILD_DIR:-/opt/etherpocket/etherfingerprint-arm64}
cmake -S etherfingerprint -B "$build_dir" -DCMAKE_INSTALL_PREFIX=/usr
cmake --build "$build_dir" --target package
cp "$build_dir/etherfingerprint_0.2.0_arm64.deb" build/
