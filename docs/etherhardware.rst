EtherHardware
=============

EtherHardware is a read-only system registry, not another radio, modem, audio or
power manager. HardwarePage is embedded in EtherShell Settings 2.0 under System
→ Hardware & Drivers. It uses the existing themes, search, sheets and keyboard.
The service runs as etherhardware, never as root. Its group permissions allow
inventory reads; active device capture is exclusively an explicit GUI action
under the desktop user's existing audio permissions.

Build and install
-----------------

``cmake -S etherhardware -B build-hardware -DCMAKE_INSTALL_PREFIX=/usr`` then
``cmake --build build-hardware --target package`` produces the ARM64 Debian
package (pure Python service, architecture constrained for target integration).
Build EtherShell with its usual cross-build script to embed HardwarePage and
HardwareClient. The hardware package includes source integration components;
the shell package supplies the compiled existing Settings host. Install using
``dpkg -i etherhardware_0.1.0_arm64.deb``. No network/modem/audio service is
restarted. Removal stops only EtherHardware. History is retained for reinstall.
``systemctl restart etherhardware`` discards runtime evidence and recollects;
the saved registry file is an export, never treated as current proof on restart.

API version 1
-------------

System bus name/interface ``com.etherneco.EtherHardware1`` at
``/com/etherneco/EtherHardware1``. JSON documents have schemaVersion 1. Additive
fields may be introduced; clients must tolerate unknown fields and nulls.

* GetState() → s: cached inventory, categories, failures and capabilities.
* GetCapabilities() → s: cached capability envelope with ready/busy state.
* GetCapability(s identifier) → s: one capability, or JSON null if unknown.
* Refresh(s category) → void: queue a read-only targeted refresh, or ``all``.
* RunDiagnostics(s category) → void: asynchronous read-only refresh including
  module firmware metadata and bounded current-boot kernel journal evidence.
* Changed(s snapshot): emitted on busy and completed state transitions.
* GetHistory(s query, s component) → s: up to 200 redacted transitions, newest
  first. Empty component matches all; component filter is exact.
* ExportReport(s format) → s: ``json`` or ``text``; caller writes the destination.
* ClearHistory() → void: separately authorized by PolicyKit, with asynchronous
  completion. The registry query API never requires administrator privileges.

Reads never trigger scans or wake media devices. Explicit refreshes have global
and per-connection rate limits; diagnostics have a 30-second cooldown. The
single worker serializes collectors; D-Bus methods return cached data immediately.
Kernel uevents and existing D-Bus owner/property events invalidate relevant
categories, with event coalescing. There is no idle inventory or kernel-log poll.

Capability fields: id, hardwareProvider, backendProvider, supported,
operational, status, lastVerification, evidence and failureReason. Supported
and operational are nullable: null means unknown, false requires negative
evidence, true requires evidence scoped to the capability. Wi-Fi Working means
an activated link, not internet success. Battery Working means readable
telemetry. BlueZ adapter Working means powered controller control, not tested
discovery, pairing or audio. PCM/video nodes alone never prove microphone,
speaker or camera function. A DRM connector alone never proves external display
transmission. No automatic microphone, speaker, camera, AP, call, SMS, data
session, suspend, firmware load or storage-write test is performed.

Consumers
---------

All consumers can use the same GetCapability method or the CLI, e.g.
``etherhardware capability cellular.sms``. No additional module-specific
monitor is necessary. The Qt client is available for other applications.

* EtherMobile: cellular.data, cellular.sim, cellular.sms, cellular.voice.
* EtherBluetooth: bluetooth.adapter, bluetooth.audio and the provider's driver.
* EtherShare: wifi.ap, wifi.concurrent, usb.gadget, usb.network,
  ethernet.interface and bluetooth.pan. Its existing quarantine wins over AP
  capability advertisement. This registry never authorizes sharing activation.
* EtherAudio: audio.microphone, audio.speaker and ALSA/session evidence.
* EtherPower: power.battery, power.suspend and supply telemetry.
* EtherAIR: display.external, display.touch and session display evidence.
* EtherPhone: cellular.voice plus audio prerequisites. Unknown voice support
  must disable automatic calling assumptions.

Firmware and maintenance
------------------------

Driver binding and module linkage come from sysfs; bound drivers without a
module link are identified as built in. Kernel config is read from config.gz or
the running kernel's boot config. A missing module in lsmod is never treated as
a missing driver. Unexposed binding/dependency data remains unknown. On-demand
modinfo dependencies are checked in firmware search paths, including compressed
files; missing files are classified missing only with a correlated failed load
request. Journal permission denial remains visible. Built-in/vendor firmware
dependencies not described by modinfo cannot be certified by this mechanism.
The exact model/kernel-matched vendor profile reuses EtherMobile's ten-file IPA
audit metadata to check names, sizes and hashes on demand, without opening Android
partitions. It distributes no firmware binaries. Bluetooth's existing runtime
manifest contributes ROM/patch/transport evidence without sending new HCI commands.
Camera diagnostics issue VIDIOC_QUERYCAP only and distinguish codec/memory-to-memory
nodes from capture-only nodes. No camera stream or control is enabled.

The PolicyKit repair helper accepts only reviewed diagnostic tool package names
and the reviewed candidate version. It checks Debian 13 ARM64, configured
official trixie repositories, and a simulated APT transaction. It rejects
removals, upgrades of existing packages, and unreviewed dependencies. APT keeps
its signature verification. If a safe plan cannot be produced, the UI explains
the maintenance requirement. No repository is added, no APT update is run, and
no arbitrary command or package argument is accepted. No driver, DKMS, kernel,
modem firmware, calibration, bootloader or protected partition write is exposed.
Installing an inspection tool does not imply hardware has been repaired.

Privacy and persistence
-----------------------

Only selected properties are copied from the existing owners. Subscriber IDs,
messages, credentials, Wi-Fi profile settings and Bluetooth peer lists are never
queried. Reports and history additionally redact sensitive key names, MACs,
long identifiers and personal home paths. Raw kernel logs are never exported.
SQLite history retains at most 1,000 transitions and is held in a mode-0700 state
directory. JSON/text reports are exported under the user's Documents/EtherHardware
with owner-only permissions. Session audio/graphics inspection is transient and
does not enter shared history. Explicit microphone tests use a private temporary
directory and delete the short recording on completion.

Validation
----------

Run ``python3 -m unittest discover -s etherhardware/tests -v``. Fixtures cover
Android built-in binding, missing interfaces, operational status, firmware
correlation, capability ambiguity, redaction, history bounding, removal and
restart. Real device acceptance and remaining physical tests are recorded in
``evidence/etherhardware-*.json`` and the delivery report. Package installation
does not certify physical camera, acoustic, external-display or suspend tests.
