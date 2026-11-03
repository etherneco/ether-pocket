EtherCamera: native rear IMX586 capture
=====================================

Current software: EtherCamera 0.4.0; ethercamera-spectra 0.2.0.
Target: verified GM1920, SDX50M MTP 18827 15, aarch64, 4.14.117-perf.
This report supersedes the earlier transport-only state in this document.

Real implemented path
---------------------

The native worker uses the running downstream Qualcomm kernel UAPI. It
probes rear slot 0 (ID 0x0586, CCI slave 0x34, ID register 0x0016), configures
its pinned initialization/mode/stream tables, acquires CSIPHY 1 and IFE RDI0,
and receives RAW10 through three IOMMU-mapped pixel buffers and sync fences.
The mode is 4000 x 3000, 5008-byte stride, three C-PHY trios. Initial HFR and
clock/bandwidth configuration is submitted once. Repeating unchanged HFR
blobs makes this downstream kernel emit a zero-register CDM command; the
worker avoids that kernel bug without patching the kernel.

Completed buffers are recycled with increasing request IDs. RGB output is
bounded to 640 x 480; downsampling averages Bayer cells over each output
pixel area. Black-level subtraction, bounded software metering and gamma
lift improve brightness. This does not claim sensor auto-exposure, calibrated
white balance, autofocus, noise reduction or stock ISP quality. No pattern
source exists in the installed driver. An unobstructed scene was captured
and inspected after the first covered-camera dark frames.

The worker is an ordinary video-group process launched only by the managed
service after consent. It exits on pipe failure, SIGTERM, a bounded fence
failure or a five-minute limit. Cleanup stops the sensor, flushes requests,
stops receivers, deactivates/unlinks CRM, releases devices/fences/buffers,
and closes descriptors. CRM itself is single-open. The managed service
continues same-owner leases, fail-closed EtherLock checks, suspend/owner-loss
cleanup, sleep inhibition and recording power/storage/duration limits.

Backend integration
-------------------

The enumerated logical camera is spectra:rear-imx586, not a fabricated video
node. It is available only with the exact board/kernel, root-owned worker
and pinned private plan. The service transports preview JPEGs as sealed FDs;
raw high-resolution frames never enter D-Bus messages. The existing photo
and private media APIs save JPEG/PNG and H.264 MP4. Video is limited to 640 x
480 at an output rate up to 15 fps and 60 seconds. Native source frames can
be slower; videorate may repeat physical frames. Hardware encoding is not
claimed. Optional AAC audio comes only from a separately consented EtherAudio
lease. PCM timestamps use sample counts to prevent overlapping timestamps
when pipe reads arrive in bursts.

Device profile and privacy
--------------------------

The module parser bounds-checks the handset-owned QTI parameter container.
Three exact SHA-256-pinned manufacturer variants agree on probe/power,
mode geometry and all initialization/mode/start/stop registers. The plan is
derived on the phone, root-owned and video-group readable. Vendor binaries,
calibration data, EEPROM contents and register tables are not shipped in the
package or exported as evidence. Vendor partition access uses debugfs without
-w, mounting or journal replay. No vendor HAL binary is loaded or executed.

No kernel, boot configuration, Android partition, camera firmware, calibration
or pop-up motor state is changed. Other camera slots receive capability
queries only during explicit engineering discovery. No front sensor is
powered. Module supplier/lens calibration remains unqualified. Existing
network, modem, shell and audio owners are preserved.

Evidence and limits
-------------------

* ethercamera-spectra-rear-probe.json: physical sensor ID comparison.
* ethercamera-spectra-raw-test.json: native stream/fence test.
* ethercamera-spectra-managed-capture.json: real managed JPEG/MP4 references.
* ethercamera-rear-uncovered.jpg: first inspected scene after uncovering.
* ethercamera-rear-brightened.jpg: subsequent software-brightened capture.
* ethercamera-physical-ui/result.json: production QML consent, preview,
  photo, video and release acceptance on the real session bus.
* ethercamera-spectra-av-playback.json: final audio/video decoder inspection.
* ethercamera-delivery.json: current package/source hashes and acceptance.

C++ lifecycle/probe ABI and RAW conversion/tone tests, bounded module-parser
tests, and the camera Python regression suite are separate from hardware
acceptance. Private-bus UI tests use explicitly labelled offline fixtures;
those are never counted as sensor evidence.

Rear photo/video transport is implemented. Optical focus, automatic sensor
exposure, colour calibration, orientation acceptance, other rear lenses,
front motor safety, suspend/resume, website capture and physical label/document
scanning acceptance remain outside verified scope. Task 07 is not declared
fully accepted while these conditions remain open.

Build and install
-----------------

Use scripts/build-ethercamera-spectra.sh and scripts/build-ethercamera.sh in
EtherPocketBuild. The matching source UAPI is /opt/etherpocket/kernel/include/uapi;
only media headers are isolated, leaving libc Linux headers intact. Install
with scripts/deploy-ethercamera-spectra.py (private on-phone plan derivation)
and scripts/deploy-ethercamera.py. Neither package starts a camera on install.

Implementation references: the exact local downstream kernel cam_sensor,
cam_req_mgr, cam_sync, cam_isp and cam_csiphy sources; native orchestration
examples in commaai/openpilot system/camerad/cameras/spectra.cc; CamX schema
field ordering in bjzhou/CamxChi. No automotive power/register profile or
proprietary schema file is redistributed.
