#!/bin/sh
set -eu
source_root=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
cd "$source_root"
python3 -m unittest discover -s etherbackup/tests -v
build_dir=${ETHERBACKUP_BUILD_DIR:-/opt/etherpocket/etherbackup-package}
cmake -S etherbackup -B "$build_dir" -DCMAKE_INSTALL_PREFIX=/usr
cmake --build "$build_dir" --target package
cp "$build_dir/etherbackup_0.1.0_arm64.deb" build/
