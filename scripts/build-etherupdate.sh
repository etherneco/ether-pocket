#!/bin/sh
set -eu
source_root=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
cd "$source_root"
python3 -m unittest discover -s etherupdate/tests -v
build_dir=${ETHERUPDATE_BUILD_DIR:-/opt/etherpocket/etherupdate-package}
cmake -S etherupdate -B "$build_dir" -DCMAKE_INSTALL_PREFIX=/usr
cmake --build "$build_dir" --target package
cp "$build_dir/etherupdate_0.1.0_arm64.deb" build/
