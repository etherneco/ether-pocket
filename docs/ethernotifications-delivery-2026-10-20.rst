EtherNotifications delivery assessment — 20 October 2026
========================================================

Status
------

Implemented and installed as an engineering release on the OnePlus 7 Pro. This
is an independent notification daemon and real EtherShell integration, not a
UI-only list. The entire master-task Definition of Done is NOT yet satisfied:
authenticated EtherLock, verified haptics, controlled inline reply, and physical
suspend acceptance remain outstanding. Attended reboot acceptance passed.
No claim of device wake, real
calling, emergency delivery, or physical audibility is made.

Delivered
---------

* Single org.freedesktop.Notifications owner, acquired without replacement or
  queuing; independent enabled systemd user service and D-Bus activation.
* Standard Notify, CloseNotification, capabilities/server information and
  sender-directed action/closed signals. Session-PID/UID identity, ownership,
  bounded input, rate limits and safe plain-text/theme-icon rendering.
* SQLite history, configurable retention, monotonic IDs, secure deletion,
  active/read/dismissed/expired lifecycle, bounded records and metadata export.
  Sensitive bodies are never written; secret/transient cards remain in memory.
* Mobile Notification Center, search/application/priority filters, grouped
  conversations/categories, collapse, actions, read/dismiss, clear, history,
  delete/export and action-free restoration. Persistent warnings resist bulk
  clear. Queued banners support actions, tap, timeout and swipe dismissal.
* One backend for Settings and Quick Settings, global/per-app enablement,
  priorities, sound/silent policy, banners, grouping, lock visibility, retention,
  DND modes, explicit application exceptions, local-time overnight schedules and
  manual override. No arbitrary urgency flag grants a critical bypass.
* EtherSMS conversation/event hashes, existing repository and mark-as-read/open
  actions; EtherPhone missed-call history action and single-instance history
  focusing. Incoming-call presentation stays in its dedicated overlay.
* EtherAudio built-in cues through its existing category volume, focus and
  PipeWire path. EtherPower system warnings, Saver policy, screen-off retention
  and logind sleep handling. Existing local-seat LockedHint/Lock signals enforce
  privacy independently of the shell's home restriction.
* Debian ARM64 packages, existing-distributor manifest, tests, migration scripts,
  source hashes, private backups and documented limitations. Packages remain
  local engineering builds; no public distribution publication was performed.

Verification
------------

On actual ARM64 hardware, 12 notification policy tests, five private-bus protocol
tests and nine checks of the real Qt client passed. The Qt client checks exercise
delivery, action close, unread count, DND suppression, a configured DND exception
and lock redaction. Protocol tests include an unauthorized peer, directed signals,
expiry reasons, service restart, stripped stale actions and refusal of a second
notification owner. A private six-client burst verifies the global cap and
post-burst state-query responsiveness: 120 attempts completed in 0.65 seconds,
99 were accepted (one earlier request occupied the global window), 21 were rate
limited, and a subsequent state query took approximately 14 ms.
Notification Center, Settings and banners render without QML
warnings at 360x900, 1000x600, 1920x1080 and native 1440x3120/320-DPI conditions.
Native controls use explicit pixel fonts to avoid double scaling by the desktop's
high-DPI defaults. Long unbroken notification content can wrap within the cards.

Full existing EtherShell Settings regression passes 325 checks per view across
narrow, landscape and external layouts (975 total), including existing network,
SMS, phone, sharing, hardware, power, audio and appearance routes. Consumer
regression passes 20 phone tests plus its private-bus fixture, 22 audio tests,
eight audio protocol tests and 15 EtherSMS tests. Fixtures never place a real call,
send an SMS, vibrate, change radio configuration or open real audio hardware.
Private shell tests isolate XDG_STATE_HOME as well as configuration/data/runtime.

Live acceptance verifies a real standard notification and banner, durable history,
EtherShell restart with the daemon remaining alive, daemon restart with automatic
shell reconnection, no banner replay, rejection of ordinary-client content reads,
and screen-off/on retention. EtherAudio reported completion of its built-in cue
pipeline; this is not physical audibility confirmation. SQLite mode is 0600.

The user-attended full reboot also passed on 20 October 2026. The user selected
EtherPocket in the boot menu. A changed boot ID proves a new boot; the notification
daemon and UID-1000 EtherShell started automatically. All prior history records,
the current test card, saved settings, preferences, launcher, shell binary and
notification code survived unchanged. The restored card did not replay its
banner. Wi-Fi-bound HTTPS returned 200; SSH, existing system services and all
five checked audio/phone user services recovered, with zero daemon crash
restarts. The pre-existing inactive ethermobile-data service stayed inactive.
The restored Notification Center was captured and visually inspected.

A device sample over approximately 437 seconds measured 0.23% of one CPU core
and 31,040 KiB RSS for the daemon, with zero automatic restarts. The one-record
acceptance database occupied 16 KiB. The sample includes ordinary bus events,
expiry and shell lease renewal, not a synthetic zero-event benchmark. Current
measurements and package hashes are in the final regression evidence.

Wi-Fi-bound HTTPS returned 200, SSH remained accessible, and NetworkManager,
ModemManager, the modem service, Bluetooth, EtherHardware, EtherPower and
EtherShare stayed active. PipeWire, pipewire-pulse and WirePlumber PIDs did not
change. Existing telephony remains an engineering implementation with real calls
unverified. No modem/network reconfiguration, kernel or Android partition writes
were performed.

Remaining acceptance and unavailable providers
----------------------------------------------

* EtherLock authentication is absent. Existing homeLocked is not authentication.
  Redacted/count-only cards and logind lock-hint handling are implemented;
  physical authentication/lock transitions and secure tap-to-open still require
  acceptance with the real EtherLock provider.
* EtherHardware detects /sys/class/leds/vibrator but has no verified haptic
  operation. Vibration activation is unavailable rather than simulated. Short,
  long and patterned haptic delivery require hardware implementation/acceptance.
* Inline reply is not advertised or fabricated. Open conversation is supported;
  an application-owned reply API with confirmation is still required.
* Selected-contact/repeated-call exceptions and trusted alarm delivery await
  verified producer integration. Per-app DND exceptions are available now.
* Existing EtherPower blocks deep suspend on this kernel because recovery/wake
  is unverified. Screen blanking and process restart are not suspend tests.
* Reboot persistence is verified with user attendance. The boot menu still
  requires someone to select EtherPocket; unattended boot selection and full
  power-off/cold-start acceptance are not implied by this reboot test.
* Physical sound confirmation, real incoming SMS/missed-call delivery, hardware
  thermal/battery thresholds and extended battery endurance remain unverified.

Evidence and recovery
---------------------

Evidence is under evidence/ethernotifications*: audit, device/acceptance.json,
integration-tests.json, shell-stage.json, install.json, live-verification.json,
final-regression.json and the live/native screenshots. Source SHA-256 checks
bind tested Python/QML/client files to the deployed release. Final package hashes
are external evidence so the package does not attempt to contain its own digest.
Attended reboot evidence is in ethernotifications-reboot-before.json,
ethernotifications-reboot-after.json, ethernotifications-reboot-comparison.json
and ethernotifications-reboot.png. Reproduce the snapshot/comparison workflow
with scripts/test-ethernotifications-reboot.py; reboot is a separate explicit
action and requires someone at the boot menu.

Migration saves the previous launcher and module files beneath the private
/var/backups/ethernotifications directory before changing ownership. The install
report records exact previous/current stage paths and backup directory. To roll
back an ownership migration, stop the current graphical shell, disable/stop
ethernotifications, restore the recorded launcher/module backup, reload the user
manager and start the recorded previous shell. If returning to the original
embedded implementation, use the initial-install report/backup; a previous new
shell still needs the notification daemon. Do not leave an activation-triggered
new daemon competing with the original embedded shell. Never alter Android
partitions as part of rollback. File restoration alone does not revert dpkg's
package metadata; use the recorded prior packages when doing a full package
rollback. Persistent history can be retained privately for recovery.

Interface reference: https://specifications.freedesktop.org/notification/latest/.
