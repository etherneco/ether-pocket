#!/bin/sh
set -eu
source_root=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
cd "$source_root"
python3 -m unittest discover -s etheraudio/tests -v
build_dir=${ETHERAUDIO_BUILD_DIR:-/opt/etherpocket/etheraudio-package}
cmake -S etheraudio -B "$build_dir" -DCMAKE_INSTALL_PREFIX=/usr
cmake --build "$build_dir" --target package
cp "$build_dir/etheraudio_0.1.1_arm64.deb" build/
