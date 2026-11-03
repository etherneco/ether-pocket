#!/bin/sh
set -eu
source_root=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
python3 -m unittest discover -s "$source_root/ethercredentials/tests" -v
build_dir=${ETHERCREDENTIALS_BUILD_DIR:-/opt/etherpocket/ethercredentials}
cmake -S "$source_root/ethercredentials" -B "$build_dir" -DCMAKE_INSTALL_PREFIX=/usr
cmake --build "$build_dir" --target package
cp "$build_dir/ethercredentials_0.1.0_all.deb" "$source_root/build/"
