EtherHardware delivery and acceptance — 19 October 2026
======================================================

Installed result
----------------

The actual phone runs etherhardware 0.1.0 and the existing EtherShell with the
Hardware & Drivers Settings integration. The system discovery process runs as
etherhardware; the UI runs as UID 1000. D-Bus exposes 28 reusable capabilities.
The on-demand diagnostic inventory contains 265 components across all twelve
categories (counts include individual block partitions and camera subdevices).
The boot ID remains unchanged from before this task; no reboot was performed.

Delivered packages
------------------

* ``build/etherhardware_0.1.0_arm64.deb`` — service, API/CLI, collectors,
  safe repair helper, systemd/PolicyKit/D-Bus policy, tests, documentation,
  vendor metadata and Settings integration sources.
* ``build/ethershell-hardware_2.1.0_arm64.deb`` — compiled Settings host with
  the native asynchronous client and phone-first QML page.

Hardware package SHA-256:
``ecac1d2bc648ec062fb9e45eb37e18fc78ac2275362084e5dfdd38a97e0dea91``.
Shell package SHA-256:
``39dc755eec0019e3ef31a77d4fda343b667ecb36b7b11448adb143c9957a4bdd``.
Active executable SHA-256:
``79b001a29669ab9b6ccc85bffd937f1c36a8c055cbda1f129cabf704ad20f83b``.

The active stage is ``/opt/ethershell2/2.1.0-hardware-39dc755eec00``. Activation
checked the exact executable against the Debian package and preserved the old
stage ``/opt/ethershell2/2.1.0-share-ce4541d4d1d2``. The previous launcher is at
``/home/mobian/.local/bin/ethershell2-start.before-2.1.0-hardware-39dc755eec00``.
The guarded activation script automatically restores the previous launcher if
startup or routing checks fail. Only the user shell is restarted.

Verification
------------

All 17 core/security tests pass on Linux and the real ARM64 phone. They cover
built-in bindings absent from lsmod, ambiguous device detection, codec/capture
distinction, AP quarantine, memory/CPU counters, missing firmware correlation,
redaction, removal/history/restart behavior, and rejection of arbitrary packages,
third-party candidates, removals, upgrades and unreviewed dependencies.

The exact final ARM64 executable passes 904/904 UI checks: 226 each at 360x900,
1080x2340, 1000x600 and 1920x1080. All Settings routes and every hardware category
are rendered in both themes. Tests exercise category navigation, real component
detail sheets, horizontal geometry, Settings search, keyboard visibility and
preference persistence. Logs contain no QML warnings. Screenshots were visually
reviewed, including phone details in the dark theme and the live 1440x3120 panel.

Real D-Bus tests verify cached queries, unknown capabilities, invalid category
rejection, asynchronous diagnostics, JSON/text export, unprivileged access,
event subscription, service restart and history persistence. The PolicyKit
installer was exercised as root with the already-installed iw candidate; this
was an idempotent package transaction. New installation/authentication through
the desktop dialog was not simulated as a claim of user interaction. The missing
pkexec runtime dependency was installed from the configured signed Debian
repository; no existing package was upgraded or removed.

The vendor profile verifies all ten existing IPA files by name, size and hash
against EtherMobile's prior audit, without copying firmware or opening protected
partitions. Bluetooth reuses the existing transport's ROM/patch evidence. Camera
VIDIOC_QUERYCAP identifies sde_rotator and msm_vidc_driver codec nodes; this does
not certify camera sensors or image capture. Restricted wake-source and kernel
journal access remains restricted and is reported honestly.

The final short idle sample used 0.20% of one CPU core over 20 seconds, with
34,184 kB RSS and no inventory generation change. This is a short CPU/RSS sample,
not a battery-life or whole-device power measurement. No periodic full-device
or kernel-log scan is installed. Event coalescing and category throttles bound
refresh activity; rapidly changing throughput/signal metrics do not cause scans.

Live regression confirms Wi-Fi-bound HTTPS 200, powered Bluetooth evidence,
working SSH, and active NetworkManager, ModemManager, BlueZ, EtherShare,
etherpocket-modem, USB debugging/recovery and USB storage services. IPv4 forwarding
remains 0. The pre-existing ethermobile-data service remains failed, with data
capability false. AP is advertised by the driver but operationally blocked by
EtherShare's existing quarantine. No radio recovery, AP attempt, bearer startup,
network profile edit, firmware upload, kernel replacement, bootloader operation
or protected-partition write is part of this delivery.

Evidence
--------

* ``evidence/etherhardware-device.json``: install, tests, unprivileged service,
  report export and before/after service state.
* ``evidence/etherhardware-diagnostics.json``: current inventory, capability
  evidence, vendor hashes, read-only diagnostics and performance sample.
* ``evidence/etherhardware-settings-device``: per-size acceptance, individual
  checks, logs and screenshots.
* ``evidence/etherhardware-shell-stage.json`` and
  ``evidence/etherhardware-shell-deployment.json``: reviewed package and activation.
* ``evidence/etherhardware-shell-regression.json`` and
  ``evidence/etherhardware-live.png``: actual running stage, live services and UI.

Explicit acceptance limits
--------------------------

Unknown hardware remains unknown. The current vendor sensor subsystem does not
provide a verified standard accelerometer/gyroscope/proximity/light/magnetometer
provider. Modem SMS support is advertised, voice is unverified, and data is
currently failed. Controller-powered Bluetooth is not proof of discovery,
pairing, audio or PAN. Codec enumeration is not camera capture. PCM nodes are
not proof of acoustic routing. Microphone and speaker tests are available only
after deliberate user confirmation in Settings; they were not started unattended.
Physical external-display transmission, camera capture, sensor samples,
suspend/resume, physical cable events and battery drain require corresponding
hardware interaction and remain uncertified. No kernel/firmware repair is
claimed for the existing LTE/AP failures.

Distributor integration includes the EtherHardware catalog family and local
ARM64 release metadata. Remote publication remains dependent on actual release
credentials; the implementation does not invent a hosted release or signature.
