#!/bin/sh
set -eu
restore_desktop() {
 systemctl start lightdm
 sleep 4
 echo 0 > /sys/class/backlight/panel0-backlight/bl_power
 echo 300 > /sys/class/backlight/panel0-backlight/brightness
}
trap restore_desktop EXIT
mkdir -p /run/bootmenu
mv /run/option-0.xrgb /run/option-1.xrgb /run/bootmenu/
systemctl stop lightdm
set +e
/run/etherpocket-bootmenu /run/bootmenu 120 > /run/bootmenu-preview.log 2>&1
result=$?
set -e
echo "Preview selection result: $result (no operating system handoff in this preview)"
cat /run/bootmenu-preview.log
