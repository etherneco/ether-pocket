EtherPhone Task 04/11 delivery — 2026-10-20
==========================================

Status: installed engineering release; cellular calling is NOT complete.
The full hardware definition of done is not met. No real outgoing/incoming
call, two-way call audio, screen-off incoming wake or VoLTE was verified.
Emergency calling is unverified. Keep a separate known-working telephone.

Feasibility before implementation
---------------------------------

The mandatory live Phase 0 audit used the existing pinned USB SSH connection.
The actual GM1920 / SDX50M MTP 18827 15 board differs from an assumed LTE-only
OnePlus 7 Pro. It runs the existing Debian ARM64 downstream 4.14.117-perf.
The USIM is present/ready with PIN1 disabled. NAS reports not-registered,
CS/PS detached, power-save and no selected radio interface. Wi-Fi remains
connected. ModemManager owns modem management but exports no modem; its log
reports 'Failed to find a net port in the QMI modem'. rmnet_ipa0 is absent.
An earlier one-shot IPA initialization is not current runtime availability.

QRTR advertises Voice 9 v2, IMS settings 18, IMSA 33 and IMS private 77.
Read-only libqmi Voice Get All Call Info succeeds with zero calls. Thus
Voice enumeration is partially supported even though Get Supported Messages
returns InvalidQmiCommand 71. Dial/answer/indication control is not verified.
Both IMSA status queries return InvalidOperation 70; binding, IMS ownership,
carrier provisioning and compatible vendor dependencies remain unresolved.
These failures do not establish that the modem firmware lacks IMS.
EtherAudio explicitly reports no validated native modem/DSP voice session
or earpiece UCM path. Media PCM and A2DP are not proof of call/HFP audio.

See etherphone-feasibility-2026-10-20.rst for the capability assessment and
primary API references. Neither oFono nor another modem manager was installed.
No firmware, NV/calibration, protected carrier configuration, Android partition,
radio startup, network profile, call or suspend operation was performed.

Delivered independent components
--------------------------------

* Native Qt6/QML light-theme dialer: keypad, plus, backspace, clipboard paste,
  contact/recent suggestions, explicit calling and emergency warning. Compact
  touch targets and bounded external-display layout. Backend-unavailable Call
  is disabled; no UI command submission fabricates an Active/Ended state.
* Unprivileged background service com.etherneco.EtherPhone1 and provider
  interface with a real ModemManager Voice/Call D-Bus adapter. Call objects
  and StateChanged indications are authoritative. Preflight checks normal
  SIM/network readiness; 112/999 bypass those checks only after explicit
  emergency confirmation and still require a real Voice interface. Other-
  region emergency-number discovery is not implemented.
* Persistent private SQLite history: numbers, contact references, direction,
  start/end, observed active duration, result and backend. Search/filter,
  callback preparation, contact creation, delete and confirmed clear. Backend
  loss records Uncertain rather than inventing success or a missed call.
  Monotonic timing excludes held intervals; restart downtime is excluded and
  live-call timing marked incomplete. A private journal reattaches surviving
  backend objects with the same call identity.
* Reusable EtherContacts class, store and com.etherneco.EtherContacts1 session
  API in the same process: create/edit/delete, multiple numbers, emails, notes,
  local photo references, favourites, search and recent-contact metadata.
  UTF-8 vCard 3.0 FN/TEL/EMAIL/NOTE import/export with folding, conflict refusal,
  atomic import and private SQLite backup. Unsupported vCard fields/photos
  are not round-tripped; photo references are edited as local URLs. No SIM
  phonebook access or per-contact ringtone is claimed. Browse snapshots are
  bounded to 300 contacts/history entries; backup/vCard export uses the full
  contact store. Number matching is exact after punctuation removal; no
  country-code inference is applied.
* EtherSMS now attaches the same contact database. Legacy migration is
  transactional, with its old contacts retained as an inactive private archive
  for conflict review. Updating an SMS contact name preserves the shared
  contact's other fields and numbers. No duplicate active phone contact store.
* Existing EtherShell Network & Internet → Calls route, search index, app
  profile and existing AutoUpdate catalog family. No separate distributor or
  remote release. Persistent privacy, missed-notification and retention settings.
  Other calling/audio settings explain the unavailable integrations.
* Shell incoming/active-call overlay with answer/decline/end and caller privacy.
  The existing home lock state is preserved through answering and termination.
  This is not a claim of an authenticated EtherLock implementation or a
  reliable modem wake path. The standalone dialer does not unlock the shell.
* Missed-call desktop notification integration from observed termination.
  Notifications omit caller data. Ringtone, haptics, DND/silent-mode delivery
  are explicitly blocked; a notification alone is not a verified audible ring.
* EtherAudio focus lifecycle and logind sleep inhibition for observed calls.
  EtherPower already respects blocking logind inhibitors. Resources release
  when calls disappear/end; EtherAudio cleans leases on service disconnect.
  No media-to-modem routing, microphone recording or unverified mixer changes.
  Audio routes/mute, hold/resume, conference and additional outgoing calls are
  disabled. DTMF requires observed Active state and remains backend-dependent.
* Private D-Bus activation, systemd user service, ARM64 Debian package,
  allowlisted diagnostic export and safe errors. Existing ModemManager
  PolicyKit authorization is retained; no broad root access rule was added.
  Same-user native applications still have same-user data/control access;
  application sandboxing/contact permissions are not claimed.

Validation
----------

* 20 policy/storage tests pass on Windows, Debian build host and ARM64 phone.
  They cover number handling, emergency gating, actual state transitions,
  duration/held time, stale events, missed/rejected/failure classification,
  backend loss, restart reattachment, contacts, vCard rollback and permissions.
  An ambiguous Start error never automatically deletes/hangs up a possibly
  connected modem call and never retries the call.
* 13 private-bus integration checks pass on ARM64 with both system/session
  bus addresses isolated. Fake modem/audio/notification services ensure no
  real radio/audio calls. Checks include request-vs-state separation, incoming
  answer, DTMF, termination, notifications, reusable contact API, redaction,
  service restart, no network and unconfirmed emergency refusal.
* Native ARM64 write-disabled UI checks pass at 360x900, 1080x2340, 1000x600
  and 1920x1080, plus a 320-DPI font case, with no QML warnings. Each view checks keypad interaction,
  unavailable Call, all tabs, contact-dialog bounds and synthetic locked-call
  presentation/return. Synthetic overlay screenshots are explicitly named.
* EtherSMS ARM64 regression: 15 passing Qt results including setup/cleanup.
  Added legacy migration/shared-database readback and field-preservation checks.
  Its capture tests use synthetic tools; no microphone or SMS send is involved.
* EtherShell Settings acceptance covers Calls and the existing pages in both
  themes across four sizes. Exact final stage/hash, per-view results and
  rollback launcher are recorded in the evidence, rather than inferred from
  source compilation alone.
* Actual installed settings survive an EtherPhone service restart and are
  restored after the test. Contact/history/settings files are 0600. Installed
  Python hashes are recorded for comparison with source.
* Wi-Fi-bound Debian HTTPS returns 200. Existing SSH, NetworkManager,
  ModemManager, Bluetooth, EtherHardware, EtherPower and EtherShare remain
  active. PipeWire/Pulse/WirePlumber retain PIDs 1505/1508/1507, with no audio
  server restart. No reboot, cellular traffic, acoustic, Bluetooth-headset,
  USB-call-route, screen-off call or suspend acceptance is inferred.

Deployment and evidence
-----------------------

Local packages are build/etherphone_0.1.0_arm64.deb and
build/ethersms-phone_0.1.0_arm64.deb. The shell package is
build/ethershell-phone_2.1.0_arm64.deb, staged separately with rollback.
The EtherPhone user service is enabled and ready as an application service;
its current modem/voice/registration availability remains false.

The first installation exposed a root-owned newly created data parent in the
installer's backup step. The installer now assigns that parent to the desktop
user before service startup. Subsequent private-storage and actual restart
checks pass. No broad permission relaxation or root telephony service was used.
The first actual screen capture also exposed inherited point-font scaling in
the new Calls page. Its body/control fonts and dialer editors/dialogs now use
explicit pixel sizes within the existing shell scale. A high-DPI test case
and a fresh live capture verify this separately from the isolated default-DPI
renders. Live shell acceptance also verifies the Phone client's service
readiness rather than inferring it from the separately running service.
The Calls snapshot binding uses a distinct property name so QtQuick Item's
inherited state property cannot coerce it to an animation-state string.
Read-only shell QA loads allowlisted observed Phone metadata to exercise
enabled settings without transmitting any command to the real service.

* evidence/etherphone-audit-2026-10-20.json — live read-only Phase 0 evidence.
* evidence/etherphone-voice-query.json — successful zero-call QMI query.
* evidence/etherphone-arm64-tests.json — isolated policy/protocol results.
* evidence/etherphone-ui/ — four-size UI and SMS regression results/images.
* evidence/etherphone-install.json — installed package hashes and before/after.
* evidence/etherphone-device-verification.json — private files, persistence,
  installed source hashes, HTTPS and service process baseline.
* evidence/etherphone-settings-device/ — isolated shell acceptance/screenshots.
* evidence/etherphone-shell-stage.json and etherphone-shell-deployment.json —
  exact stage, hash, acceptance and rollback launcher.
* evidence/etherphone-final-regression.json — final process/source/connectivity
  comparison after the idle refresh interval and shell deployment.

Stop only this subsystem with systemctl --user disable --now etherphone.
It releases its own focus/inhibitor resources. Existing modem/audio/network
owners remain in place. The shell deployment record identifies the preserved
launcher and previous stage. Preinstall SQLite backups are under the private
directory recorded in etherphone-install.json; do not overwrite newer user
data when restoring. The original EtherSMS package remains in build/.

Remaining acceptance gates
--------------------------

Restore a verified native modem/network-port lifecycle through EtherMobile;
establish real registration and supported Voice/IMS ownership/control; validate
the exact-board Qualcomm DSP/earpiece/microphone path. Then coordinate a real
non-emergency call with a consenting recipient. Verify outgoing/incoming states,
two-way audio, route changes, mute, missed/rejected history, screen-off wake
and failure/restart recovery. Verify carrier provisioning/VoLTE independently
of QMI service advertisement. Ringtone/haptic, authenticated lock service,
call-waiting/conference and physical power-profile interactions still need
compatible backends and device testing. Cellular calling must remain marked
incomplete until those real-device gates pass.
