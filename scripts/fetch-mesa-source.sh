#!/bin/bash
set -euo pipefail
mkdir -p /opt/etherpocket/mesa-source
cd /opt/etherpocket/mesa-source
apt-get source mesa
