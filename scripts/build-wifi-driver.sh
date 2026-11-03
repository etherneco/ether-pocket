#!/bin/bash
set -euo pipefail
src=/opt/etherpocket/wifi-source/android_kernel_oneplus_sm8150-lineage-17.1/drivers/staging
make -C /opt/etherpocket/kernel O=/opt/etherpocket/out -j8 \
 ARCH=arm64 CROSS_COMPILE=aarch64-linux-gnu- CC=aarch64-linux-gnu-gcc-12 \
 HOSTCFLAGS=-fcommon KCFLAGS="-Wno-error=format -Wno-error=strict-prototypes -Wno-error" \
 M="$src/qcacld-3.0" WLAN_ROOT="$src/qcacld-3.0" \
 WLAN_COMMON_ROOT=../qca-wifi-host-cmn WLAN_COMMON_INC="$src/qca-wifi-host-cmn" \
 MODNAME=wlan BOARD_PLATFORM=msmnile CONFIG_QCA_CLD_WLAN=m modules
aarch64-linux-gnu-strip --strip-debug "$src/qcacld-3.0/wlan.ko"
/opt/etherpocket/out/scripts/sign-file sha512 \
 /opt/etherpocket/out/certs/signing_key.pem \
 /opt/etherpocket/out/certs/signing_key.x509 "$src/qcacld-3.0/wlan.ko"
cp "$src/qcacld-3.0/wlan.ko" /mnt/c/projects.local/mobiam/build/wlan.ko
