#!/bin/sh
# Use configfs RNDIS with Microsoft OS descriptors, DHCP without a router.
# For native RAM tests only; no changes to persistent phone volumes.
set -eu
grep -q 'etherpocket.ramboot=1' /proc/cmdline
mkdir -p /sys/kernel/config
grep -qs ' /sys/kernel/config configfs ' /proc/mounts || mount -t configfs none /sys/kernel/config
gadget=/sys/kernel/config/usb_gadget/etherpocket
if [ ! -d "$gadget" ]; then
    mkdir "$gadget"
    cd "$gadget"
    printf 0x1d6b > idVendor
    printf 0x0104 > idProduct
    printf 0xEF > bDeviceClass
    printf 0x02 > bDeviceSubClass
    printf 0x01 > bDeviceProtocol
    mkdir -p strings/0x409 configs/c.1/strings/0x409 functions/rndis.usb0
    printf EtherPocket-GM1920 > strings/0x409/serialnumber
    printf EtherPocket > strings/0x409/manufacturer
    printf 'Native Mobian USB debug' > strings/0x409/product
    # Qualcomm's downstream configfs rejects MAC attributes before bind
    # with ENODEV, and rejects stores after function allocation with EBUSY.
    # Use the generated MAC addresses; identify the host device by USB IDs.
    printf 1 > os_desc/use
    printf 0xcd > os_desc/b_vendor_code
    printf MSFT100 > os_desc/qw_sign
    printf RNDIS > functions/rndis.usb0/os_desc/interface.rndis/compatible_id
    printf 5162001 > functions/rndis.usb0/os_desc/interface.rndis/sub_compatible_id
    ln -s functions/rndis.usb0 configs/c.1/
    ln -s configs/c.1 os_desc/
    for attempt in $(seq 1 45); do
        udc=$(ls /sys/class/udc | head -1)
        [ -z "$udc" ] || break
        sleep 1
    done
    [ -n "$udc" ]
    printf '%s' "$udc" > UDC
fi
iface=$(cat "$gadget/functions/rndis.usb0/ifname")
ip link set "$iface" up
ip address replace 10.77.0.2/24 dev "$iface"
cat > /run/etherpocket-udhcpd.conf <<EOF
start 10.77.0.1
end 10.77.0.1
interface $iface
option subnet 255.255.255.0
option lease 3600
lease_file /run/etherpocket-udhcpd.leases
pidfile /run/etherpocket-udhcpd.pid
EOF
exec /bin/busybox udhcpd -f /run/etherpocket-udhcpd.conf
