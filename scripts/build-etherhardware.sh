#!/bin/sh
# Run in the existing Debian/WSL build environment. Does not deploy anything.
set -eu
source_root=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
cd "$source_root"
python3 -m unittest discover -s etherhardware/tests -v
build_dir=${ETHERHARDWARE_BUILD_DIR:-/opt/etherpocket/etherhardware-package}
cmake -S etherhardware -B "$build_dir" -DCMAKE_INSTALL_PREFIX=/usr
cmake --build "$build_dir" --target package
cp "$build_dir/etherhardware_0.1.1_arm64.deb" build/
