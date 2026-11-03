# Against the unchanged, matching 4.14.117-perf build output.
obj-m += ether_hci_uart.o
ether_hci_uart-y := hci_ldisc.o hci_h4.o hci_qca.o
ccflags-y += -DCONFIG_BT_HCIUART_H4=1 -DCONFIG_BT_HCIUART_QCA=1
