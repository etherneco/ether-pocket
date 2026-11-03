EtherCamera task 07 delivery — 20 October 2026
=============================================

Disposition
-----------

Independent backend baseline installed and verified. Internal sensor capture
is BLOCKED; task 07 is NOT fully complete. No real physical camera frame has
been obtained, and no external UVC camera is attached. Photography/preview UI
is deferred in accordance with the first-frame gate. The settings-only shell
integration is packaged, staged and tested beside the active shell.

Hardware findings
-----------------

The exact running device identity is GM1920. Read-only vendor_b build
properties identify OnePlus7ProNR_EEA/OnePlus7ProNR, Android 10. Debian runs
the downstream Spectra kernel ABI, not a standard V4L2 sensor capture graph.
video0/video1 are request/synchronization endpoints; video2 is a rotator;
video32/video33 are codec endpoints; video34 rejects QUERYCAP. Vendor media
entities have zero pads and links. Sensor slots do not establish physical
sensor identity, probe success or an operational stream.

Read-only debugfs inspection finds the Camera HAL/provider and ICP firmware
in the existing Android vendor image. They are not integrated into Debian.
The provider needs Android linker64, bionic, Binder/HIDL, graphics mapper,
CamX, Qualcomm DSP/QMI and OnePlus modules. Binder device nodes are present,
but /system/bin/linker64 and the provider path are absent in running Debian.
No vendor binary was executed or redistributed. No Android partition was
mounted or modified; no firmware was flashed or explicitly loaded and no motor attribute
or calibration was changed. The motor's oneplus_motor/drv8834 bindings are
documented; safety/obstruction/retraction sequencing is not verified.

Delivered software
------------------

* ethercamera_0.1.0_arm64.deb: independent core, V4L2 device enumeration,
  bounded GStreamer external-UVC provider, JPEG/PNG photo capture API,
  experimental silent MP4/H.264 branch, enumerated standard UVC controls.
* Session D-Bus API with owner tokens, explicit consent, single-owner busy
  rejection, fail-closed EtherLock checks, sealed JPEG preview FDs and
  read-only media FDs. No uncompressed video in D-Bus messages.
* Private UUID media storage, metadata allowlist/location exclusion, search,
  read/delete/export access and reusable inventory attachment references.
* ZXing QR/common barcode decoding, typed results, duplicate suppression and
  no automatic URL/Wi-Fi/contact action. OpenCV document-edge detection,
  perspective correction, grayscale/contrast, rotation and multi-page PDF.
* Asynchronous scan/document jobs, bounded frame/job memory, no idle polling,
  owner-loss/lock/suspend/error cleanup, logind sleep inhibition, video time,
  thermal, battery and storage guards, existing notification transport.
* Existing Settings -> Applications -> Camera integration, managed camera
  indicator and Quick Settings shortcut in the staged EtherShell package.
* EtherHardware camera capability identifiers; unknown hardware/operational
  values remain unknown. Updated registry package installed and tested.
* Reproducible build, deployment, audit, verification and stage scripts,
  automated tests, redacted diagnostic API and detailed blocker/API guides.

Validation
----------

All 15 EtherCamera tests pass on both Debian amd64 build host and ARM64 phone,
including real ZXing decoding and OpenCV processing of explicitly OFFLINE
fixtures, real GStreamer absent-node failure, sealed FD readability and
immutability, owner exit, lock failure, lease expiry and mux-failure cleanup.
All 17 EtherHardware tests pass. No fixture is classified as a sensor capture.

The final ARM64 EtherShell package passes all existing Settings assertions
in light/dark themes at 360x900, 1080x2340, 1000x600 and 1920x1080 on private
Xvfb displays. Camera pages were visually inspected. This does not verify
physical touchscreen use, an external display or camera orientation.

Live D-Bus checks reject Qualcomm/codec nodes, invalid sessions and unowned
jobs. API introspection confirms file-descriptor transport. An idle 10-second
sample shows no CPU-tick increase, unchanged approximately 27MiB RSS and no
open camera/media/subdevice descriptors. This is not a battery measurement.

Deployment before/after snapshots preserve boot ID, Wi-Fi, SSH, Bluetooth,
power, modem, sharing and USB service states, audio server PIDs and default
audio routes. Existing ethermobile-data remains inactive. The running shell
and locker policy are preserved. EtherLock is not running; EtherCamera never
auto-starts it and capture stays denied until it confirms an unlocked session.
The prior task 06 live-lock acceptance gate is not bypassed by promoting its
staged client as part of this camera work.

Evidence
--------

* ethercamera-audit-2026-10-20.json: physical node/driver/config/topology audit.
* ethercamera-vendor-audit.json: read-only vendor metadata and ELF dependencies.
* ethercamera-tests-amd64.txt, ethercamera-build-tests.txt: native build tests.
* ethercamera-install.json: ARM64 tests and unchanged deployment baseline.
* ethercamera-device-verification.json: live API, idle descriptors/CPU, services.
* ethercamera-hardware-update.json, ethercamera-hardware-regression.txt.
* ethercamera-shell-stage.json, ethercamera-settings-device/acceptance.json
  and the four view directories: exact staged package and UI acceptance.
* ethercamera-delivery.json: final package/evidence hashes and disposition.

Outstanding acceptance
----------------------

An operational internal vendor bridge or an attached compatible UVC camera is
needed for first-frame, preview, photography, video, autofocus and live scan
acceptance. The internal bridge is not established by merely locating blobs.
No production photo/video/scan was captured. No sensor performance, encoder
acceleration, physical orientation, disconnect or real suspend/resume is
certified. Full camera UI, media-browser UI/thumbnails, persisted preferences,
video microphone/audio synchronization, browser portal and live inventory
application integration remain outside this blocked baseline. These are
explicitly unfinished, not represented by disabled mock capture controls.
