EtherPocket: native ARM64 Linux with Xorg
========================================

EtherMAP implementation on 2026-10-21
------------------------------------

EtherMAP adds native OSM raster maps, licensed MBTiles, consented IP estimates
through EtherLocation, local segmented tracks and GPX, saved places, configurable
geocoding/routing, and EtherShell launcher/Location settings/catalogue integration.
The ARM64 application and EtherLocation 0.1.1 are installed on the phone, and the
tested shell integration is active. On-device offline map rendering, 60 tests,
permission denials and the live launcher passed. Verified GNSS, production
provider acceptance and signed AutoUpdate publication remain pending. See
docs/ethermap-device-delivery-2026-10-21.rst, docs/ethermap.rst and
evidence/ethermap-delivery.json for exact scope and verification.

EtherBackup commissioning on 2026-10-21
--------------------------------------

EtherBackup adds Restic encryption, incremental backup, SQLite online export,
verified sample restores, private isolated recovery, retention, an independent
administrator CLI and mandatory EtherUpdate pre-install recovery points. The
native backup coordinator and update hook are installed; scheduling and real-data
destinations remain unconfigured until independent storage/password commissioning.
The EtherShell Backup & Restore Settings page is active after four-size,
light/dark acceptance, preserving the newer EtherMAP integration. The final
handset run passed 35 backup tests and 39 update tests. No full-system recovery, USB acceptance or signed publication is
claimed. See docs/etherbackup.rst and the delivery evidence for exact status.

EtherSensors independent framework on 2026-10-21
-----------------------------------------------

EtherSensors 0.1.0 is installed as the native session sensor owner, with an
ARM64 ether-sensors package, compatible read-only IIO provider, sensor registry,
bounded permission-controlled subscriptions, power policy, diagnostics, and
EtherShell System / Sensors & Motion plus Quick Settings integration.

The real handset audit found only PMIC ADC IIO channels and unverified Qualcomm
SSC/vendor proximity interfaces. No changing motion, light or near/far samples
were verified. Fusion, gestures, automatic rotation/brightness, call proximity,
calibration and EtherAIR motion therefore remain blocked. Task 10 is incomplete;
no simulated hardware is advertised. Signed publication is blocked by missing
EtherUpdate credentials, publisher keys and component mappings.

25 sensor tests, 20 hardware regressions, eight real D-Bus authorization
rejections and light/dark UI checks at four sizes passed. Wi-Fi was already
disconnected after a DHCP failure hours before this task; internet regression
did not pass. See docs/ethersensors-delivery-2026-10-21.rst and
evidence/ethersensors-delivery.json for the exact state and remaining gates.

EtherUpdate commissioning build on 2026-10-21
--------------------------------------------

EtherUpdate 0.1.0 provides a system-bus update coordinator, authenticated
installation approvals, independent Ed25519 publisher trust, bounded downloads,
persistent history, tested versioned application recovery and an integrated
EtherShell Software Updates page. The existing AutoUpdate Center repository has
an optional signed-manifest upload extension; no second update platform was built.

The agent and token-entry Settings page are installed on the phone. No release
was published. Trust keys and project mappings are intentionally empty.
Rotated credentials, official signed releases,
self-update recovery, scheduled/batch installs and production acceptance remain
delivery gates. Existing boot/Android partitions were not modified. See
``docs/etherupdate.rst`` and ``evidence/etherupdate-delivery.json``.

EtherLocation partial delivery on 2026-10-20
-------------------------------------------

EtherLocation 0.1.0 is installed with native Qualcomm LOC/QRTR positioning,
backend-enforced permissions, approximate location, licensed offline raster
maps, optional local history, geofences, opt-in EtherCamera GPS EXIF, and existing
EtherShell Settings/Quick Settings integration. Location, history, online
positioning and background tracking are off by default. No Fleet integration
or automatic location upload is included.

Real GNSS sessions start and stop, and the native decoder has reported GPS and
GLONASS satellites. No valid position fix has been verified, so internal GNSS
is not marked operational. Offline maps work independently with the supplied
public-domain Natural Earth overview. Browser bridging, routing/navigation,
outdoor acquisition and lifecycle/power acceptance remain open.

See ``docs/etherlocation-delivery-2026-10-20.rst``,
``docs/etherlocation-feasibility-2026-10-20.rst`` and
``evidence/etherlocation-delivery.json`` for exact evidence and limitations.

EtherCamera independent baseline on 2026-10-20
---------------------------------------------

EtherCamera 0.4 and the native Spectra 0.2 driver now capture the physical
rear-main Sony IMX586 on the GM1920 handset. The implemented path is sensor
CCI -> three-trio C-PHY -> IFE RDI RAW10 -> mapped DMA buffers -> software RGB
processing -> managed JPEG preview/photos and H.264/AAC recording.

Real handset tests saved a 4000 x 3000 RAW frame, displayed preview through
the production QML, saved JPEG photos, and finalized H.264 video. An uncovered
scene was inspected independently. Software metering/gamma now brightens low
light frames; area averaging reduces noise from preview downsampling.

Open **EtherCamera — Aparat**, choose the rear IMX586, press **Uruchom kamerę**
and accept access. **Zrób zdjęcie** saves a photo; **Film** enables recording
with a separate microphone choice. Saved media is in the private EtherCamera
library. The backend still supports USB UVC as a fallback.

This is a basic rear-camera implementation: fixed sensor exposure and lens
position, no calibrated ISP colour processing, autofocus, OIS, HDR, flash or
front pop-up operation. Other internal cameras and suspend/resume remain
unverified. Browser websites have no implicit native-Spectra bridge. It is
not full stock-camera parity or complete acceptance of all Task 07 features.

See ``docs/ethercamera-spectra-driver-2026-10-20.rst`` and the current
``evidence/ethercamera-delivery.json``. Earlier 0.1-0.3 audit/delivery reports
are historical and their internal-camera blockers are superseded by this
rear capture evidence. Kernel, Android partitions and calibration data were
not changed. Vendor mode tables are derived privately on the phone and are
not redistributed. EtherLock consent/owner checks, EtherPower recording
limits, EtherAudio leases and the media/scanning APIs remain in use.

EtherLock staged engineering implementation on 2026-10-20
--------------------------------------------------------

EtherLock adds a Debian ARM64 package with XSecureLock enforcement, a Qt6 touch
credential interface, PAM authentication/account checks and backend attempt
limits, a session D-Bus privacy API, Settings integration, power blanking guard
and administrator recovery/evidence gates. Automatic locking remains disabled;
the updated shell is staged beside the active release. Separate PINs, physical
lock/wake/hotplug acceptance, supported suspend, locked calls and biometrics
remain incomplete. The audit also identifies existing autologin, passwordless
sudo and unencrypted ext4. Task 06 is not release complete. See
``docs/etherlock.rst`` and ``docs/etherlock-delivery-2026-10-20.rst``.


EtherNotifications engineering release on 2026-10-20
----------------------------------------------------

EtherNotifications moves the standard Linux notification name out of EtherShell
into an independent user service, with bounded private SQLite history, mobile
Notification Center, queued banners, actions, grouping, DND, per-app policies,
Settings/Quick Settings and privacy-aware cards. EtherSMS adds conversation/event
deduplication and mark-as-read; EtherPhone keeps its dedicated incoming-call UI
and adds a missed-call history action. Notification cues use EtherAudio's existing
focus/category backend. An attended reboot verified automatic startup, preserved
history/settings and restored Wi-Fi/SSH. No audio server, network, modem or Android partition is
replaced. Hardware vibration, authenticated EtherLock, inline reply and deep
suspend remain incomplete or unverified. See ``docs/ethernotifications.rst`` and
``docs/ethernotifications-delivery-2026-10-20.rst`` for acceptance and recovery.

EtherPhone engineering release on 2026-10-20
-------------------------------------------

EtherPhone adds a native Qt6/QML dialer, a background ModemManager adapter,
shared EtherContacts service/store used by EtherSMS, persistent event-based
call history, private vCard import/export/backup and redacted diagnostics.
Calls settings and an incoming/active-call overlay integrate with EtherShell.
The current phone has a ready SIM and working read-only QMI Voice enumeration,
but ModemManager exports no modem/network port, NAS is not registered, IMSA
queries fail and native Qualcomm call audio is unvalidated. Real calling,
VoLTE, screen-off wake and emergency support are NOT verified. Keep a known-
working emergency phone. See ``docs/etherphone-feasibility-2026-10-20.rst``,
``docs/etherphone.rst`` and ``docs/etherphone-delivery-2026-10-20.rst``.

EtherAudio on 2026-10-20
-----------------------

The existing working PipeWire/WirePlumber and Qualcomm UCM routes are retained.
EtherAudio adds session D-Bus policy, verified endpoint/stream controls, focus,
logical volumes, bounded consent-based capture for EtherSMS/EtherSpeech,
microphone activity, Sound & Notifications sections and Quick Settings.
EtherBluetooth uses the same routing/call/capture guards. ARM64 packages,
diagnostics and automated tests are included. Native modem voice/earpiece,
physical USB/Bluetooth acceptance and actual suspend/resume remain explicitly
unverified. See ``docs/etheraudio.rst`` and
``docs/etheraudio-delivery-2026-10-20.rst`` for the requirement assessment,
measurements, evidence and recovery instructions.

EtherPower on 2026-10-19
-----------------------

EtherPower 0.1.0 is installed and active, with native Battery & Power Settings,
Quick Settings, history, thermal/charging diagnostics, verified CPU/GPU profiles
and coordinated power-button behaviour. The active shell is now
``/opt/ethershell2/2.1.0-power-552338610e39``, with Balanced effective.
All 19 backend tests and 1132 UI checks pass; live brightness, timeout, blank/wake,
long-press menu and Wi-Fi-bound HTTPS checks pass. Suspend is explicitly blocked
because this kernel has no verified recovery/wake path or RTC wakealarm.
An approved full reboot on 2026-10-20 verified automatic service/shell startup,
unchanged saved settings, Balanced and Wi-Fi HTTPS. Physical unplug/AR/endurance
and full power-off/cold-start tests remain unverified. See ``docs/etherpower.rst`` and
``docs/etherpower-delivery-2026-10-19.rst`` for measurements, packages and evidence.

EtherHardware on 2026-10-19
--------------------------

EtherHardware 0.1.0 is installed and active on the phone. Existing Settings →
System → Hardware & Drivers now exposes real discovery, driver/firmware evidence,
28 shared capabilities, diagnostics, bounded history and redacted JSON/text
reports. The read-only service runs as an unprivileged account and subscribes to
hardware/service events. Its separate PolicyKit helper accepts only reviewed
Debian userspace diagnostic tools. The distributor recognizes EtherHardware;
no remote release is published without release credentials.

All 17 backend/security tests and 904 Settings UI checks pass on ARM64, across
360x900, 1080x2340, 1000x600 and 1920x1080 in both themes. The active shell is
``/opt/ethershell2/2.1.0-hardware-39dc755eec00``. Live Wi-Fi-bound HTTPS returns
200; Bluetooth, SSH, USB recovery/storage and existing services remain active.
The existing failed cellular data session and AP quarantine remain visible.
Physical audio/camera/sensor, external-display transmission and suspend tests
are not inferred from interface detection. See ``docs/etherhardware.rst`` and
``docs/etherhardware-delivery-2026-10-19.rst`` for API, evidence and limitations.

EtherShare internet sharing on 2026-10-19
----------------------------------------

The approved reboot restored Wi-Fi, USB SSH and storage on a verified new boot.
Fresh Windows Wi-Fi-to-USB HTTPS, DNS and DHCP tests pass; the temporary host
gateway was removed afterwards. The latest shell passes all three UI acceptance
sizes and is active. LTE packet initialization succeeds, but data-session requests
currently fail with modem reason esm-proc-timeout. Hotspot remains quarantined
after the earlier WLAN recovery failure. Sharing is off; full acceptance remains
blocked by LTE and AP stability. Earlier LTE traffic results are historical.

Earlier sharing implementation:

EtherShare 0.1.0 adds a native management app, Internet Sharing in existing
Settings and sharing controls in EtherControl. Real Windows HTTPS and DNS pass
through both LTE-to-USB and Wi-Fi-to-USB. USB recovery and mass storage are
preserved. A protected Wi-Fi AP activates alongside the existing station;
external wireless-client traffic still needs acceptance. The controller uses
owned legacy firewall rules, guarded source routing, scoped DHCP/DNS and explicit
VPN policy. Data-loss and controller-crash recovery pass. See
``docs/ethershare-2026-10-19.rst`` for capabilities, evidence and remaining gates.

Cellular IPv4 connectivity on 2026-10-19
--------------------------------------

Real giffgaff LTE ping, DNS and TCP now pass with Wi-Fi disabled through the
explicit ethermobile-data service and downstream IPA/QMAP adapter. Two final
reconnection cycles passed 10/10 ICMP replies. The existing Mobile Data GUI
does not yet control this adapter; automatic startup and reboot persistence
remain unverified. See ``docs/cellular-ping-2026-10-19.rst`` for commands,
evidence and the temporary current-boot IPA format migration.

Settings 2.0 redesign on 2026-10-19
---------------------------------

EtherShell 2.1.0 rebuilds the existing Settings across all eleven categories
with shared mobile components, direct setting search, light/dark themes and
keyboard-aware forms. It reuses the existing system and cellular backends.
Unsupported capabilities are labelled explicitly. See
``docs/settings-2-2026-10-19.rst`` for implementation, acceptance evidence,
deployment/rollback records and remaining device capability limits.

Mobile Network Settings integration on 2026-10-18
------------------------------------------------

EtherShell 2.0.2 embeds the shared EtherMobile 0.1.1 backend in Settings >
Network & Internet > Mobile Network. It adds verified APN editing/duplication,
credential preservation, rollback and conflict detection, saved data policies,
SIM/network-mode controls, local usage history and shared Quick Settings/dock
status. Real NM profile tests and private unprivileged phone UI renders cover
both themes and portrait/landscape/external sizes. An approved reboot preserved
the existing APN, launcher and firmware; EtherShell autostarted, and one manual
IPA startup restored modem/SIM detection. Cellular registration/data and
disruptive SIM/radio acceptance remain pending. See
``docs/mobile-network-settings-2026-10-18.rst`` for implementation and evidence.

EtherMobile update on 2026-10-18
------------------------------

EtherMobile 0.1.0 is an initial native Qt 6 cellular manager, packaged for ARM64
and installed on the phone. Its read-only EtherModem Doctor queries the actual
QRTR/QMI modem and distinguishes control, SIM, radio, packet path and internet
state. The approved one-shot IPA startup now loads firmware successfully and
creates the real rmnet_ipa0 interface. A device-specific udev association lets
ModemManager export the QRTR modem; the inserted giffgaff USIM is readable and
ready without a PIN1 request. Cellular internet is not working: LTE registration
is rejected with no-suitable-cells-in-location-area. The user reports activating
the SIM about 20 minutes earlier, so provisioning is a possible unverified cause.
Device evidence identifies the SDX50M/GM1920
variant, so the task's LTE-only hardware assumption must not be used as fact.
Matching IPA firmware has been copied from this phone's read-only vendor_b
into Linux with verified hashes. Startup was performed once after confirmation;
automatic startup at boot has not been enabled. See
``docs/ethermobile-2026-10-18.rst`` and ``ethermobile/README.rst`` for evidence,
implementation, acceptance results, limitations and remaining milestones.

EtherFiles update on 2026-10-17
-----------------------------

EtherFiles 0.1.1 adds verified SFTP/SMB/WebDAV fixture acceptance on both the
build host and physical ARM64 phone, including bad credentials, changed SSH
keys and untrusted TLS rejection. It is installed on the phone. See
``docs/etherfiles-network-2026-10-17.rst`` for evidence and acceptance limits.

EtherFiles 0.1.0 is built and installed as a native ARM64 Qt 6 file manager.
It manages real files with adaptive Pocket/desktop layouts, safe operations,
Trash/restore, search, previews, tabs/split panes and Linux service integration.
The filesystem suite passes on amd64 and the phone; the private X11 UI checks
also pass. This is an initial implementation with remaining release work,
including remote-server/AR/touch acceptance. Thunar remains unchanged.
See ``docs/etherfiles-2026-10-17.rst`` and ``etherfiles/README.rst``.

EtherBluetooth update on 2026-10-17
---------------------------------

The native Qt 6 EtherBluetooth app, Driver Doctor and signed external UART driver
are installed on the phone. ``hci0`` is operational: power off/on and real nearby
discovery work as the normal desktop user. Two driver-service restart cycles
passed; automatic startup is enabled. UART runs at 3 Mb/s using verified
controller-resident firmware. Pairing/audio/HID and complete cold-boot validation
remain outstanding. See ``docs/bluetooth-driver-2026-10-17.rst`` for evidence,
installation and limitations, and ``docs/etherbluetooth-2026-10-17.rst`` for the
initial audit/application implementation. The working kernel and Android/boot
partitions are unchanged.

Native touch update on 2026-10-17
--------------------------------

Firefox now receives native XI2 touchscreen events, enabling finger panning
instead of mouse dragging. The configuration is deployed on the phone and
persisted for XFCE and EtherShell. Synthetic touch tests on the phone verified
Firefox page scrolling and GTK kinetic scrolling. Legacy applications can
still require individual adaptation; see ``docs/native-touch-2026-10-17.rst``.

EtherShell status on 2026-10-16
------------------------------

USB Mass Storage is installed: ETHERPOCKET is an 8 GiB FAT32 exchange
disk, verified with bidirectional file transfers on Windows. Visible home
files are mirrored onto the disk before export; computer edits return
to the home directory after eject, with backups and conflict copies. On Mobian,
open ~/USB after ejecting the disk on the computer. See
``docs/usb-storage-2026-10-16.rst`` for ownership rules and host test limits.

The native Qt 6/QML EtherShell 0.2.0 application is now built and installed
on the physical ARM64 phone, with an X11 keyboard, XDG app launcher,
window controls and system settings integration. XFCE remains the default
and the recovery desktop. A separate EtherShell/Openbox login entry is
installed. See ``docs/ethershell-2026-10-16.rst`` for build instructions,
device test evidence, recovery commands and the substantial remaining
work, including missing verified ARM64 app packages and untested glasses.
The App Centre now reads real public AutoUpdate catalogue/release metadata;
MCP access also works with the explicit EtherShell User-Agent and Bearer
authentication, with the management token kept off the phone.

The required runtime is native Mobian/Debian ARM64, Qualcomm DRM/KMS,
Mesa Freedreno, Xorg, XFCE4 (or an explicitly selected Openbox session),
and EtherAIR. External display scanout is provided by kernel USB-C
DisplayPort Alt Mode and configured through XRandR. Wayland is not an
authorized fallback. Android, Termux, proot and containers are not the
target runtime.

Status on 2026-10-15
--------------------

The Etherneco boot menu is now installed in both boot slots. It shows
etherPocket and Android 10; Volume Up/Down selects and a fresh Power
press/release confirms. There is no automatic countdown. Each system
keeps its own kernel. The original boot images remain backed up under
recovery/stock-backup. The menu uses native DRM/KMS before starting either
system. See docs/bootmenu-2026-10-15.rst for verification and recovery.

Native custom ARM64 Linux, systemd, Xorg and XFCE have booted on the
physical GM1920. The user confirmed a visible desktop, working touch,
menu opening and window dragging. Software rendering is llvmpipe;
hardware acceleration remains unverified. Three local Xorg modesetting
patches and a libinput width-axis quirk were required. Native USB SSH
works using the Qualcomm configfs RNDIS implementation.

Connecting Nreal Air caused a documented kernel Oops in DSI backlight
handling on a DP connector. Patch 0006 is compiled but awaiting hardware
validation. Functional glasses output has not been established.

The user requested dual boot and explicitly authorized an Android data
reset. The userdata split is applied: exactly 32 GiB Android userdata and
208,467,374,080 bytes for Mobian, in addition to fixed Android system
partitions. Mobian is installed on sda21 and its filesystem passed e2fsck.
Mobian boot_a, matching DTBO A and custom-kernel verification metadata A
are installed. Native disk-root boot and physical touch/display updates
are verified; Android vbmeta_b is unchanged. Android
also completed its reset and boots with the 32 GiB data volume. Use
``Android.cmd`` / ``Mobian.cmd`` remain available with USB connected to this PC; they handle
the GM1920 boot type GUIDs and subsequent Fastboot slot activation.
See ``docs/dualboot-2026-10-15.rst`` for round-trip verification and limits.

Bring-up history is in ``docs/device-execution-2026-10-14.rst``. The
following paragraphs describe the original discovery, not current blockers.

This workspace was empty when the task update arrived. There were no
previous build scripts or EtherAIR sources to migrate. The supplied task
is preserved in ``docs/task-update.txt``. New files are preparation tools,
not a bootable image or evidence of successful device deployment.

Read-only ADB discovery found model GM1920, device OnePlus7ProNR,
Android 10, vendor kernel 4.14.117-perf+, current slot _b,
ro.boot.flash.locked=0 and verifiedbootstate=orange. These properties
suggest an unlocked Android bootloader; fastboot state has not been
independently verified. OnePlus identifies GM1920 as OnePlus 7 Pro 5G:
https://service.oneplus.com/content/dam/support/ce-doc/OnePlus_7_Pro_5G_CE_DOC.pdf

The phone exposes /dev/kgsl-3d0, /dev/dri/card0 and renderD128, with the
display device bound to the vendor msm_drm driver. Connector directory
names include DSI-1, DP-1 and Virtual-1. Android shell permissions prevented
reading connector status/modes and several kernel interfaces. These names
do not establish a usable native Linux DP path, GPU render node, or
glasses compatibility. See ``evidence/device-discovery-2026-10-14.txt``.

The immediate blocker is a verified native Linux kernel/device tree and
boot/rootfs combination for this exact 5G variant. A guacamole or hotdog
image must not be assumed compatible. No such image, kernel source, board
port or recovery backup was present here. No flashing or reboot was done.

Further investigation found OnePlus's SDX50M Android 10 source branch
with project 18827 overlays; the connected phone also reports project
18827. The running kernel config was read without root. It confirms
CONFIG_VT and CONFIG_DEVTMPFS are disabled, blocking the intended normal
local Xorg/LightDM and native device provisioning path. See
``evidence/running-kernel-audit.json`` and ``docs/kernel-investigation.rst``.
An experimental config fragment addresses initial native prerequisites;
it has not been compiled or booted and does not solve GPU ABI compatibility.

Preparation tools
-----------------

* ``scripts/install-x11.sh``: preview or install the X11 stack on an
  already booted native Mobian/Debian ARM64 system. Installation requires
  --apply and fails if the kernel exposes no DRM card. It records package
  versions and APT sources, chooses LightDM/XFCE and supplies X11 tools.
* ``scripts/etherair-x11.py``: native X11 display controller, polling
  hotplug/resume watcher, touch rotation/calibration, mobile setup,
  battery/thermal report, EWMH workspace controls and diagnostics.
* ``config/20-etherpocket-modesetting.conf.example``: optional modesetting
  configuration, only after the KMS and Mesa compatibility gate passes.
  Default installation lets Xorg probe the actual driver.
* ``docs/bringup.rst``: kernel, rootfs, USB, recovery and acceptance gates.
* ``scripts/audit-kernel.py`` and ``kernel/x11-native.fragment``: initial
  kernel prerequisite audit and proposed configuration input.
* ``tests/test_x11.py``: host tests of XRandR parsing, display selection,
  mode selection, touch transforms and renderer classification. These
  tests do not prove hardware support.

On native Linux, preview with ``bash scripts/install-x11.sh``. Once the
bring-up gates are met, install with ``sudo bash scripts/install-x11.sh
--apply``. In the physical XFCE session run::

    etherair-x11 diagnose --output evidence-x11.json
    etherair-x11 display --layout extend --dry-run
    etherair-x11 display --layout mirror --external <discovered-output>
    etherair-x11 mobile --dpi 180
    etherair-x11 rotate --output <phone-output> --touch <device-id> --rotation left

Package installation and display configuration have not run on the
phone. Native boot, physical Xorg, touchscreen, GPU acceleration, Nreal
Air desktop output and EtherAIR rendering remain unverified.
