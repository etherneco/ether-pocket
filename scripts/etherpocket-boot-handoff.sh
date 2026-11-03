#!/bin/busybox sh
# Called by PID 1 after validating and mounting the Mobian root read-only.
marker=/newroot/var/lib/etherpocket/next-system
for part in /sys/class/block/*; do
    label=$(sed -n 's/^PARTNAME=//p' "$part/uevent")
    [ -z "$label" ] && continue
    mkdir -p /dev/disk/by-partlabel
    ln -sf "/dev/${part##*/}" "/dev/disk/by-partlabel/$label"
done
if [ "$(cat "$marker" 2>/dev/null)" = etherPocket ]; then
    mount -o remount,rw /newroot || exit 1
    rm "$marker"
    sync
    mount -o remount,ro /newroot || exit 1
    exit 0
fi
while :; do
    /usr/bin/etherpocket-bootmenu /usr/share/etherpocket/bootmenu >> /run/bootmenu.log 2>&1
    result=$?
    case "$result" in
        0) exit 0 ;;
        10)
            if mount -o remount,rw /newroot; then
                printf 'Android\n' > "$marker.new"
                mv "$marker.new" "$marker"
                sync
                mount -o remount,ro /newroot || exit 1
                if /usr/sbin/etherpocket-slotctl -s b >> /run/bootmenu.log 2>&1; then
                    reboot -f
                fi
            fi
            echo 'Android handoff failed; returning to menu' >> /run/bootmenu.log
            sleep 2
            ;;
        *)
            # A missing panel/input must not trap the phone outside its OS.
            echo "Menu unavailable ($result); starting etherPocket" >> /run/bootmenu.log
            exit 0
            ;;
    esac
done
