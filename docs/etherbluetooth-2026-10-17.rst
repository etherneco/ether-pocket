EtherBluetooth 0.1.0: implementation and hardware readiness
=========================================================

Later bring-up update: the native external UART driver is now operational;
normal-user discovery and two service restart cycles passed. This document
preserves the initial audit and application work. Current driver installation,
measured identifiers and limitations are in ``bluetooth-driver-2026-10-17.rst``.

Status
------

The native Qt 6/QML/C++ application is packaged for Debian ARM64 and installed
on the physical EtherPocket. It uses real BlueZ D-Bus interfaces; the device
list has no demonstration devices. The current phone has no registered HCI
controller, so Bluetooth support is **not complete**. Pairing, Bluetooth audio,
BLE and input-device hardware acceptance remain blocked.

The hardware audit preceded implementation and any configuration changes.
No driver or firmware was installed, no radio power was changed, and no
Bluetooth service restart, subsystem reset, boot change or reboot was performed.
Android partitions were opened for read-only firmware inventory only.

Verified baseline
-----------------

* Debian 13.7, ARM64, running kernel ``4.14.117-perf #6``.
* Device tree model ``SDX50M MTP 18827 15``; SM8150 platform.
* ``/vendor/bt_wcn3990`` declares ``compatible = qca,wcn3990``. This identifies
  the declared WCN3990 platform family, **not** a measured silicon/ROM revision.
* ``/dev/ttyHS0`` is bound to ``msm_geni_serial`` at
  ``soc/c8c000.qcom,qup_uart``, compatible ``qcom,msm-geni-serial-hs``.
  Its physical Bluetooth routing has not been independently exercised.
* ``CONFIG_BT=y``, BREDR and LE enabled. Bluetooth core is built in;
  its absence from ``lsmod`` would not imply a missing core.
* ``CONFIG_MSM_BT_POWER=y`` and ``CONFIG_BTFM_SLIM_WCN3990=y``.
  Vendor power driver is bound and ``/dev/btpower`` exists.
* ``CONFIG_BT_HCIUART`` and ``CONFIG_SERIAL_DEV_BUS`` are disabled.
  No ``hci*`` in ``/sys/class/bluetooth`` and no BlueZ Adapter1 object.
* ``CONFIG_BT_HIDP`` is disabled; ``CONFIG_UHID=y`` and
  ``CONFIG_HID_GENERIC=y``. Classic HIDP and BLE HID support must be
  evaluated separately; UHID alone does not prove keyboard or mouse operation.
* Bluetooth rfkill ``bt_power``: soft block 1, hard block 0.
  WLAN rfkill: unblocked. WLAN interface remained up.
* BlueZ 5.82 service active; system D-Bus and BlueZ root object accessible
  to the normal desktop user. A running daemon does not establish radio readiness.
* PipeWire 1.4.2, WirePlumber 0.5.8, ``libspa-0.2-bluetooth`` installed.
  PulseAudio compatibility reports PipeWire. Internal speaker sink is visible.
  No Bluetooth sink can be verified without a controller/connection.
* ``pkexec`` is absent: privileged recovery buttons are disabled with an
  explanation. ``polkitd`` alone does not supply ``pkexec``.

Subsystem classification: hardware declaration and power driver partially
working; kernel HCI UART support missing; rfkill blocked; HCI missing;
BlueZ and D-Bus working; firmware compatibility unknown; discovery, pairing,
Bluetooth audio and HID hardware tests blocked.

Evidence is in ``evidence/bluetooth-baseline-2026-10-17.json`` and
``evidence/bluetooth-firmware-partitions-2026-10-17.json``.

Qualcomm driver investigation
-----------------------------

The matching source and build output are available on EtherPocketBuild at
``/opt/etherpocket/kernel`` and ``/opt/etherpocket/out``. The running decompressed
``/proc/config.gz`` and build ``.config`` have the same SHA-256:

``7f2a8e023daf9912f45086a00b699d7cefaf7746718c24d952c2a4329868a01b``.

The build UTS release matches the running ``4.14.117-perf``. These checks are
prerequisites, not proof that a proposed module is safe or ABI-compatible.
Module signatures are enforced (``CONFIG_MODULE_SIG_FORCE=y``), while symbol
versioning is disabled. A candidate needs the exact generated headers,
compiler/ABI validation, exported-symbol checks, vermagic inspection and an
accepted signature. Do not copy a Debian 6.x kernel module onto this kernel.

The local ``drivers/bluetooth/hci_qca.c`` calls ``qca_uart_setup_rome`` and
prints ROME setup. ``btqca.c`` requests ROME rampatch/NVM names based on version.
There is no WCN3990 initialization path in this copy. Source hashes:

* hci_qca.c: ``4941e414a7be9c88ad419093cd03cdb3730680c3b2dcf59c990c82ee7f279fb8``.
* btqca.c: ``d68860580ad208eefa30c67b5c56e467dd94f00fecc5af04d2e23921a21c11b2``.

The vendor ``bluetooth-power.c`` exposes rfkill and a narrow ``/dev/btpower``
interface. It handles ``BT_CMD_PWR_CTRL`` (0xbfad); ``BT_CMD_CHIPSET_VERS``
sets a software value and **does not read a hardware ROM identifier**.
No such ioctl was invoked during this task.

Firmware investigation
----------------------

The inspected Linux firmware directories have no recognized Bluetooth
rampatch/NVM candidates. The Android ``bluetooth_a`` and ``bluetooth_b``
partitions are FAT16. Read-only directory and file reads found CRBTFW11/20/21,
CRNV11/20/21 and board-specific CRNV21 variants, plus APBT/APNV files.
Their sizes, hashes and short format headers are recorded in the inventory.
The slots contain different CRBTFW21 and CRNV21 contents; selecting one by
filename alone would be unsafe. No firmware binary was extracted or redistributed.

The Debian trixie firmware-atheros file list contains ``qca/crbtfw21.tlv``
and ``qca/crnv21.bin``. This is a distribution candidate, not verified firmware
for this board or ROM. The phone's current APT cache did not resolve that
package. Before installation, inspect the configured Debian non-free-firmware
repositories, authenticate Release metadata/package hashes through APT, review
licensing, and match ROM and board NVM requirements. No package installation
has been proposed as an automatic cure for a missing transport driver.

Sources checked:

* https://packages.debian.org/trixie/all/firmware-atheros/filelist
* https://raw.githubusercontent.com/torvalds/linux/v4.19/drivers/bluetooth/hci_qca.c
* https://raw.githubusercontent.com/torvalds/linux/v4.19/drivers/bluetooth/btqca.c

Remediation plan and acceptance gates
------------------------------------

1. Preserve the matching source, output config, generated headers, Module.symvers,
   known-good kernel and recovery path. Do all driver development in a separate
   build output. Do not rewrite the current build configuration.
2. Backport the upstream WCN3990-specific setup and firmware handling into a
   driver compatible with this kernel and its vendor GENI UART/power interfaces.
   Upstream v4.19 provides a WCN3990 implementation, but its serdev integration
   is not a drop-in solution: this kernel has serdev disabled and a separate
   vendor power device. A module-only route requires adapting the tty attachment
   and power ownership; it has not yet been built or verified.
3. Confirm regulators, UART routing, flow control, initial/operational baud rates
   and shared Wi-Fi coexistence before any hardware test. Do not bind a second
   power driver to existing regulator ownership or reset the shared subsystem.
4. Build the adapted UART/H4/QCA components against the exact running kernel.
   Check unresolved symbols, vermagic, config-sensitive structures and signature
   acceptance offline. Preserve rollback by keeping modules outside the installed
   module tree until a reviewed, explicitly authorized hardware trial.
5. Obtain the actual controller version through the verified initialization path.
   Select matching legally distributable firmware and board NVM. Record hashes
   and actual successful load evidence. Never rename an arbitrary TLV to satisfy
   a failed request.
6. With explicit driver/firmware authorization, test a temporary, supervised
   attachment without changing boot partitions or enabling it at boot. Require
   clean HCI registration, adapter power-on and bounded discovery while monitoring
   Wi-Fi and SSH. Roll back on UART errors, kernel faults or WLAN disruption.
7. If module-only adaptation cannot satisfy the existing core ABI/power interfaces,
   stop and report the additional kernel requirement. A kernel change requires
   a separately approved boot/recovery plan; none was performed here.
8. Only after HCI works, complete all physical audio, keyboard, mouse, BLE,
   restart, persistence, Wi-Fi coexistence and boot regression tests from the task.

This is a technically grounded development route, **not a ready-to-load driver**.
Unblocking rfkill or restarting BlueZ cannot add the disabled HCI transport.

Application architecture and implemented behavior
-------------------------------------------------

``etherbluetooth/`` is a standalone Qt 6 application. ``Bluetooth`` maintains
BlueZ ObjectManager snapshots and InterfacesAdded/Removed/PropertiesChanged
events. It re-registers its agent after a BlueZ owner change. Adapter and device
identity uses object paths and BlueZ addresses, never display names.

Implemented controls:

* Multiple adapter selection, power and time-limited discoverability.
* Explicit 30-second discovery with cancellation and cleanup of the app's scan.
* Real device list, pairing vs connection distinction, battery/RSSI when exposed,
  UUIDs, service-resolution state and device-specific errors.
* Pair, cancel, connect, disconnect, trust/untrust, local alias and confirmed forget.
* Agent1 PIN/passkey entry/display, numeric confirmation, pairing/service
  authorization, cancellation and 60-second unanswered-request rejection.
  Agent calls are accepted only from the current BlueZ bus owner.
* Per-device opt-in recovery of lost connections: 2/4/8/16-second retries,
  maximum four; disabled for untrusted devices, powered-off adapters and manually
  disconnected devices. This is loss recovery, not a background discovery service.
* Per-user notification preference, connection/pairing/error notifications,
  last-seen/last-connected timestamps and bounded 50-event per-device history.
* GATT service/characteristic inspection, explicit reads and start/stop notification
  requests. No arbitrary characteristic writes are issued.
* Input registration evidence from matching kernel input ``uniq`` values.
  This does not establish working pointer motion, scrolling or X11 key delivery.
* Actual pactl JSON sinks, sources and available card profiles, default input/output
  selection, bounded volume and mute. Advanced routing opens pavucontrol.
  The application does not install or replace the audio stack or reroute on connect.
* Twelve-stage read-only Driver Doctor and optional narrowly scoped PolicyKit
  recovery: Bluetooth-only software unblock or Bluetooth service restart. Both
  require an in-app impact confirmation and administrator authorization.

The graphical process refuses root. Recovery commands use fixed argument arrays
and trusted system executable paths. Normal Bluetooth operations use the system
bus permissions. No custom protocol stack, arbitrary privileged shell, firmware
installer, updater, trace upload or boot modification is included.

Persistence uses QSettings under
``~/.config/Etherneco/EtherBluetooth.conf`` (schema 1). The standalone process
uses umask 0077. BlueZ retains ownership of pairing keys, trust and aliases;
the application does not edit ``/var/lib/bluetooth``. Per-device history is bounded
but can contain metadata: keep diagnostic files local and review before sharing.
The read-only collector limits subprocess time and retained output; it never
starts btmon. Full firmware partition inventory remains a separate privileged
investigation and is not automatically repeated by the graphical audit.

EtherShell integration
----------------------

The shell source links the same event-driven backend. Quick settings toggle
power through D-Bus, show powered state and connected count, and launch
``etherbluetooth`` instead of blueman. ARM64 compilation succeeds.
The running shell binary/session has not been replaced or restarted; runtime
quick-settings verification remains outstanding. The standalone app and launcher
are installed and usable independently. AutoUpdate catalogues and the existing
six-application distribution scope are unchanged.

Build, installation, operation and removal
-----------------------------------------

On Debian with Qt 6 development packages, CMake, Ninja and a C++17 compiler::

    cmake -S etherbluetooth -B build/etherbluetooth -G Ninja -DCMAKE_INSTALL_PREFIX=/usr
    cmake --build build/etherbluetooth -j2
    cd build/etherbluetooth
    cpack -G DEB

The existing cross-build environment can use
``sh scripts/build-etherbluetooth-cross.sh``. The toolchain is shared with
EtherShell. Qt Core/Gui/Qml/Quick/QuickControls2/DBus/Test development components
are required; package runtime dependencies are emitted by CPack/shlibdeps.

Install or upgrade on the phone with::

    sudo apt install ./etherbluetooth_0.1.0_arm64.deb
    etherbluetooth

``pkexec`` and ``pavucontrol`` are recommended optional packages. Their absence
is explained in the UI. Firmware/driver installation is not part of app package
installation. The development SSH deployment helper installs only this app and
does not restart the shell or Bluetooth service.

The desktop launcher is EtherBluetooth. ``etherbluetooth --doctor`` opens
diagnostics; ``--audio`` opens routing. A CLI audit is available at::

    python3 /usr/libexec/etherbluetooth/etherbluetooth-doctor.py --output bluetooth-report.json

A user audit may be unable to read kernel configuration/logs. Those stages must
remain unknown; an administrator can run the read-only collector separately.
For pairing, enable a ready adapter, choose Add Device, select the discovered
device and confirm its real PIN/passkey request. Pairing does not imply connection;
select Connect afterward. Trust and automatic reconnect are separate user choices.

For connected-without-audio problems, refresh Audio and check for a real Bluetooth
sink and available card profile. Do not infer A2DP/HFP or codecs from device names
or UUIDs alone. Profile availability and active media transports differ.

Remove with ``sudo apt remove etherbluetooth``. Pairing state stays managed by
BlueZ; per-user preferences remain until explicitly deleted by their owner.
No system service or boot initialization hook is installed. Recovery requires
closing the app or reinstalling its package; the existing desktop stays intact.

Tests and remaining work
------------------------

* Six Python diagnostic-classification tests pass on the workstation.
* Four Qt policy test cases pass on the physical ARM64 phone (six QtTest entries
  including initialization/cleanup).
* One integration test exercises real D-Bus messages against an isolated fake
  BlueZ service: snapshots, connection events, scan calls, unknown-device rejection,
  explicit PIN reply and pairing rejection. It passes on ARM64 (three QtTest
  entries including initialization/cleanup). No fake service owns the real system bus.
* Native QML smoke runs load the main, Driver Doctor and Audio screens, exit
  cleanly and report zero adapters/devices as expected. Screenshots are stored
  in ``evidence/etherbluetooth-*-2026-10-17.png`` and were visually inspected.
* Both EtherBluetooth and the shell integration compile for ARM64.
* Test output, idle resource sample and final service checks are in
  ``evidence/bluetooth-tests-2026-10-17.txt`` and
  ``evidence/bluetooth-idle-2026-10-17.json``. The idle sample is short and has
  no controller; it cannot establish radio battery impact.

The measured 12-second idle sample used approximately 76 MiB resident memory
and accumulated zero additional CPU ticks (reported as 0.0% of one core over
that interval). This is not a claim of zero long-term CPU use.

Not yet verified/implemented to production acceptance: working WCN3990 transport
and exact ROM identification; compatible firmware load; all physical Bluetooth
tests; touch gestures during real pairing; long-running reconnect/suspend tests;
active audio-transport/codec telemetry; automatic audio event subscription;
full EtherControl/EtherAir runtime integration; low-battery notification policy;
optional btmon capture UI; packaged driver installation; startup auto-connect;
cross-version preference migrations; complete per-service repair rules;
boot/Android/glasses regression tests. No reboot or glasses test was performed.

The screenshot reference is a design reference, not hardware evidence. There are
no hardcoded Sony/Logitech devices, claimed battery levels or healthy-controller
statuses. The Definition of Done remains unmet until the hardware gates pass.
