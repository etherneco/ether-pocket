#!/bin/bash
set -euo pipefail
cat > /etc/apt/sources.list.d/etherpocket-debug-source.sources <<'EOF'
Types: deb-src
URIs: http://deb.debian.org/debian
Suites: trixie trixie-updates
Components: main
Signed-By: /usr/share/keyrings/debian-archive-keyring.pgp

Types: deb-src
URIs: http://deb.debian.org/debian-security
Suites: trixie-security
Components: main
Signed-By: /usr/share/keyrings/debian-archive-keyring.pgp
EOF
apt-get update
mkdir -p /opt/etherpocket/xorg-source
cd /opt/etherpocket/xorg-source
apt-get source xorg-server
