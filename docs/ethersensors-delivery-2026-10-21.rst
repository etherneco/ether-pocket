EtherSensors Task 10 — partial delivery, 2026-10-21
=================================================

Delivered and installed
-----------------------

ether-sensors 0.1.0 ARM64 is installed and its user service is active. The
provider/registry, compatible scalar IIO reader, application D-Bus control API,
bounded sampling, session permission approvals, client cleanup, lock/suspend
revocation and power policy are implemented. No subscriptions means no sensor
polling. Metadata exposes operational uncertainty and derived provenance.
EtherHardware 0.1.1 includes sensor owner references and the additional
capability identifiers, with derived sensors explicitly non-physical.

EtherShell is running the exact UI-tested versioned build at
/opt/ethershell2/2.1.0-sensors-07e9238c2655. Settings -> System -> Sensors & Motion
is open on the handset. Quick Settings links to the same backend status.
The preceding shell remains at
/opt/ethershell2/2.1.0-update-token-8344f5475ddf, and the previous launcher is
/home/mobian/.local/bin/ethershell2-start.before-2.1.0-sensors-07e9238c2655.
The activation script verifies exact package/binary hashes, rejects active
calls/camera work, and restores the predecessor if activation fails.

The API and security model are documented in ethersensors.rst. Factory
calibration, firmware, kernel, boot and protected Android partitions were not
modified. There is no simulated production provider or EtherFleet integration.

Hardware result and unfinished work
------------------------------------

The mandatory initial audit preceded implementation. The three IIO devices
are PM8150 family ADCs, not motion/light sensors. SSC is enabled and firmware
exists, but /dev/sensors has only a timer ioctl in the audited driver source.
A compatible sample transport, sensor identity registry and calibration path
have not been established. Vendor VL53L1/ultrasound input interfaces produced
zero bytes during bounded passive reads; no near/far behavior is claimed.

No physical sensor passed changing-measurement validation. Accelerometer,
gyroscope, magnetometer and ambient light remain Blocked, proximity is discovery
only / Partially supported, and barometer presence remains Not tested.
Derived outputs are Blocked, not physical hardware. Sampling frequencies,
coordinate mapping, precision and power use remain unverified.

Fusion was deliberately not developed before real inputs were validated.
Motion gestures, auto rotation, ambient brightness, call proximity blanking,
user calibration, EtherAIR controls, EtherLocation movement and EtherCamera
orientation integration are consequently deferred. Their API availability
is false/null. No call/display/input side effects are triggered.

Real suspend/resume, power consumption, boot round trips, touchscreen physical
interaction, GNSS fix, camera capture, cellular calls and external-display
motion acceptance were not performed in this task. The independent framework
fallback is delivered; the full Task 10 definition of done is not satisfied.

Validation and regression
---------------------------

* 25 sensor discovery, SI conversion, timestamp, permission, expiry, owner
  isolation, stale/removal, polling/rate and lifecycle tests pass under Linux
  and on the physical ARM64 handset. Temporary test sysfs values are labelled
  fixtures and are not hardware evidence. Windows is not a supported runtime
  for Linux sysfs fixture tests (colon names, symlinks and fcntl).
* Eight unauthorized operations are rejected through the real D-Bus service
  in an isolated unprivileged session on native ARM64. No test daemon owns the
  production bus and no synthetic readings were injected into production.
* All 20 EtherHardware regressions pass, including the new alias and
  non-physical derived-capability checks.
* Production Qt/QML compiles for ARM64. Light/dark Settings rendering, route
  and geometry checks pass at 360x900, 1080x2340, 1000x600 and 1920x1080.
  Narrow light and landscape dark screenshots were inspected. The real
  handset screenshot was inspected after activation.
* SSH, NetworkManager, ModemManager, EtherHardware, EtherPower, the modem
  service and Bluetooth remain active. Other than the intended Hardware
  registry service restart, installation preserved monitored service PIDs.
  EtherSensors has zero automatic restarts and zero active subscriptions.
  EtherLock, EtherCamera, EtherPhone and EtherLocation readiness was recorded.
  EtherNotifications rejected the CLI status query under its existing privacy
  policy; notification behavior was not retested. This is service health,
  not full functional parity.

Wi-Fi is disconnected and the HTTPS regression check failed. Read-only
NetworkManager history records DHCP ip-config-unavailable at 08:21 UTC
(09:21 Europe/London), before the initial sensor audit at 14:21 UTC
(15:21 Europe/London). There is no default route. No network, radio or resolver
configuration was changed by this task. The pre-existing connectivity failure
is recorded in ethersensors-network-check.json and ethersensors-wifi-history.json;
do not describe Wi-Fi/internet regression as passing.

Distribution
-------------

Local artifacts are build/ether-sensors_0.1.0_arm64.deb,
build/etherhardware_0.1.1_arm64.deb and
build/ethershell_2.1.0_ethersensors_arm64.deb. Exact SHA256 hashes and live
acceptance gates are in evidence/ethersensors-delivery.json.

Existing EtherUpdate is ready but has no configured credential, component
mapping or publisher trust keys. The descriptor marks the package
hardware-verification-pending. No release was published or signing/trust
mechanism bypassed. AutoUpdate Center commissioning and signed publication
remain external release gates; no second updater was created.

Evidence
---------

evidence/ethersensors-hardware-audit.json records the latest real audit;
ethersensors-device-tests.json contains native unit/bus results;
ethersensors-install.json records package installation and live discovery;
ethersensors-ui-package.json ties layout acceptance to its exact shell hash;
ethersensors-ui/ contains eight light/dark screenshots and logs;
ethersensors-stage.json and ethersensors-deployment.json record activation;
ethersensors-live/live-screen.png is the physical screen capture;
ethersensors-delivery.json is the final machine-readable report.
