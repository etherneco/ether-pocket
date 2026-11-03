EtherPower
==========

EtherPower provides battery, charger, thermal and power history, verified CPU/GPU
profiles and application events through the system bus. EtherHardware remains
the shared capability registry. Existing EtherShell Core/Media retain brightness,
X11 software blanking and power-key ownership. Existing NetworkManager,
ModemManager, BlueZ, EtherShare and audio owners remain responsible for hardware.

System API version 1
--------------------

Bus/interface com.etherneco.EtherPower1, path /com/etherneco/EtherPower1.
GetState() returns cached JSON. Changed(s state), Event(s kind,s JSON), and
Notice(s title,s message) publish battery, charging, thermal, profile, sleep and
resume events for EtherMobile, EtherShare, EtherBluetooth, EtherSMS, EtherRemote,
EtherAIR, EtherFleet and EtherMCP. No application is stopped by another module.
Refresh() requests a coalesced refresh. GetHistory(u hours) supports 1/24/168/720,
returning ready=false while an asynchronous query is built; listen to Changed
and query again. Samples are aggregated into at most 240 points.
GetProcessImpact() asynchronously returns only processes belonging to the D-Bus
caller's UID: CPU seconds, sampled CPU percentage after two inspections, RSS and
I/O counters. It reads no command lines, exposes no per-app watts, stores no
process history and caches each caller's result for 20 seconds.

ApplyProfile(s name,s customJSON), Configure(s JSON), RestoreOriginal() and
PowerAction(s suspend|shutdown|restart) require their scoped PolicyKit action.
Read-only queries require no administrator privileges. Profile transactions
accept only discovered CPU policies, advertised governors/frequencies and the
verified Adreno devfreq maximum. CPU cores, thermal protection, charging
registers, firmware, kernel and protected partitions are never written.
Requested, effective, current, supported and error states remain distinct.
Failures restore prior values and report rollback verification separately.
Configuration uses atomic, readback-verified JSON schema 1, with a guarded
legacy migration and retained original controls. Other active CPU policy managers
block profile application. Restart reapplies a saved profile only through the
same compatibility and conflict checks.

ReportDisplayState(s JSON) accepts bounded evidence only from a local active
graphical session verified through logind. The root service never manipulates
the X server. The Settings and Quick Settings use the same native asynchronous
client. Battery/external-power timeouts are delegated to the existing Media
blanker; brightness reuses Core's verified provider. AR sessions are preserved
by default, and battery updates never reconfigure XRandR outputs.

Safety and measurements
-----------------------

The exact kernel source establishes target-specific units and charge-control
semantics; see the phase-0 audit. Unavailable values, negative error sentinels,
missing design capacity, runtime and unmapped thermal sensors remain unknown.
Runtime requires sustained battery-only discharge and a verified capacity;
reported estimates are smoothed, workload-dependent estimates. Battery terminal
power and USB input estimates are separate and do not constitute measured total
device power. Per-process resource statistics do not claim electrical energy.

Default thresholds: low 20%, critical 10%, emergency 5%; actions default to
notifications. Optional saver policies use the same validated transaction.
Emergency request-shutdown prompts for a deliberate user action; it never
forces shutdown. Thermal alerts do not override kernel thermal protection.
Charge-percentage limits are unsupported: charge_control_limit is a thermal
level on this driver. Automatic brightness has no verified light provider.

Suspend remains blocked until a root-owned maintenance validation record for
this exact model/kernel certifies a wake source and records a validationId.
rtc0 currently has no wakealarm and no bounded unattended wake path is verified.
No suspend experiment is run. Merely listing mem/deep is insufficient. If
verified in a separate physical maintenance workflow, suspend uses logind and
its existing block/delay inhibitors. Resume events collect read-only service
health and never silently restart a working service. Wake-source settings are
shown read-only until their behavior has been verified. Do not create a false
validation record to bypass this gate.

History retains 30 days and at most 86,400 compact samples plus 1,000 events in
the root-only /var/lib/etherpower directory. Coarse samples default to 60 seconds;
kernel power events coalesce to avoid excessive wakeups. No kernel-log polling,
wakeup_count polling or continuous full-device rescan is used.

Build with cmake -S etherpower -B build-power -DCMAKE_INSTALL_PREFIX=/usr, then
cmake --build build-power --target package. Install etherpower_0.1.0_arm64.deb
alongside the EtherShell package embedding the integration. Run tests using
python3 -m unittest discover -s etherpower/tests -v on Linux. The CLI provides
state, history, profile, configure, refresh, restore, action and report commands.
