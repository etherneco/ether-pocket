EtherFingerprint — GM1920 feasibility and delivery, 3 November 2026
================================================================

Release status: BLOCKED for authentication. Diagnostics and the provider
abstraction are implemented. This is not a working fingerprint unlock release.

Evidence
--------

``evidence/etherfingerprint-device-audit.json`` was collected over pinned SSH
from the physical GM1920 Debian installation, Linux 4.14.117-perf ARM64.
The repeatable collector is ``scripts/audit-etherfingerprint-device.py``.
It enumerates SPI, I2C and platform devices, device tree, input, character-device
metadata, modules, kernel config and Android vendor directory metadata.
Android vendor_b is inspected with debugfs without -w, without mounting,
executing vendor code, copying firmware or reading templates.

Findings and classification
---------------------------

* Vendor identification: Supported. Device tree compatible goodix,fingerprint;
  platform device soc:goodix_fp bound to goodix_fp. Exact silicon model and
  firmware revision remain Not tested; the compatible string is not a chip ID.
* Interface: Partially supported. /dev/goodix_fp exists (492:0, mode 0600),
  gf_input is registered; no fingerprint SPI/I2C device was enumerated.
  Transport inside secure world is not established by this observation.
* Driver availability: Supported for discovery. CONFIG_INPUT_FINGERPRINT,
  CONFIG_FINGERPRINT_DETECT and CONFIG_FINGERPRINT_GOODIX are built in.
  Successful capture or matching is Not tested.
* Secure backend: Blocked. QSEECOM is built in and /dev/qseecom exists.
  Vendor metadata lists libQSEEComAPI.so, libgf_ud_hal.so,
  goodix.fod.msmnile.so, the fingerprint 2.1 service, Goodix/OnePlus extension
  libraries, Keymaster and Gatekeeper components. These are evidence of an
  Android integration, not proof of a usable Debian trusted authentication API.
  Trusted-app names, firmware compatibility, enrollment authorization tokens,
  protected storage ownership and assertion validation remain unverified.
* Debian runtime: Blocked. No installed fprint/libhybris packages and no fprintd
  bus service. Android linker64 and /vendor/bin/hw are absent. Binder device
  nodes alone do not supply Android service management or a Bionic runtime.
* Display: Not tested. DSI HBM, hbm_brightness, op_friginer_print_hbm and
  dimlayer_bl_en paths exist. Their timing, safe values, sensing geometry and
  crash recovery are unverified. No brightness/sysfs writes or illumination
  operations are implemented. No lock-screen sensor position is guessed.
* Enrollment, matching, EtherLock unlocking, PAM and Polkit: Blocked.

Linux framework review
----------------------

Upstream's development support list does not establish support for this
Goodix platform interface: https://fprint.freedesktop.org/supported-devices.html
(reviewed 3 November 2026). It distinguishes USB and specific SPI devices;
Goodix USB support cannot be transferred to this phone by vendor name.

Community investigation candidate:
https://github.com/wrobelda/goodix-fp-spi-linux (reviewed 3 November 2026).
It reports a QSEE/libfprint stack for a Xiaomi Pad 5 Pro 5G with a GF3626
power-button sensor, and explicitly leaves the in-display family untested.
It also identifies incomplete signed enrollment-token handling and unobserved
trusted-app lockout enforcement. This is not verified GM1920 compatibility,
nor permission to install a trustlet or expose biometric frames. Other laptop
Goodix SPI projects target different devices and do not establish phone support.
No third-party binaries or drivers are bundled or enabled.

The preferred option remains a genuinely supported libfprint/fprintd backend.
The alternate research path is a licensed vendor-compatible local adapter that
retains trusted matching, protected templates and hardware-authenticated
identity assertions. Neither path is established on this device. Do not replace
it with host-side image/hash comparison or bypass secure world.

Delivered boundary
------------------

etherfingerprintd is a system D-Bus diagnostic service running as a dedicated,
unprivileged etherfp system account. It has no sensor access, device writes, timers,
template storage, external commands or match-result signals. GetState and
GetCapabilities return cached allowlisted metadata. Restart it after hardware
changes to collect new evidence. Refresh in Settings reads the cached snapshot.
Capabilities remain false even if device or QSEE nodes exist.

HardwareProvider defines the fail-closed boundary; enrollment, verification and
identity management reject all calls, including injected match booleans.
No provider/plugin is loaded from caller-supplied configuration.
The service intentionally exposes no management or verification API until
authorization and trusted assertions can actually be enforced.

EtherShell Security & Privacy includes Fingerprints diagnostics, an unavailable
toggle and disabled Add Fingerprint control. EtherHardware identifies the
Goodix component with authentication unavailable. EtherLock's state machine and
PIN/password paths are preserved; it consumes no biometric boolean or signal.
EtherPower requires no sensor lease because no operation activates hardware.
No notifications contain biometric data. PAM, Polkit, SSH and Android partitions
are unchanged. There is no remote authentication, template export or Fleet API.

Build and distribution
----------------------

Run ``sh scripts/build-etherfingerprint.sh`` in the existing Debian build
environment. It runs provider security tests and produces the ARM64 Debian
package with service, CLI, integration sources, tests and documentation.
The diagnostic service is started explicitly with
``systemctl start etherfingerprintd`` after installation; no postinst modifies
authentication or enables biometric unlocking. ``etherfingerprint`` reads status.
Installation creates only the service account and reloads systemd/D-Bus policy.
The distributor.json uses the existing EtherUpdate/AutoUpdate Center package
convention and marks authentication blocked. Publication/signing is pending;
there is no new updater and this is not advertised as operational biometrics.

Required evidence before enabling authentication
------------------------------------------------

1. Establish exact sensor/firmware and licensed secure backend compatibility.
2. Verify local user/session ownership, recent PIN/password management approval,
   trusted challenge-bound results, cancellation and rejection of replay.
3. Verify sensor geometry on the internal panel and a bounded illumination lease
   whose owner restores panel state even after service death or suspend.
4. Real enrollment, enrolled acceptance, unenrolled rejection, retry/lockout,
   timeout, reboot primary-auth requirement, recovery and privacy testing.
5. Review EtherLock assertion consumption inside its existing state machine.
6. Rebuild and visually verify Settings on the physical portrait display, then
   complete touchscreen, brightness, shell, power, SSH and reboot regressions.

Milestones 1 and 2 have discovery evidence and a documented backend blocker.
Milestones 3–10 and the full Definition of Done remain unfulfilled. No sensor
initialization, enrollment, verification, unlock, suspend or reboot test is
claimed from read-only inventory or unit tests.

Validation completed
--------------------

* 33 Linux unit tests passed: 3 EtherFingerprint, 21 EtherHardware and
  9 EtherLock. Windows cannot create the Linux fixture paths/symlinks, so these
  tests were run in the existing EtherPocketBuild Debian environment.
* Isolated Qt portrait renders at 360x800 and 480x960 loaded without QML
  warnings; disabled enrollment and authentication controls were asserted.
  These are blocked-state fixtures, not hardware or authentication tests.
* The ARM64 diagnostic package was installed on the physical phone and its
  service started as etherfp with DevicePolicy=closed and NoNewPrivileges=yes.
  Both root and mobian can read status; an unprivileged forged Verify request
  is denied. Authentication capabilities remain false with real hardware present.
* ``evidence/etherfingerprint-device-verification.json`` records identical
  before/after PAM hashes, panel brightness and monitored service PIDs/states.
  Boot enablement remains disabled. No shell switch or reboot was performed.

At Task 13 delivery, the EtherShell and EtherHardware integration changes were
source/build artifacts. See etherfingerprint-manager.rst for the subsequent
Task 13.1 manager activation. The hardware service integration remains a source
change; biometric distribution and hardware acceptance remain pending.
