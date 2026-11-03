#!/bin/bash
set -euo pipefail
workspace=/mnt/c/projects.local/mobiam
audio=/opt/etherpocket/audio-source/android_kernel_oneplus_sm8150-77a0c0f8a59c868236c495373d98b03a819c0108/techpack/audio
kernel=/opt/etherpocket/kernel
out=/opt/etherpocket/out
test -d "$audio"
python3 "$workspace/scripts/patch-audio-pdr.py"
printf 'obj-y += ipc/ dsp/ dsp/codecs/ soc/ asoc/ asoc/codecs/ asoc/codecs/wcd934x/ asoc/codecs/wcd9360/ asoc/codecs/tfa9894/\n' > "$audio/Kbuild"
# Standalone builds must not export all internal Kbuild variables or read
# Android's per-directory symbol files; modpost resolves this whole tree.
find "$audio" -name Kbuild -exec sed -i '/^[[:space:]]*export[[:space:]]*$/d; /KBUILD_EXTRA_SYMBOLS +=/d' {} +
ln -sf "$kernel/drivers/pinctrl/core.h" "$audio/soc/core.h"
ln -sf "$kernel/drivers/pinctrl/pinctrl-utils.h" "$audio/soc/pinctrl-utils.h"
ln -sf "$kernel/drivers/base/regmap/internal.h" "$audio/include/soc/internal.h"
mapfile -t options < <(sed 's/=y$/=m/' "$audio/config/sm8150auto.conf")
make -C "$kernel" O="$out" -j8 ARCH=arm64 \
 CROSS_COMPILE=aarch64-linux-gnu- CC=aarch64-linux-gnu-gcc-12 \
 HOSTCFLAGS=-fcommon KCFLAGS="-Wno-error=format -Wno-error=strict-prototypes -Wno-error" \
 M="$audio" AUDIO_ROOT="$audio" MODNAME=audio BOARD_PLATFORM=msmnile \
 "${options[@]}" modules
mkdir -p "$workspace/build/audio-modules"
while IFS= read -r module; do
 aarch64-linux-gnu-strip --strip-debug "$module"
 "$out/scripts/sign-file" sha512 "$out/certs/signing_key.pem" "$out/certs/signing_key.x509" "$module"
 cp "$module" "$workspace/build/audio-modules/"
done < <(find "$audio" -name '*.ko')
