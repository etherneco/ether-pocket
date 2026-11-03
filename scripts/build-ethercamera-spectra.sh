#!/bin/sh
set -eu
export PATH=/usr/sbin:/usr/bin:/sbin:/bin
source_root=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
cd "$source_root"
uapi=/opt/etherpocket/kernel/include/uapi
native=/opt/etherpocket/ethercamera-spectra-native
arm64=/opt/etherpocket/ethercamera-spectra-arm64
python3 -m unittest discover -s ethercamera/spectra -p test_module_profile.py -v
cmake -S ethercamera/spectra -B "$native" -G Ninja -DSPECTRA_UAPI_ROOT="$uapi" -DCMAKE_BUILD_TYPE=Debug
cmake --build "$native"
ctest --test-dir "$native" --output-on-failure
cmake -S ethercamera/spectra -B "$arm64" -G Ninja -DSPECTRA_UAPI_ROOT="$uapi" -DCMAKE_TOOLCHAIN_FILE="$source_root/ethershell/cmake/debian-arm64.cmake" -DCMAKE_BUILD_TYPE=Release -DCMAKE_INSTALL_PREFIX=/usr
cmake --build "$arm64" --target package
cp "$arm64/ethercamera-spectra_0.2.0_arm64.deb" build/
