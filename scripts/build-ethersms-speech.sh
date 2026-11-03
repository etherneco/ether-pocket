#!/bin/sh
# Build the optional offline engine, never download speech models.
set -eu
root=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
source_dir=${WHISPER_SOURCE_DIR:-/opt/etherpocket/ethersms-whisper-source}
build_dir=${WHISPER_BUILD_DIR:-/opt/etherpocket/ethersms-whisper-arm64}
package_dir=${WHISPER_PACKAGE_DIR:-/opt/etherpocket/ethersms-speech-package}
expected=$(tr -d '\r\n' < "$root/evidence/ethersms-whisper-source-commit.txt")
actual=$(git -C "$source_dir" rev-parse HEAD)
[ "$actual" = "$expected" ] || { echo 'Use the recorded upstream Whisper source revision.' >&2; exit 1; }
cmake -S "$source_dir" -B "$build_dir" -G Ninja -DCMAKE_TOOLCHAIN_FILE="$root/ethershell/cmake/debian-arm64.cmake" -DCMAKE_BUILD_TYPE=Release -DBUILD_SHARED_LIBS=OFF -DWHISPER_BUILD_TESTS=OFF -DWHISPER_BUILD_EXAMPLES=ON -DGGML_NATIVE=OFF -DGGML_OPENMP=OFF
cmake --build "$build_dir" --target whisper-cli --parallel 3
mkdir -p "$package_dir/DEBIAN" "$package_dir/usr/bin" "$package_dir/usr/share/doc/ethersms-speech-engine"
cp "$build_dir/bin/whisper-cli" "$package_dir/usr/bin/"
cp "$source_dir/LICENSE" "$package_dir/usr/share/doc/ethersms-speech-engine/copyright"
printf '%s\n' "$actual" > "$package_dir/usr/share/doc/ethersms-speech-engine/source-revision"
cat > "$package_dir/DEBIAN/control" <<'CONTROL'
Package: ethersms-speech-engine
Version: 1.9.5~dev-1
Architecture: arm64
Maintainer: Etherneco LTD
Depends: libc6 (>= 2.38), libstdc++6 (>= 14), libgcc-s1
Description: Offline whisper.cpp CLI for EtherSMS (models installed separately)
 Source revision is recorded in the installed documentation.
CONTROL
chmod 755 "$package_dir/DEBIAN"
dpkg-deb --root-owner-group --build "$package_dir" "$root/build/ethersms-speech-engine_1.9.5~dev-1_arm64.deb"
