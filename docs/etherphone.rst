EtherPhone engineering release
==============================

This native Qt6/QML dialer uses a same-user session D-Bus service and the
existing system ModemManager Voice API. It is not verified cellular telephony.
Read etherphone-real-call-2026-10-21.rst for the latest hardware findings:
an outgoing call was answered, but audio failed; the dedicated DSP voice
session reports missing calibration and has no compatible installed loader.
The October 20 feasibility report is historical. IMS, VoLTE,
two-way audio, screen-off wake, ringtone and emergency calling are unverified.
Keep a known-working emergency telephone. Never place an emergency test call
without an authorized, coordinated procedure.

The original Android ACDB loader and its matching Bionic runtime were later
identified and successfully dynamically loaded in an isolated process; see
etherphone-acdb-loader-2026-10-21.rst. Calibration initialization/upload and
two-way audio are still unverified.

Build with scripts/build-etherphone.sh on the existing Debian cross-build
host. Install the local ARM64 package using dpkg and enable the session unit
with systemctl --user enable --now etherphone. No modem manager is installed
in parallel with ModemManager, and no radio/firmware configuration is changed.
Upstream ModemManager PolicyKit authorization remains authoritative; no
unrestricted custom allow rule or root telephony daemon is introduced.
The existing session bus restricts access to the logged-in Unix user.
Same-user programs retain that user's contact/control access; this is not an
application sandbox or per-app contact permission system.

Contacts are reusable in $XDG_DATA_HOME/ethercontacts/contacts.sqlite;
the com.etherneco.EtherContacts1 session API exposes Search and contact-only
commands from the same process. It is activated by the etherphone user unit.
history is in $XDG_DATA_HOME/etherphone/history.sqlite. Both use private
directories/files (0700/0600). EtherSMS attaches that contact database,
migrates legacy contacts transactionally and keeps a legacy archive for
conflict review. It does not create a second active contact store. Multiple
numbers, emails, notes, favourites and local photo references are supported.
No regional number guessing or national-to-international rewrite is applied;
lookups match normalized numbers exactly. SIM phonebook access is unverified.
The vCard 3.0 subset supports FN/TEL/EMAIL/NOTE and UTF-8 line folding;
unsupported fields/photos are not round-tripped. Imports are atomic and
existing telephone-number conflicts require explicit editing/merging.
Local database backup is available from Settings. Exports are private files
under $XDG_DATA_HOME/etherphone/exports. Diagnostics use a field allowlist
and omit caller/contact data and subscriber identifiers.

Call states come from ModemManager Call objects and StateChanged signals.
A successful CreateCall/Start/Accept/Hangup request never sets Active or Ended.
Call durations accumulate only across observed Active intervals, excluding
held time; these are observed durations, not carrier billing measurements.
Production timing uses an epoch anchored to the monotonic clock. A private
live-call journal reattaches a still-exported call after service restart;
unobserved downtime is excluded and timing completeness is marked false.
Missing call objects or a lost backend produce Uncertain history, never a
fabricated successful termination or missed call. No automatic dial retry.
Additional outgoing calls, hold, conference, audio routes and mute are gated.
DTMF requests require an observed Active call; a backend may still reject
them. Normal calls require SIM/network readiness. Recognized UK baseline
emergency numbers 112/999 bypass ordinary readiness validation, require an
explicit confirmation, and still require a real Voice interface. Other-region
emergency-number discovery is not implemented.

The background service survives UI exit, requests EtherAudio call focus and
a logind sleep inhibitor for observed calls, and releases resources when
none remain. Focus is not a verified DSP voice path. Backend refresh on
resume does not establish a wake-capable modem. Screen wake, ringtone/haptic
delivery and secure EtherLock integration remain hardware/system gates.
The existing shell home lock is not an authenticated EtherLock service.
The shell incoming overlay never changes lock state and hides caller data
by default. Missed notifications follow observed incoming termination only.
No automatic recording, modem NV changes, firmware flashing, carrier
authentication bypass, unattended calls or suspend experiments are included.

Persistent settings currently cover lock-screen caller privacy, missed
notifications and history retention. Other settings explicitly describe
unavailable integrations rather than saving ineffective audio/ringtone values.

Validation
----------

python -m unittest discover -s etherphone/tests -v exercises independent
number validation, emergency preflight, call state/history, backend loss,
duration, privacy, contacts, duplicate rollback, vCard and file permissions.
Synthetic tests are isolated from real radios, audio and personal contacts.
The delivery report records actual ARM64 and UI results separately from
physical acceptance. A live non-emergency call requires a consenting test
number, restored modem/network and a validated DSP voice path. Incoming,
earpiece/speaker/HFP/USB/mute, screen-off and suspend tests remain required.
