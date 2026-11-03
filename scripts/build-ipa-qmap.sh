#!/bin/sh
# Signed, temporary migration of an already-open non-QMAP WAN producer.
set -eu
root=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
module_dir=/opt/etherpocket/ipa-qmap
mkdir -p "$module_dir"
cp "$root/kernel/ether_ipa_qmap.c" "$module_dir/"
echo 'obj-m := ether_ipa_qmap.o' > "$module_dir/Makefile"
make -C /opt/etherpocket/kernel O=/opt/etherpocket/out -j2 \
 ARCH=arm64 CROSS_COMPILE=aarch64-linux-gnu- CC=aarch64-linux-gnu-gcc-12 \
 HOSTCFLAGS=-fcommon KCFLAGS="-Wno-error=format -Wno-error=strict-prototypes -Wno-error" \
 M="$module_dir" modules
/opt/etherpocket/out/scripts/sign-file sha512 \
 /opt/etherpocket/out/certs/signing_key.pem \
 /opt/etherpocket/out/certs/signing_key.x509 "$module_dir/ether_ipa_qmap.ko"
cp "$module_dir/ether_ipa_qmap.ko" "$root/build/"
modinfo -F vermagic "$module_dir/ether_ipa_qmap.ko"
modinfo -F signer "$module_dir/ether_ipa_qmap.ko"
