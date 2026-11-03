EtherCamera physical hardware feasibility, 20 October 2026
========================================================

Result: internal camera capture BLOCKED. No physical camera frame obtained.
No external UVC camera was attached. External capture is implemented but has
not passed a physical camera acceptance test. Do not describe this release as
a working smartphone camera or a completed task 07/11.

Evidence and identity
---------------------

``evidence/ethercamera-audit-2026-10-20.json`` is collected over the existing
pinned SSH channel by ``scripts/audit-ethercamera-device.py``. Device identity
is GM1920-548cb338-mobian-sda21. Kernel is 4.14.117-perf/aarch64. Device Tree
model is SDX50M MTP 18827 15, compatible qcom,sm8150-mtp. This does not identify
an exact sensor BOM or prove that four physical modules are connected. The
marketing model and typical OnePlus camera arrangement cannot substitute for
sensor identification. A subsequent debugfs-only vendor_b audit identifies
the shipped Android fingerprint as OnePlus/OnePlus7ProNR_EEA/OnePlus7ProNR,
Android 10/API 29. This corroborates the GM1920 5G variant, but not a physically
probed sensor BOM. No sensor EEPROM/calibration was read or written, and no
Android partition was modified.

Real node classification
------------------------

* /dev/video0: cam-req-mgr, bound cam_req_mgr; VIDIOC_QUERYCAP returns ENOTTY.
* /dev/video1: cam_sync, bound cam_sync; VIDIOC_QUERYCAP returns ENOTTY.
* /dev/video2: sde_rotator, bidirectional/memory-to-memory processing.
* /dev/video32: msm_vidc_vdec, decoder, deviceCaps 69218304.
* /dev/video33: msm_vidc_venc, encoder, deviceCaps 69218304.
* /dev/video34: msm_vidc_v4l2 binding; QUERYCAP returns EINVAL.
* /dev/v4l-subdev0..49: vendor CPAS, ISP, CCI, CSIPHY, actuator, sensor,
  flash, EEPROM, OIS, ICP, JPEG, face detection and LRME subdevices.

These are generic vendor slots, not 50 cameras. There are seven generic
cam-sensor-driver subdevices; their presence does not prove sensor probing,
sensor identity, orientation, number of populated modules or stream support.

``media-ctl`` reports media0 driver cam_req_mgr/model cam-req-mgr-devnode and
media1 driver cam_sync/model cam_sync_device. Every entity has zero pads and
zero links. There is no standard pad/link graph that media-ctl can configure
into a capture pipeline. v4l-utils was installed with three userspace library
dependencies, no kernel or firmware replacement. Audit was repeated afterward.

Kernel configuration: CONFIG_SPECTRA_CAMERA=y, CONFIG_MEDIA_CONTROLLER=y,
CONFIG_VIDEO_V4L2_SUBDEV_API=y, CONFIG_USB_VIDEO_CLASS=y;
CONFIG_VIDEO_QCOM_CAMSS, CONFIG_MSM_CAMERA and CONFIG_MSMB_CAMERA are disabled.
Drivers are built in; absence from lsmod does not mean they are unavailable.
The bounded kernel log read yielded no camera initialization evidence. This
does not establish that a sensor has or has not ever initialized.

Architecture and compatibility choices, in required order
--------------------------------------------------------

1. Native V4L2/media controller: unavailable for internal sensors on this boot.
   Request/synchronization/codec nodes are rejected as image sources.
2. Open source stack: no installed libcamera capture provider was found; an
   upstream CAMSS pipeline cannot be assumed compatible with this downstream
   Spectra request-manager ABI. No kernel switch is attempted.
3. Device-specific Spectra integration: needs correct sensor probe and power
   packets, CCI programming, ISP resource requests, DMA/ION buffers, request
   synchronization, tuning and calibration interpretation. The exposed ABI
   alone is insufficient to construct a safe working pipeline.
   Existing kernel source confirms CAM_SENSOR_PROBE_CMD consumes a userspace
   memory handle and supplied power-up/down settings before matching sensor
   ID (drivers/media/platform/msm/camera/cam_sensor_module/cam_sensor/
   cam_sensor_core.c, lines 1031 onward). cam_req_mgr_dev.c handles session
   creation and buffer mapping. The ICP A5 path explicitly requests
   CAMERA_ICP.elf; none of the three checked /lib/firmware, /lib/firmware/qcom
   or /vendor/firmware paths contains that filename. This is a dependency
   finding, not proof that every possible camera path needs ICP firmware.
4. Isolated vendor bridge: checked /vendor/lib64/hw/camera.qcom.so and
   /vendor/bin/hw/android.hardware.camera.provider@2.4-service are absent.
   /vendor is not mounted in the audited Debian mount table. This is evidence
   about the running filesystem, not a claim that Android partitions lack
   the blobs. A bridge would require a matching Android/bionic service
   environment, dependencies, tuning/calibration data and redistribution
   rights. No bridge is enabled or claimed viable without those tests.
   The later read-only vendor_b inspection finds camera.qcom.so (5,858,968
   bytes), android.hardware.camera.provider@2.4-service_64 (11,800 bytes),
   its init declaration and CAMERA_ICP.elf (3,602,680 bytes). These files are
   PRESENT in Android, but not integrated into Debian. The ELF provider
   requires /system/bin/linker64 plus Android camera/graphics mapper HIDL,
   binder, libcutils/libutils/liblog and bionic libraries. The HAL also needs
   CamX statistics/face-detection, Qualcomm DSP/QMI and OnePlus camera HIDL
   and native modules. This is not a glibc library that GStreamer can load.
   Sensor libraries include IMX586, IMX481, S5K3M5, IMX471, IMX371 and GC5035;
   shipped module/tuning filenames include multiple module suppliers. Those
   are supported variants in a vendor image, not physical detection results.
   Only ELF metadata, directory listings, selected build properties and the
   camera init declaration are exported to ethercamera-vendor-audit.json;
   no vendor binaries, tuning blobs, firmware or calibration are redistributed.
5. External UVC fallback: kernel driver enabled; provider restricts capture to
   QUERYCAP capture-only nodes driven by uvcvideo. No such camera is attached.
   A real UVC frame is still required before accepting preview/photo/video.

Per-camera acceptance matrix
----------------------------

=================== ================ ================ ============= ============ ======== ===== ===== =========
Expected module     Physical detected Driver available Sensor init   Stream       Preview  Still Video Autofocus
=================== ================ ================ ============= ============ ======== ===== ===== =========
Rear main           Unknown          Generic slots    Not verified  Not verified Not run  No    No    Unknown
Rear ultra-wide     Unknown          Generic slots    Not verified  Not verified Not run  No    No    Unknown
Rear telephoto      Unknown          Generic slots    Not verified  Not verified Not run  No    No    Unknown
Front pop-up        Unknown          Generic slots    Not verified  Not verified Not run  No    No    Unknown
External UVC        Not attached     Built-in config  Not tested    Not tested   Not run  No    No    Per device
=================== ================ ================ ============= ============ ======== ===== ===== =========

All internal modules share the missing usable userspace capture path. Front
camera additionally lacks verified safe motor sequencing/control.

Pop-up motor
------------

Device Tree has oneplus-motor and oneplus,step-motor nodes. Actual platform
bindings are oneplus_motor on vendor:motor_pl and drv8834 on vendor:step_motor.
The directory exposes enable, direction, force_move, factory_mode, hall_reg,
hall_calibration, stall, move_state and other controls. Directory names and
bindings do not prove a safe API, obstruction protection or retraction sequence.
No sysfs attributes were read for their operational values or written. The
service has no motor implementation; front-camera capture stays unsupported.

Remaining physical acceptance
-----------------------------

Attach a compatible UVC camera, confirm the actual node with ethercamera state,
then explicitly invoke a photo/scan/video command with consent. Independently
inspect image dimensions/orientation and video playback. Verify disconnect,
lock, owner crash, disk-full, battery, temperature and real suspend/resume.
Measure preview FPS, latency, CPU, memory and battery; no acceleration or
thermal performance is certified. Internal acceptance requires actual sensor
identification and first frame through a safe supported pipeline.

EtherLock currently reports suspend security acceptance pending; do not force
suspend or reboot just to manufacture a camera recovery test. Existing shell,
audio, power, network and USB owners must remain running. No Android mount,
flash, firmware write, register write or calibration modification is needed
for the independent software delivery.
