EtherSensors mandatory hardware audit — 2026-10-21
=================================================

The live GM1920 handset was inspected through the existing pinned USB SSH
connection before developing sensor providers. Evidence is in
evidence/ethersensors-hardware-audit.json. Kernel: 4.14.117-perf; identity:
GM1920-548cb338-mobian-sda21. EtherHardware already owns hardware inventory;
EtherPower owns display brightness and power policy. No existing Qt Sensors
manager or motion consumer was found in EtherShell. No competing inventory,
brightness, telephony, updater or input manager will be introduced.

The initial live audit ran at 14:21 UTC; the evidence file contains the latest
repeat audit after implementation. All three PMIC IIO devices are bound to
qcom-spmi-adc5.c, confirmed through their resolved sysfs parent driver links.

All three exposed IIO devices are Qualcomm PM8150 family VADC channels:
voltage, temperature and power, without accel/anglvel/magn/illuminance or
proximity channels. CONFIG_IIO=y, CONFIG_IIO_BUFFER is disabled. These nodes
are not evidence of smartphone motion sensors. iio_info and libinput tooling
are absent. Input topology was read without grabbing touchscreen/input nodes.

CONFIG_SENSORS_SSC=y; the enabled DT nodes are qcom,msm-ssc-sensors and the
PIL SSC loader. /dev/sensors and /sys/class/ssc/sensors exist. The local
Lineage kernel archive at revision 77a0c0f contains drivers/sensors/sensors_ssc.c:
its file_operations offers open/release and a slow-timer ioctl only, with no
read/poll measurement interface. Its boot/SSR attributes control SLPI loading
and restart; neither was written. Firmware slpi.mdt exists, but compatible
vendor HAL/sscrpcd paths checked are absent. QRTR advertises diagnostic sensor
services and unknown service 1053; this does not establish an SSC sample
protocol, enumeration, calibration or physical sensor identities. A compatible
userspace SSC transport/protocol and sensor registry remain required.

The STM VL53L1 and elliptic_ultrasound_proximity input interfaces are detected.
Their intended role, enable protocol, units, calibration and near/far behavior
remain unverified. Passive bounded reads are recorded in the evidence. No
input interface was enabled, grabbed or interpreted as ear proximity.

Capability report
-----------------

Accelerometer, gyroscope, magnetometer and ambient light: Blocked. Physical
part identity, driver behind SSC, device sampling endpoint, initialization,
SI units, supported frequencies, calibration and power requirements remain
unknown; no changing real samples verified. /dev/sensors is not that endpoint.

Proximity: Partially supported at discovery only; vendor input nodes exist.
Measurements, units, near/far thresholds, rates, calibration and power remain
Not tested. Do not enable call blanking from this evidence.

Barometer, step counter and hardware rotation vector: Not tested; presence
unknown. No inference is made from the Snapdragon model. Orientation,
gravity, linear acceleration and rotation vector are derived capabilities,
Blocked pending validated inputs and coordinate mapping.

No factory calibration partition was accessed or modified. No firmware,
kernel, boot, Android partition or vendor daemon changes were made. Physical
movement/light/cover tests, calibrated mapping, suspend/resume and power
measurements remain acceptance gates. Fusion development is deferred until
real input validation, as required by Task 10.
