#!/bin/sh
# Run in the existing Debian/WSL build environment. Does not deploy anything.
set -eu
source_root=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
cd "$source_root"
python3 -m unittest discover -s etherpower/tests -v
build_dir=${ETHERPOWER_BUILD_DIR:-/opt/etherpocket/etherpower-package}
cmake -S etherpower -B "$build_dir" -DCMAKE_INSTALL_PREFIX=/usr
cmake --build "$build_dir" --target package
cp "$build_dir/etherpower_0.1.0_arm64.deb" build/
