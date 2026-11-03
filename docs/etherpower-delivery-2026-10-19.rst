EtherPower delivery — 2026-10-19
===============================

Release state
-------------

EtherPower 0.1.0 is installed, enabled and active on the actual ARM64 phone.
EtherShell runs as mobian (UID 1000), with native Battery & Power Settings,
Quick Settings and the coordinated power-button menu. The final requested and
effective profile is Balanced; brightness is restored to 5%, timeout to 300s,
and the screen is on. Android partitions, bootloader, kernel, charger controls
and thermal protections were not modified.

Active shell: ``/opt/ethershell2/2.1.0-power-552338610e39``.
Previous shell: ``/opt/ethershell2/2.1.0-hardware-39dc755eec00``.
The previous startup launcher is preserved at
``/home/mobian/.local/bin/ethershell2-start.before-2.1.0-power-552338610e39``.
Activation validates the staged binary and has startup-failure rollback.
The service retains original CPU/GPU controls; its guarded RestoreOriginal
operation restores them, and removal restores an applied profile before stopping.

Local ARM64 packages and SHA-256:

* ``build/etherpower_0.1.0_arm64.deb``:
  ``b9402737974657d4305e40fb2d3af915080406a04e2e0bd9d1f4955edda7fb64``
* ``build/ethershell-power_2.1.0_arm64.deb``:
  ``552338610e39e9fb17dbe1203e389845ede1a440b988de00a980dba2f86d2d37``

The existing distributor recognizes EtherPower. No remote release was published.
API, security, persistence, events and integration are documented in
``docs/etherpower.rst``. Initial device/source findings are preserved in
``docs/etherpower-audit-2026-10-19.rst``.

Validation completed
--------------------

All 19 backend tests pass on the build host and installed ARM64 phone.
All 1132 UI checks pass: 283 checks at each of 360x900, 1080x2340, 1000x600
and 1920x1080, covering both themes, existing Settings/Hardware sections,
nine power sections, Quick Settings and the power menu. Final acceptance logs
have no QML warnings. The actual long-press screenshot was visually reviewed.

Actual kernel interfaces were exercised for Performance, Balanced and Saver,
with effective readback, original-control restoration, invalid-request rejection,
and persistence after a service restart. Saver CPU maxima were
1209600/1612800/1920000 kHz and GPU maximum 345000000 Hz; Balanced restores the
original maxima with schedutil. The Adreno governor remains unchanged.

Live display validation passed five off/wake cycles, short holds, idle blanking,
waking with the power input, a 1.8-second long hold opening the power menu,
brightness 15% with actual readback and restoration to 5%, and a saved 15-second
external-power timeout causing blanking before restoration. Input was injected
through the existing kernel input interface; this does not certify physical
touch accuracy or a person pressing the hardware button.

History aggregation, schema migration, bounded retention, transactional profile
rollback, competing-manager rejection, caller-owned process resources and the
suspend safety gate are covered by tests. Settings/configuration is stored
atomically on persistent storage and reapplied after a tested service restart.
An explicitly user-approved full phone reboot subsequently passed on 2026-10-20
(Europe/London). The user selected etherPocket in the boot menu. Boot ID changed
from ``46d7ed2f-bf16-4e08-b8ec-a06d40c6559d`` to
``498cc181-63b7-4905-bea6-1a303326cc60``. EtherPower was enabled and started
automatically, with Balanced effective. Full configuration, power preferences,
original-control snapshot, launcher and binary hashes matched the pre-reboot
snapshot. Brightness 5%, timeout 300s and the existing software blanker were
confirmed in the restored UID-1000 shell. Wi-Fi-bound HTTPS returned HTTP 200.
All previously active services returned active. The previously failed static
ethermobile-data service became inactive/dead with Result=success on the new
boot; this is not evidence of restored cellular connectivity. The actual Settings
screen was captured and reviewed after reboot. This verifies reboot persistence;
a full power-off/cold-start was not tested.

Final read-only regression confirmed Wi-Fi-bound HTTPS HTTP 200, SSH access,
Bluetooth powered on and active NetworkManager, ModemManager, EtherHardware,
EtherShare, modem, USB debug and USB storage services. IPv4 forwarding is 0.
The pre-existing cellular-data problem and AP quarantine remain unresolved;
ethermobile-data changed from failed to inactive on reboot as recorded above.
Service activity does not certify working cellular traffic or hotspot clients.
No radio reconfiguration, external-display hotplug or physical audio test was run.

Power observations and their limits
----------------------------------

These are individual, sequential USB-powered ADC observations at brightness 5%,
not steady-state benchmarks or evidence of a particular battery-life improvement.
The initial audit's screen state was not measured and is labelled accordingly.
Battery current and USB input are separate measurements. Input watts are an
estimate from the observed USB voltage/current, not total device consumption.
Battery terminal power of zero while Full does not imply zero device power.

.. list-table:: Controlled live observations
   :header-rows: 1
   :widths: 38 16 16 15 15

   * - Condition
     - USB estimate W
     - Battery W
     - CPU C
     - Battery C
   * - Performance, screen on
     - 2.3852
     - 0.0000
     - 51.5
     - 30.4
   * - Balanced, screen on
     - 1.7044
     - 0.0000
     - 39.1
     - 30.3
   * - Balanced, software blank
     - 1.7257
     - 0.0000
     - 39.5
     - 30.4
   * - Balanced, bounded one-core load
     - 2.3852
     - 0.6553
     - 60.8
     - 30.3

Positive calibrated battery current means discharge; the load observation can
therefore include battery contribution while USB is attached. Values from these
different interfaces are not added into a fabricated total-power metric.
The software blanker covers the screen while leaving the physical panel powered;
it provides no proof of panel power savings. Existing DPMS wake failures require
retaining this recovery-safe behaviour.

During a 20.0007-second quiet interval the service consumed 0.1500% of one CPU core
and reported 36012 kB RSS. This is a short process-overhead sample, not an
electrical energy measurement. Process diagnostics expose CPU/RSS/I/O for the
caller's UID and no invented per-application energy.

Specific blockers and remaining physical acceptance
---------------------------------------------------

* Suspend: the kernel advertises freeze/mem and s2idle/deep, but rtc0 has no
  wakealarm and there is no verified bounded wake/recovery path for this exact
  kernel/model. Suspend remains disabled with that reason visible in Settings
  and the power menu. No suspend was attempted. Resume signals and refresh
  handling exist; physical post-resume touch/radio/audio recovery is unverified.
* Charging limits: battery charge_control_limit is a system thermal mitigation
  level (0..4), not an 80% charge threshold. No supported percentage charging
  limit or verified USB-PD negotiation is claimed. Charger diagnostics are read-only.
* Battery-only endurance, physical USB detach/reattach, charge transitions,
  external AR display attach/detach and physical touch/audio
  require further physical acceptance. Runtime remains unknown until enough
  calibrated battery-only discharge samples are available. Wear remains unknown
  because a reliable design-capacity reference is unavailable.

Evidence
--------

* ``evidence/etherpower-audit.json`` — original hardware/source observations.
* ``evidence/etherpower-device.json`` — package install and backend tests.
* ``evidence/etherpower-profiles.json`` — real profiles and restart persistence.
* ``evidence/etherpower-settings-device/acceptance.json`` — all four UI sizes.
* ``evidence/etherpower-shell-stage.json`` and
  ``evidence/etherpower-shell-deployment.json`` — staging/activation records.
* ``evidence/etherpower-live-validation.json`` — display, samples and overhead.
* ``evidence/etherpower-long-press.png`` and ``evidence/etherpower-live.png`` —
  actual phone screenshots.
* ``evidence/etherpower-regression.json`` — final Wi-Fi/services/profile and hashes.
* ``evidence/etherpower-reboot-before.json``, ``etherpower-reboot-after.json``,
  ``etherpower-reboot-comparison.json`` and
  ``etherpower-reboot-service-transitions.json`` in ``evidence/`` — approved
  full reboot, persistent hashes and exact service-state differences.
* ``evidence/etherpower-reboot-display.json`` and ``evidence/etherpower-reboot.png``
  — restored live display/session on the new boot.

Read-only revalidation — 2026-10-20
---------------------------------

The repeated master task was checked against the existing implementation and
the reachable phone. No replacement service, reinstall, reboot or hardware
policy change was needed. All 19 installed backend tests passed as the mobian
user on ARM64. SHA-256 comparisons confirmed that power.py, service.py, cli.py
and tests/test_power.py exactly match the workspace sources. A Windows-host
run passed 18 tests; process-resource inspection requires Linux os.sysconf and
was therefore validated on the actual target instead.

EtherPower and EtherHardware remain active, with Balanced requested and
effective. The battery reports Full, 100%, 4.303 V and 29.1 C at the sampled
instant. Wi-Fi-bound HTTPS returned HTTP 200, SSH remained accessible and
Bluetooth reported powered on. The shell runs as UID 1000 with its existing
300-second software blanker and 5% brightness preference. The same previously
verified boot is still running. Cellular data remains inactive; working cellular
traffic is not claimed.

Fresh results are saved in
``evidence/etherpower-revalidation-2026-10-20.json`` and the refreshed
``evidence/etherpower-regression.json``. Prior profile/display/UI checks above
were not repeated during this read-only pass. The suspend wake-path blocker,
unsupported percentage charge limits, physical display/charger acceptance and
battery-only measurements remain outstanding as described above. This is not
an assertion that all physical acceptance milestones are complete.
