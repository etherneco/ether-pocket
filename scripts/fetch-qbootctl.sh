#!/bin/bash
set -euo pipefail
mkdir -p /opt/etherpocket/qbootctl
cd /opt/etherpocket/qbootctl
apt-get download qbootctl:arm64
apt-get source qbootctl
for package in qbootctl_*_arm64.deb; do
 cp "$package" /mnt/c/projects.local/mobiam/build/
 dpkg-deb -I "$package"
done
