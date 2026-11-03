EtherLocation feasibility — 2026-10-20
======================================

Read-only audit ran on the actual GM1920 handset via the existing pinned USB
SSH connection. Debian 13.7 ARM64, Android-derived 4.14.117-perf #6. Evidence:
``evidence/etherlocation-hardware-audit.json``. No Android partition, bootloader,
firmware, calibration, radio configuration or existing location daemon was
modified. Kernel configuration and Device Tree were inspected, not changed.

* GNSS transport: Supported. QRTR node 0 advertises service 16 v2 (LOC), port 93
  in this audit. A dynamically discovered service port must be used at runtime.
* Kernel path: Supported for QMI/QRTR transport; CONFIG_QRTR=y and QRTR SMD/MHI/
  FIFO are present. No /dev/gnss0 or serial GNSS endpoint is exposed. The absence
  of the Linux GNSS character device does not imply LOC is unavailable.
* Firmware dependency: Partially supported. Modem-side LOC responds under Debian.
  Checked Android vendor GNSS HAL/launcher paths are absent. No firmware change
  was attempted; whether additional assistance/vendor configuration is needed
  to acquire a fix is unresolved.
* ModemManager GNSS: Not tested. ModemManager is active but currently enumerates
  no modem. Cellular data success is not assumed and is not a GNSS prerequisite
  for the direct LOC path. EtherMobile's QRTR transport is reused without
  changing its WDA, bearer or radio configuration.
* gpsd / GeoClue / oFono: inactive in the baseline. No competing service was
  installed or enabled. Existing compatible local gpsd receivers are supported
  as an explicitly selected fallback; no external receiver is attached/tested.
* Session start/stop: Supported. qmicli accepted session 201, and the native
  rootless helper accepted session 208. Native stop was acknowledged and its
  client/device resources were released. Native evidence:
  ``evidence/etherlocation-native-fix-test.json``.
* Satellite visibility: Partially supported. The final 60-second native retest
  decoded 51 real satellite reports with up to three reported satellites from
  GPS and GLONASS, including real signal readings. No used-in-fix count or other
  constellation is inferred. Evidence is in
  ``evidence/etherlocation-runtime-verification.json``. An earlier Python GI
  decoder crashed on satellite structs and was removed; the earlier 180-second
  native test had received no reports. Telemetry is intermittent, not fabricated.
  A subsequent five-minute attempt reported up to 14 satellites, including
  Galileo. A fresh five-minute test after the user confirmed clear sky view
  decoded 267 satellite reports and 300 position reports marked in-progress,
  but no successful position. Partial reports are deliberately not published
  as real fixes. The engine also reported timeout. See
  ``evidence/etherlocation-clear-sky-test.json`` and
  ``evidence/etherlocation-five-minute-test.json``.
* Real fix: Blocked in current verification. No valid coordinate/accuracy/time
  tuple with success status was received, including the user-confirmed clear-sky
  test. The verified blocker is that the engine supplies only partial reports
  and times out; its underlying cause remains unknown. This proves first-fix acceptance
  is incomplete, not that firmware permanently prevents positioning. Antenna,
  sky view, assistance and firmware configuration require further controlled
  investigation. No unsupported vendor writes were made to guess a remedy.
* Accuracy, cold-start time and warm-start time: Not tested; no verified fix.

Internal GNSS is NOT marked operational. This delivery provides independent
location policy, maps, history and geofencing infrastructure plus a real LOC
provider and compatible external-gpsd path. Outdoor acquisition and actual
battery-only measurements remain release gates, along with external receiver,
browser bridge and lifecycle acceptance documented in the main module guide.
