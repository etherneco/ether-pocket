EtherPower phase 0 — physical and architecture audit
===================================================

Actual target: Debian 13.7 ARM64, 4.14.117-perf, Device Tree model SDX50M MTP
18827 15. Evidence: evidence/etherpower-audit.json. Battery is Full/100%, with
readable voltage, current, temperature, health and charge counter. Current is
zero on USB; this does not mean the device consumes zero watts. USB reports
present=1, online=0, real_type=USB and pd_active=0 despite type=USB_PD. Do not
infer negotiated PD or charger disconnection from the nominal type/online alone.

Verified kernel-source quirks
----------------------------

The existing build host's exact kernel tree is /opt/etherpocket/kernel.
qpnp-smb5.c maps battery charge_control_limit to system thermal level, not a
charge percentage. Therefore 80/75% charge limiting is unsupported on these
interfaces. Charging_enabled, input_suspend, calibration and JEITA controls
will not be written. smb5-lib.c:smblib_read_usbin_voltage_chan explicitly
divides USB ADC voltage by 1000: this target reports USB voltage in mV.
bq27541_battery_voltage returns uV; bq27541_average_current returns sign-inverted
uA (positive discharge, negative charging). The external gauge's full capacity
is mAh; charge_counter is supplied by the internal gauge and must not be
assumed to share calibration. charge_full_design=-22 is unavailable, not a
negative design capacity. No invented battery wear percentage is justified.

Three CPU clusters expose supported frequency lists and governors; all were
configured for performance at maximum frequencies before optimisation. The
Adreno devfreq governor is msm-adreno-tz, with 257/345/427/499.2/585 MHz and
standard min_freq/max_freq controls. Balanced can use schedutil; saver may cap
supported maximum frequencies without disabling cores or touching thermal
controls. Capture original values and verify/rollback every write transaction.

Thermal zones include CPU TSENS names and gpuss-max-step, confirmed against
sm8150-thermal.dtsi. Some thermal interfaces are voltage/threshold sensors
(for example vbat/vph); do not label every raw thermal value as temperature.
Only verified CPU/GPU mappings and power_supply battery/charger temperatures
will contribute to named temperature summaries. Unknown zones retain raw labels.

Existing owners and suspend blocker
----------------------------------

Media owns X11 power-key dispatch, screenshot chords and the existing software
screen blanker. It suppresses XFCE's power-key action while running and restores
it on exit. XFCE holds logind's hardware-key inhibitor. No new input listener or
second screen blanker will be installed. Core owns verified backlight writes
through logind/direct access; panel0-backlight is the real DSI backlight, while
the other PMIC backlight is unused. Existing display management is EtherAIR/X11.

Earlier user-confirmed DPMS wake failures require ETHERSHELL_SOFT_BLANK=1. Keep
this workaround: a black surface does not prove display hardware power-down or
measured power saving. External output must not be reconfigured on battery
events. If connected, external-active policy must preserve its session.

Kernel advertises freeze/mem and s2idle/deep. rtc0 exposes no wakealarm. Its
since_epoch does not provide a verified wall-clock wake path. Reading
/sys/power/wakeup_count blocked in pm_get_wakeup_count during audit; the exact
audit process was terminated and no power state was changed. Never poll that
interface. There is no verified bounded RTC wake or unattended suspend recovery
path. Suspend must remain blocked with this specific reason until a separate
physical wake-validation workflow certifies this exact kernel/device.

NetworkManager and ModemManager already hold delay sleep inhibitors. Suspend
must go through logind, preserving inhibitors; never stop working services to
simulate recovery. Post-resume checks query the same EtherHardware registry.
UPower is installed but failed; power-profiles-daemon/TLP are inactive. XFCE
remains the session/input policy provider, and no competing power daemon will
be installed or existing hardware service restarted.

Baseline and implementation decision
------------------------------------

The saved baseline samples are USB-powered low-activity observations, with Wi-Fi,
Bluetooth, SSH and USB recovery active. X11 screen state was not measured in
this initial audit and is not asserted. LTE data is already failed and AP is
quarantined. Physical AR glasses, battery-only discharge, charger removal and
an external power meter are unavailable to unattended software. No total-device
or approximately-2-W conclusion can be drawn from battery current=0. Additional
screen-blank samples can use the existing, verified software blanker and timed
wake restoration; suspend experiments are prohibited without a verified wake.

Implement one narrow, PolicyKit-controlled power service: reuse EtherHardware
readers and its system capability API; retain existing network/audio/input
owners; publish cached power state and application events. Event-triggered
refreshes plus one bounded, coarse telemetry/history cadence support runtime
estimates and graphs. Use a bounded SQLite store, nullable measurements,
readback-verified CPU/GPU transactions and atomic configuration migrations.
The existing Settings Battery & Power route and Quick Settings share one native
asynchronous client. No GUI runs as root, and no arbitrary root command is exposed.
