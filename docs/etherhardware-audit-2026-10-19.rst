EtherHardware architecture audit, 19 October 2026
================================================

The workspace has no Git metadata or AGENTS.md. EtherShell is Qt 6/C++ with
QML resources (ethershell/CMakeLists.txt). SettingsWorkspace.qml is the existing
Settings 2.0 router; qml/settings supplies semantic themes, cards, rows, sheets
and compact typography. Core/settings.cpp already reads system/storage/audio
information asynchronously. Core/Pocket own telemetry, brightness and sleep;
Media owns audio playback. These integrations must remain in place.

EtherMobile's shared C++ core uses NetworkManager and ModemManager. Its existing
ethermobile-data service owns Qualcomm IPA sessions. EtherBluetooth uses BlueZ
and its existing UART helper. EtherShare has a system Python D-Bus service
com.etherneco.EtherShare1 and a reusable asynchronous Qt client. Sharing's radio
quarantine is authoritative. No new component may start/stop these owners.
EtherAIR uses existing X11 display tooling. Distributor validates remote release
metadata and ARM64 architecture before offering external packages; publication
credentials are not present. Local Debian packaging is the delivery mechanism.

Preferences use Core's atomic JSON files and module-specific stores. Existing
PolicyKit uses scoped actions and mate-polkit; the GUI explicitly refuses root.
SSH uses the pinned build/mobian-known-hosts and existing deployment key.

Read-only physical audit confirms Debian 13.7/aarch64, 4.14.117-perf. Device Tree
reports SDX50M MTP 18827 15, so the UI must show that actual value without
inventing a OnePlus marketing model. /proc/config.gz is available. wlan0 binds
to icnss, with the vendor wlan module loaded. Many /sys/module entries are
built in. DRM has DSI, DP and Virtual connectors; Qualcomm KGSL is exposed.
V4L2 exposes video and many sensor subdevices, which alone do not prove camera
capture. ALSA has capture/playback nodes, which do not prove physical routing.
Android SSC, three IIO devices, UDC a600000.dwc3, dual_role_usb, and battery/USB
power supplies are exposed. No hardware interfaces are changed by this audit.

NetworkManager, ModemManager, BlueZ, SSH and EtherShare are active. The existing
ethermobile-data service is failed; prior evidence reports ESM timeout 1069.
AP is quarantined after WLAN recovery failure. These failures must remain
visible. No automatic radio probe, AP activation, firmware load or repair is safe.

Implementation decision: one unprivileged system discovery service aggregates
allowlisted sysfs/proc fields and read-only properties from existing D-Bus owners.
Cache-only versioned API plus explicit asynchronous diagnostics, filtered events
and bounded history provide the common registry. Session-only display/rendering
and audio evidence is inspected in the GUI user's context. Unknown/unreadable
facts remain unknown. A separate PolicyKit helper may install only reviewed
Debian userspace diagnostic tools, never kernels, vendor firmware or drivers.
Physical microphone/speaker tests require a deliberate user action.
