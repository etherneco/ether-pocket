EtherPocket Bluetooth driver: operational bring-up
=================================================

Current result
--------------

The signed native UART module is installed and running on the physical GM1920.
Linux registers ``hci0``; BlueZ powers it on/off and discovers real nearby
devices. The normal ``mobian`` desktop user successfully toggled controller
power and performed a ten-second discovery, finding 17 devices, 16 with RSSI
properties during that scan. Discovery was explicitly stopped afterward.

Two subsequent service restart/discovery cycles both returned a powered
controller, the same configured address, and 17 discovery results. Autostart
is enabled for ``etherbluetooth-uart.service``. A complete phone reboot/cold boot
has not been tested. Pairing, Bluetooth audio and HID input still require a
user-owned device for hardware validation; nearby third-party devices were not
paired or connected.

Wi-Fi stayed associated (NetworkManager connected, signal -35 dBm). A TCP
connection to Debian HTTPS through a socket explicitly bound to ``wlan0``
succeeded. Initial gateway ping attempts used an unsupported inetutils-ping
option; those attempts are invalid tests, not evidence of Wi-Fi failure.
USB SSH and the graphical desktop remained active.

The working kernel and all Android/boot partitions are unchanged. No firmware
binary was installed, extracted for distribution, or uploaded to the controller.

What changed
------------

* Built ``ether_hci_uart.ko`` against the exact running vendor kernel output,
  with the same GCC 12 cross compiler and kernel configuration. Its vermagic is
  ``4.14.117-perf SMP preempt mod_unload aarch64``. The module is signed by the
  existing kernel build key; enforced kernel signature validation accepted it.
  No force-load or signature bypass was used.
* Reused the vendor kernel's native HCI line discipline, H4 framing and Qualcomm
  receive/state-machine code. The unchanged Linux Bluetooth core and BlueZ remain
  authoritative. The old ROME setup callback is replaced with a board-preinitialized
  transport callback, so it cannot request an incompatible ROME firmware file.
* Added a narrow root initializer for the inspected GENI UART ``/dev/ttyHS0``.
  It uses the existing Bluetooth rfkill driver and GENI clock-vote ioctls, sends
  the documented Qualcomm Bluetooth boot pulses, reads and validates the actual
  controller version, configures the address and UART rate, and attaches native
  protocol 8. It retains the clock vote for reliable transport operation.
* UART communication is verified at 3,000,000 baud. This avoids the bandwidth
  restriction of the first successful 115,200-baud discovery experiment.
* Added a systemd service with a bounded startup, three-failure restart limit,
  no background discovery, strict filesystem access and event-driven idle wait.
  It validates the exact kernel build/configuration before modprobe. A different
  kernel requires a rebuilt and revalidated module.
* Updated Driver Doctor to recognize a real loaded external transport even though
  the unchanged kernel's built-in HCI UART configuration remains disabled.

Actual controller evidence
--------------------------

The device-tree declaration is ``qca,wcn3990``. The UART returned Qualcomm
product ``0x0000000a``, SoC ``0x40010224``, ROM build ``0x1001`` and patch
``0x6699``. Standard HCI reports manufacturer 29 (Qualcomm), HCI/LMP version 4.2.
These measured identifiers supersede any inference from the phone model or DT
node name; a more specific retail silicon name has not been established.

The resident controller firmware successfully answers version, reset, address,
feature, power and discovery commands. The previously inventoried Android TLVs
advertise ROM builds 0x0101/0x0200/0x0201, rather than measured 0x1001. They were
therefore not loaded. No claim is made that a particular Linux or Android host
firmware file has been validated for this controller.

The initial controller address was a non-unique default. A persistent locally
configured unicast address is now stored in
``/var/lib/etherbluetooth/controller-address`` with mode 0600. It is explicitly
a local configuration, not a claimed factory hardware identifier. The initializer
sets it through the existing Qualcomm NVM-access HCI command and verifies it with
Read BD_ADDR after reset. Administrators must preserve this file across reinstalls
to preserve pairing identity. BlueZ owns pairing keys under its normal state tree.

Host-initiated Qualcomm IBS sleep has not been negotiated with the resident
firmware and is disabled. A test that enabled it prevented controller startup;
it was rolled back. The transport still recognizes incoming Qualcomm sleep/wake
framing. Holding the GENI clock vote is a deliberate reliability choice; idle
radio power and battery impact remain unmeasured. Do not claim production sleep
or mobile-power optimization from these tests.

Installed files and package
---------------------------

``build/etherbluetooth-gm1920-driver_0.1.0_arm64.deb`` contains:

* ``/lib/modules/4.14.117-perf/extra/etherbluetooth/ether_hci_uart.ko``.
* ``/usr/libexec/etherbluetooth/etherbluetooth-uart.py`` and the bounded boot probe.
* ``/usr/lib/systemd/system/etherbluetooth-uart.service``.
* Adapted module C/header sources, Makefile and the kernel licence under
  ``/usr/share/doc/etherbluetooth-gm1920-driver/``. Private signing keys are not
  included.

Inspect with::

    systemctl status etherbluetooth-uart.service
    bluetoothctl show
    journalctl -u etherbluetooth-uart.service -n 40 --no-pager

The live status manifest ``/run/etherbluetooth/controller.json`` contains only
transport/version details, not the configured address or pairing keys. Doctor
reads it without administrator access. Its read-only audit correctly leaves a
new discovery test unknown instead of silently scanning.

Rebuild in the existing EtherPocketBuild environment::

    sh scripts/build-bluetooth-driver.sh
    sh scripts/package-bluetooth-driver.sh

``prepare-bluetooth-driver.py`` checks the matching kernel config and QCA source
hash before adapting the external transport. It does not rewrite the kernel
configuration or boot images. The package preinstallation checks the running
ABI/config; the service additionally checks the exact ``#6`` kernel build before
loading. Normal upgrades stop the transport and disconnect Bluetooth devices;
they should not run during an important Bluetooth connection.

Recovery/removal
----------------

To stop the added transport without changing the kernel or Wi-Fi::

    sudo systemctl disable --now etherbluetooth-uart.service
    sudo modprobe -r ether_hci_uart

Remove with ``sudo apt remove etherbluetooth-gm1920-driver``. Its removal script
stops/disables the service and unloads only this module. Local controller identity
and BlueZ pairings are retained. This returns the machine to having no attached
Bluetooth HCI transport, as in the original baseline. Do not remove the WLAN
module or reset shared Qualcomm subsystems.

The pre-existing 4.14 module tree lacks modules.order/modules.builtin metadata;
modern depmod emits warnings about those absent files. Module dependency generation
and loading still succeeded. No fabricated metadata was installed to hide these
warnings.

Validation evidence
-------------------

* ``evidence/bluetooth-native-user-radio-test-2026-10-17.json``: normal-user
  off/on, discovery and stopped-scan verification.
* ``evidence/bluetooth-driver-restart-tests-2026-10-17.json``: two transport
  reinitialization cycles, stable identity and repeated discovery.
* ``evidence/bluetooth-wifi-coexistence-2026-10-17.json``: WLAN association,
  explicitly WLAN-bound Debian HTTPS TCP success, and invalid ping-command detail.
* ``evidence/bluetooth-driver-user-audit-2026-10-17.json``: Driver Doctor evidence
  read as the desktop user with external module registered.
* ``evidence/bluetooth-driver-install-2026-10-17.txt``: package and autostart status.
* ``evidence/bluetooth-driver-artifacts-2026-10-17.json``: package/module hashes.
* Six Linux-only UART parser/configuration tests and seven Doctor classification
  tests pass. Parser tests cover the real zero-opcode vendor completion format,
  sleep/wake framing, command rejection, timeouts and persistent address permissions.
  They use local socket pairs and never simulate hardware validation.

Initial negative experiments included a plain H4 reattach without board boot
initialization, unnegotiated host IBS sleep, and a BlueZ Busy response while the
adapter was still being automatically powered. The final initializer performs
board initialization on every attachment, disables unnegotiated host IBS, and
the restart test waits for powered readiness. No incompatible TLV was attempted.

Protocol/source references:

* The exact local 4.14 vendor ``drivers/bluetooth/hci_ldisc.c``, ``hci_h4.c``,
  ``hci_qca.c``, ``bluetooth-power.c`` and GENI serial ioctl implementation.
* https://raw.githubusercontent.com/torvalds/linux/v4.19/drivers/bluetooth/hci_qca.c
  (Bluetooth-only UART boot pulse/baud sequencing).
* https://raw.githubusercontent.com/torvalds/linux/v4.19/drivers/bluetooth/btqca.c
  (Qualcomm version and address-command formats).

EtherControl shortcut correction
--------------------------------

The running shell build still invoked ``blueman-manager`` for its Bluetooth
button, even though current shell source launches EtherBluetooth directly. A
compatibility entry point is installed only in that build's private executable
directory, which already leads its PATH. It activates the existing EtherBluetooth
window or launches ``/usr/bin/etherbluetooth``. The system Blueman executable is
unchanged. The correction persists through normal restarts of this staged shell;
new shell builds use the direct source route.

``scripts/fix-active-bluetooth-launcher.py`` validates the active managed stage
and saves rollback metadata under ``/var/backups/etherbluetooth-launcher``.
The live ``bluetooth-settings`` action was verified to focus the window class
``etherbluetooth.EtherBluetooth``. The shell process and Bluetooth service stayed
running. Evidence: ``evidence/bluetooth-shortcut-test-2026-10-17.json``.
