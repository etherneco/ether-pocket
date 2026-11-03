EtherSensors 0.1.0 — independent framework
========================================

This is the Task 10 fallback delivery, not completed physical sensor support.
Read docs/ethersensors-audit-2026-10-21.rst first. No real accelerometer,
gyroscope, light, magnetometer or proximity measurements have been verified.
No simulated backend is installed. Test files use labelled temporary sysfs
fixtures; they are not device evidence.

The sensor session owner is com.etherneco.EtherSensors1 at
/com/etherneco/EtherSensors1 with the identically named D-Bus interface.
EtherHardware retains the system inventory and capability registry; its sensor
section refers consumers to this owner. EtherPower, telephony, display and
update infrastructure remain the existing owners. No EtherFleet integration.

Provider architecture
---------------------

providers.Provider defines discover/sample/close. Discovery gathers compatible
Linux IIO channels and describes unknown SSC and vendor input candidates without
activating them. The read-only IIO provider handles raw+offset+scale and processed
scalar illuminance/pressure channels. Pressure is converted kPa to Pa. Magnetic
IIO scale would require gauss-to-microtesla conversion; vectors remain blocked
until board axes are validated. Unknown proximity units are blocked. No sysfs
enable, sampling frequency, firmware, factory calibration or buffer writes occur.
Only a scalar compatible channel can currently be sampled. No measured sample
automatically upgrades a capability to Supported; a physical response audit
and driver-specific mapping remain required.

Metadata reports manufacturer, range, resolution, rate, power and calibration
as unknown when the interface cannot establish them. Advertised frequencies
are distinct from verified frequencies. Polling frequency is not device ODR.
Samples have CLOCK_MONOTONIC nanoseconds at host read completion and read duration;
these are not DSP acquisition timestamps or synchronized camera timestamps.

API version 1
-------------

All structured documents use JSON strings. Methods:

* GetState() -> s; ListSensors() -> s; GetCapabilities() -> s.
* GetSensorStatus(s sensorId) -> s.
* RequestPermission(s optionsJSON) -> s. Options: rate (0.2–10), background.
* GetManagement() -> s; ResolvePermission(s uniqueOwner, b allow) -> s;
  RevokePermission(s uniqueOwner). Only installed EtherShell while unlocked.
* StartSubscription(s sensorId, d pollHz, b background) -> s subscriptionToken.
* StopSubscription(s token); SetRequestedRate(s token, d pollHz).
* ReadLatest(s token) -> s fresh sample; no data broadcast or sample history.
* GetCalibrationStatus(s sensorId) -> s; RequestCalibration(s sensorId) rejects
  until supported. No factory/user calibration conflation or unsafe writes.
* GetOrientation() -> s; GetMotionState() -> s. Unavailable values are null;
  phone provenance never implies glasses head tracking, heading or GNSS.
* Configure(s JSON) -> s. Rotation lock is the only current safe configuration;
  unavailable autoRotate/motionControl requests are rejected.
* TestSensor(s sensorId) -> s token: foreground installed Settings only,
  30 seconds at 1 Hz. ExportDiagnostics() -> s redacted JSON (Settings only).

Changed(s metadataJSON) is event-driven and contains no raw or processed samples.
High-frequency streams, shared memory and sensor history are not implemented;
requests over 10 Hz fail. Maximum 32 subscriptions, eight per caller. Permissions
and subscriptions expire after five minutes, pending requests after one minute.
Cached values older than max(2 seconds, 2 polling intervals) are not returned.
The shared sampler reads only at the highest requested poll rate, capped at
1 Hz under EtherPower Battery Saver/unknown policy. No subscriptions means no
sampling timer or open input handles. Clients must stop when finished.

Lock, EtherLock disappearance/replacement and suspend drop all streams/grants
and cached readings. Resume requires explicit authorization and resubscription;
automatic restoration is intentionally deferred pending power acceptance.
Client D-Bus disconnection releases all resources. Foreground-only access is
checked against the current X11 application. Permission management resolves
kernel-provided caller PID and root-owned executable/script identity, never a
caller-supplied app name. Root-owned script/parent checks follow the existing
EtherLocation identity model. Unknown interpreter invocations are distinct.

Security boundary: this managed API does not sandbox same-UID processes or X11.
Direct readable kernel nodes, root, ptrace or QRTR can bypass it. The package
does not grant any device-node permissions or broaden the input group. Before
enabling a new provider, restrict its exact nodes through reviewed udev/group
policy; never deny the whole input subsystem or disturb the touchscreen.
Stored sample history and background access are off by default. Diagnostic
exports omit paths, client identities, raw samples and detailed error strings.

Settings and integration gates
------------------------------

The existing EtherShell System page opens Sensors & Motion. Quick Settings
links to the same backend status and displays rotation locked/motion unavailable.
Unavailable rotation controls are disabled. Settings shows provider state,
calibration, privacy requests/grants, activity and redacted diagnostics.
Compatible scalar test controls appear only for actual discovered channels.

Fusion/gestures, axis mapping, bias calibration, compass/declination,
auto rotation, automatic brightness, call proximity, EtherAIR pointer motion,
EtherLocation movement and EtherCamera metadata are deferred. No display or
call side effect is issued with unverified data. Existing mouse/touch input
is untouched. No claim of image stabilization or inertial navigation is made.

Build and acceptance
--------------------

Run python3 -m unittest discover -s ethersensors/tests -v, then
scripts/build-ethersensors.sh in the existing Debian build environment.
Package: ether-sensors_0.1.0_arm64.deb. The bus_acceptance.py test runs under
dbus-run-session with the real service on native ARM64; it exercises safe
metadata and unauthorized-call rejection with no hardware simulation.

The distributor descriptor identifies hardware-verification-pending. Use
existing EtherUpdate/AutoUpdate Center signed release commissioning, publisher
keys and project mapping; do not bypass trust or create another updater. A
local provisioning package is not an AutoUpdate Center publication.

Remaining acceptance: compatible SSC userspace protocol and physical sensor
identity; changed measurements under movement/light/cover; units, axes,
timestamp synchronization, rates, calibration and power; fusion and consumer
integrations; real calls; suspend/resume; boot/Android/external display
regression; signed publication. Do not mark Task 10 or hardware support complete
until those gates have real evidence.
