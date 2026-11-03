#!/bin/bash
set -euo pipefail
export ETHERPOCKET_PANEL_REFRESH_TEST=1
bash /mnt/c/projects.local/mobiam/scripts/build-xorg-driver.sh
cp /mnt/c/projects.local/mobiam/build/modesetting_drv-fixed.so /mnt/c/projects.local/mobiam/build/modesetting_drv-panel-test.so
