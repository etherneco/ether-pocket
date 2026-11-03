#!/usr/bin/env python3
"""Prepare external UART + Qualcomm IBS from the exact running vendor source.

The Linux HCI core and Bluetooth protocol stack are unchanged. Only the UART
transport is built. Board boot/version/address/baud setup runs in the bounded
userspace initializer, so the legacy ROME firmware setup must not execute.
"""
from pathlib import Path
import hashlib
import shutil

kernel = Path('/opt/etherpocket/kernel')
out = Path('/opt/etherpocket/out')
module = Path('/opt/etherpocket/bluetooth-driver')
expected = '7f2a8e023daf9912f45086a00b699d7cefaf7746718c24d952c2a4329868a01b'
if hashlib.sha256((out/'.config').read_bytes()).hexdigest() != expected:
    raise SystemExit('Kernel configuration changed: revalidate ABI before building')
module.mkdir(exist_ok=True)
for name in ['hci_ldisc.c', 'hci_h4.c', 'hci_uart.h', 'btintel.h', 'btbcm.h', 'btqca.h']:
    shutil.copyfile(kernel/'drivers/bluetooth'/name, module/name)
source = (kernel/'drivers/bluetooth/hci_qca.c').read_text()
if hashlib.sha256(source.encode()).hexdigest() != '4941e414a7be9c88ad419093cd03cdb3730680c3b2dcf59c990c82ee7f279fb8':
    raise SystemExit('QCA source changed: review transport adaptation')
start = source.index('static uint8_t qca_get_baudrate_value(')
end = source.index('static struct hci_uart_proto qca_proto =', start)
source = source[:start] + '''/* The board initializer has already verified version, address and baud.
 * Keep the upstream Qualcomm in-band sleep framing and state machine.
 * No ROME firmware request or unverified WCN firmware upload is performed.
 */
static int qca_setup(struct hci_uart *hu)
{
    struct qca_data *qca = hu->priv;
    /* Resident firmware has not negotiated host-initiated IBS sleep. */
    clear_bit(STATE_IN_BAND_SLEEP_ENABLED, &qca->flags);
    qca_debugfs_init(hu->hdev);
    BT_INFO("%s: EtherPocket preinitialized Qualcomm UART (host IBS disabled)", hu->hdev->name);
    return 0;
}

''' + source[end:]
source = source.replace('.init_speed\t= 115200,', '.init_speed\t= 0,')
source = source.replace('.oper_speed\t= 3000000,', '.oper_speed\t= 0,')
(module/'hci_qca.c').write_text(source)
