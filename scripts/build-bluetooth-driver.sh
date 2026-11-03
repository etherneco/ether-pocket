#!/bin/sh
set -eu
source_root=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
module_dir=/opt/etherpocket/bluetooth-driver
python3 "$source_root/scripts/prepare-bluetooth-driver.py"
cp "$source_root/kernel/bluetooth-external.Makefile" "$module_dir/Makefile"
make -C /opt/etherpocket/kernel O=/opt/etherpocket/out -j2 \
 ARCH=arm64 CROSS_COMPILE=aarch64-linux-gnu- CC=aarch64-linux-gnu-gcc-12 \
 HOSTCFLAGS=-fcommon KCFLAGS="-Wno-error=format -Wno-error=strict-prototypes -Wno-error" \
 M="$module_dir" modules
aarch64-linux-gnu-strip --strip-debug "$module_dir/ether_hci_uart.ko"
/opt/etherpocket/out/scripts/sign-file sha512 \
 /opt/etherpocket/out/certs/signing_key.pem \
 /opt/etherpocket/out/certs/signing_key.x509 "$module_dir/ether_hci_uart.ko"
cp "$module_dir/ether_hci_uart.ko" "$source_root/build/ether_hci_uart.ko"
modinfo -F vermagic "$module_dir/ether_hci_uart.ko"
modinfo -F signer "$module_dir/ether_hci_uart.ko"
