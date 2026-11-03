#!/bin/sh
# Read/check only an unbound diagnostic gadget; retain the working ADB gadget.
set -eu
g=/config/usb_gadget/etherpocket-probe
mkdir -p "$g"
cd "$g"
printf 0x1d6b > idVendor
printf 0x0104 > idProduct
mkdir -p strings/0x409 configs/c.1/strings/0x409 functions/rndis.usb0
printf EtherPocket-probe > strings/0x409/serialnumber
printf 02:50:00:00:00:02 > functions/rndis.usb0/dev_addr
printf 02:50:00:00:00:01 > functions/rndis.usb0/host_addr
printf 1 > os_desc/use
printf 0xcd > os_desc/b_vendor_code
printf MSFT100 > os_desc/qw_sign
printf RNDIS > functions/rndis.usb0/os_desc/interface.rndis/compatible_id
printf 5162001 > functions/rndis.usb0/os_desc/interface.rndis/sub_compatible_id
ln -s functions/rndis.usb0 configs/c.1/
ln -s configs/c.1 os_desc/
echo 'Unbound RNDIS gadget creation succeeded; working ADB remains bound.'
echo 'RNDIS ifname:'
cat functions/rndis.usb0/ifname
echo 'Working gadget UDC:'
cat /config/usb_gadget/g1/UDC
