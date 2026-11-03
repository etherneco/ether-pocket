#!/bin/sh
set -eu
root=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
stage=/opt/etherpocket/bluetooth-package
install -d "$stage/DEBIAN" "$stage/usr/libexec/etherbluetooth" \
 "$stage/usr/lib/systemd/system" "$stage/lib/modules/4.14.117-perf/extra/etherbluetooth"
install -m 0644 "$root/build/ether_hci_uart.ko" "$stage/lib/modules/4.14.117-perf/extra/etherbluetooth/"
install -m 0755 "$root/scripts/etherbluetooth-uart.py" "$root/scripts/etherbluetooth-uart-probe.py" "$stage/usr/libexec/etherbluetooth/"
install -m 0644 "$root/config/etherbluetooth-uart.service" "$stage/usr/lib/systemd/system/"
install -d "$stage/usr/share/doc/etherbluetooth-gm1920-driver/source"
install -m 0644 /opt/etherpocket/bluetooth-driver/hci_ldisc.c /opt/etherpocket/bluetooth-driver/hci_h4.c /opt/etherpocket/bluetooth-driver/hci_qca.c /opt/etherpocket/bluetooth-driver/*.h /opt/etherpocket/bluetooth-driver/Makefile "$stage/usr/share/doc/etherbluetooth-gm1920-driver/source/"
install -m 0644 /opt/etherpocket/kernel/COPYING "$stage/usr/share/doc/etherbluetooth-gm1920-driver/copyright"
cat > "$stage/DEBIAN/control" <<'EOF'
Package: etherbluetooth-gm1920-driver
Version: 0.1.0
Architecture: arm64
Maintainer: Etherneco LTD
Depends: python3, kmod, bluez
Description: Native Bluetooth UART transport for the validated GM1920 vendor kernel
 Signed external UART module and board initializer for 4.14.117-perf.
 Does not replace the kernel, flash partitions or redistribute firmware.
EOF
cat > "$stage/DEBIAN/preinst" <<'EOF'
#!/bin/sh
set -eu
test "$(uname -r)" = 4.14.117-perf || { echo 'Unsupported kernel ABI' >&2; exit 1; }
python3 -c 'import gzip,hashlib; assert hashlib.sha256(gzip.open("/proc/config.gz","rb").read()).hexdigest()=="7f2a8e023daf9912f45086a00b699d7cefaf7746718c24d952c2a4329868a01b", "Unvalidated kernel configuration"'
EOF
cat > "$stage/DEBIAN/postinst" <<'EOF'
#!/bin/sh
set -eu
if [ "$1" = configure ]; then
 depmod 4.14.117-perf
 systemctl daemon-reload
 systemctl enable --now etherbluetooth-uart.service
fi
EOF
cat > "$stage/DEBIAN/prerm" <<'EOF'
#!/bin/sh
set -eu
if [ "$1" = remove ] || [ "$1" = upgrade ]; then
 systemctl stop etherbluetooth-uart.service
 if [ "$1" = remove ]; then systemctl disable etherbluetooth-uart.service; fi
 if [ -d /sys/module/ether_hci_uart ]; then modprobe -r ether_hci_uart; fi
fi
EOF
cat > "$stage/DEBIAN/postrm" <<'EOF'
#!/bin/sh
set -eu
systemctl daemon-reload
depmod 4.14.117-perf
EOF
chmod 0755 "$stage/DEBIAN/preinst" "$stage/DEBIAN/postinst" "$stage/DEBIAN/prerm" "$stage/DEBIAN/postrm"
dpkg-deb --root-owner-group --build "$stage" "$root/build/etherbluetooth-gm1920-driver_0.1.0_arm64.deb"
