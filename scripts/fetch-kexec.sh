#!/bin/bash
set -euo pipefail
mkdir -p /opt/etherpocket/kexec-packages
cd /opt/etherpocket/kexec-packages
apt-get download kexec-tools:arm64 libfdt1:arm64
apt-get source kexec-tools
for package in *arm64.deb; do
 dpkg-deb -I "$package"
 dpkg-deb -x "$package" /opt/etherpocket/kexec-runtime
done
cp /opt/etherpocket/kexec-runtime/usr/sbin/kexec /mnt/c/projects.local/mobiam/build/kexec-arm64
readelf -d /opt/etherpocket/kexec-runtime/usr/sbin/kexec | grep NEEDED
