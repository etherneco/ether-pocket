#!/bin/sh
# Temporary recovery USB test with automatic restoration of the ADB gadget.
set -eu
g=/config/usb_gadget/etherpocket-probe
original=/config/usb_gadget/g1
udc=$(cat "$original/UDC")
[ -n "$udc" ]
restore() {
    printf '\n' > "$g/UDC"
    printf '%s' "$udc" > "$original/UDC"
    echo 'Original ADB gadget restored.'
}
cd "$g"
printf 0xEF > bDeviceClass
printf 0x02 > bDeviceSubClass
printf 0x01 > bDeviceProtocol
printf 1 > os_desc/use
printf 0xcd > os_desc/b_vendor_code
printf MSFT100 > os_desc/qw_sign
printf RNDIS > functions/rndis.usb0/os_desc/interface.rndis/compatible_id
printf 5162001 > functions/rndis.usb0/os_desc/interface.rndis/sub_compatible_id
[ -L os_desc/c.1 ] || ln -s configs/c.1 os_desc/
trap restore EXIT
printf '\n' > "$original/UDC"
printf '%s' "$udc" > UDC
echo 'RNDIS bound; ifname and generated MAC:'
cat functions/rndis.usb0/ifname
cat functions/rndis.usb0/dev_addr
cat functions/rndis.usb0/host_addr
sleep 15
