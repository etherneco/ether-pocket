EtherAudio gap implementation — 2026-10-20
=========================================

Scope
-----

The master task was compared with the repository and reachable ARM64 phone.
Existing working playback, microphone UCM, PipeWire/WirePlumber, Bluetooth,
Media's hardware-key owner and the Settings architecture were reused.
There was no EtherAudio package, central policy API, focus service, managed
capture API or complete Sound settings before this change. Those gaps are
implemented in etheraudio/ and integrated into the existing applications.

This is an installed engineering release with explicit physical acceptance
remaining. It is not certification that every master-task milestone is complete.

Final installed state
---------------------

EtherAudio 0.1.0 runs as the desktop user with its systemd user service enabled.
The active shell is /opt/ethershell2/2.1.0-audio-51d6c04db1c7; its preserved
previous stage and rollback launcher are recorded in the deployment evidence.
All 1276 final UI checks pass (319 per size at 360x900, 1080x2340, 1000x600
and 1920x1080, both themes), with actual endpoint metadata seeded into the
write-disabled isolated UI and no QML warnings.

Synthetic X11 volume-key events through the existing shell owner verified
exactly one step: 70 -> 65 -> 70 percent. No playback or recording was started.
This verifies software dispatch and on-screen feedback, not a person's physical
button presses. The final live Settings and Quick Settings screens were captured.

The final 70-second periodic-refresh check retained one service PID with zero
automatic restarts and observed a newer telemetry timestamp. Installed Python
sources match workspace SHA-256 hashes. Wi-Fi-bound HTTPS returned HTTP 200;
SSH, Bluetooth and all previously active services remain available. PipeWire,
pipewire-pulse and WirePlumber retain their original PIDs (1505/1508/1507).
Balanced remains effective. Cellular data remains inactive as before this task;
neither working cellular traffic nor physical acoustic output is inferred.

Requirement assessment
----------------------

* Hardware/software audit: evidence/etheraudio-audit-2026-10-20.json records
  ALSA cards/PCMs/mixers, the actual sm8150-asoc-snd driver, backend endpoints,
  profiles and service ownership. No assumed internal card index is used by
  EtherAudio; controls refer to discovered server IDs/names. Earlier Qualcomm
  DSP, firmware and WCD934x/TFA9874 bring-up remains documented in
  docs/audio-2026-10-16.rst. No driver or calibration change was needed.
* Architecture: new unprivileged session D-Bus policy service on the existing
  PipeWire Pulse protocol. WirePlumber retains hardware/UCM ownership. There is
  one audio server stack and one X11 volume-key handler. GetState is cached;
  kernel audio is not polled or continuously held open by EtherAudio.
* Speaker: reused the previously user-confirmed 24-bit UCM speaker route.
  Current route detection, volume and mute readback passed. An interactive
  quiet-tone test and audible-result recording are available; no new acoustic
  confirmation is claimed from this unattended run.
* Microphones: reused HandsetMic. Added bounded managed capture, source
  selection, monitor rejection, input mute/volume, explicit three-second
  diagnostic, temporary playback/deletion and capture-only level monitoring.
  The unattended tests used synthetic PCM, never the real microphone.
* Earpiece/cellular calls: blocked. The native earpiece UCM path, modem DSP
  voice-session control and an actual cellular call are not validated.
  EtherPhone can request call routing through the API and receives this reason.
  A working speaker/microphone does not mark voice-call audio operational.
* USB audio: discovered server endpoints participate in manual/automatic
  routing and disconnect fallback. No USB role, recovery gadget, tethering or
  analogue-accessory assumption is changed. Physical digital adapters,
  playback/capture and disconnect recovery await a compatible attached device.
* Bluetooth: reused BlueZ, EtherBluetooth and the installed backend. Existing
  EtherBluetooth route, volume, mute and profile controls now use EtherAudio
  when present, including active-call/recording guards. Only advertised available
  external card profiles are accepted and effective profiles are read back.
  A2DP/HFP/HSP, headset microphones/buttons and codec/volume synchronization
  still need a real connected headset. No HFP capability is inferred from A2DP.
* Routing: persistent manual preferences, Bluetooth/USB preference when no
  manual route is available, speaker fallback, stream moves, verified default
  routes and rollback. Ordinary level events do not reroute displays or devices.
  Active calls protect routes; active recordings prevent microphone/profile
  switching. External display audio policy preserves the current session.
* Application streams: real backend names/roles, volume, mute, destination and
  corked state. Unknown attribution stays unknown. There is no per-app wattage
  or invented hardware-volume category.
* Focus: emergency/call, ringtone, alarm, navigation, notification and media
  priority leases. Real software ducking and cooperative pause/resume events;
  connection-owned cleanup, conditional restoration and recycled-ID guards.
  Exclusive hardware isolation and forced pause of arbitrary apps are unavailable.
* Volume: persistent media/call/ringtone/notification/alarm software categories,
  applied to matching streams. Existing stream levels are preserved at startup.
  Existing Media keys call AdjustVolume for an active call stream or default
  output. No second hardware-key grab was added. Human physical key testing
  and notification audibility remain physical acceptance items.
* Privacy: managed requests require explicit per-action consent, obey a saved
  deny policy, expire after at most 60 seconds and release on client exit/sleep.
  No automatic recording or idle input-level sampling. The global shell status
  and Quick Settings indicate Pulse recording activity, with application/source
  details in Sound settings. Same-user applications can bypass this cooperative
  API via Pulse/ALSA under existing Unix ACLs. Direct ALSA capture cannot be
  attributed here; strong sandbox isolation is not claimed.
* EtherSpeech/EtherSMS: after the user presses dictation, capture uses the new
  bounded raw-PCM helper/API. The existing offline recognition engine remains
  unchanged. Synthetic integration tests verify consent and selected source;
  no live dictation or SMS transmission was performed for this task.
* UI: existing Sound & Notifications now contains Output, Input, Volume,
  Audio Routing, Applications and Advanced. Quick Settings retains its existing
  slider and adds mute, output selection and microphone activity. Advanced
  exposes real ALSA/backend/registry metadata and existing Bluetooth controls.
* Diagnostics: explicit playback/capture controls, manual acoustic result,
  memory-only sample auto-clearing after one minute/shell exit, last 100 metadata
  results only. No recordings are kept by the service or diagnostic history.
* Sleep/resume: EtherPower/logind lifecycle hooks cancel managed recordings,
  release focus and rediscover preferred routes without restarting audio servers.
  Physical suspend/resume remains blocked by EtherPower's unverified bounded
  wake path. No unattended suspend experiment was performed.
* Persistence: atomic schema-1 preferences and diagnostic metadata; actual
  saved-config survival after a service restart passed. The user service is
  enabled and D-Bus activation is installed. Reboot/cold-start acceptance for
  this newly introduced service remains pending manual boot-menu selection.
* Distribution: local ARM64 etheraudio package, source integration, systemd
  user unit, session D-Bus activation, existing-distributor manifest and catalog
  entry. Related EtherShell/EtherSMS/EtherBluetooth/EtherHardware integrations
  are built and installed locally. No second distributor or remote publication.

Validation and measurements
---------------------------

22 backend policy tests pass on Windows, Debian build host and ARM64 phone.
Seven private-D-Bus tests exercise synthetic capture descriptors, caller ownership,
consent denial, duration validation, disconnect cleanup, timeout and cooperative
resume notification after a focus owner's crash. Fake pactl
and parec executables isolate those tests from all real audio PCMs.
EtherSMS Qt tests pass on ARM64 (14 results including setup/cleanup); its new
managed-capture test uses fake executables and cannot record or send an SMS.
EtherBluetooth's central-policy integration test passes on ARM64 (3 results
including setup/cleanup). Existing EtherHardware tests also pass (17 tests).

Actual idle-endpoint controls passed volume/mute readback, invalid-value and
no-consent rejection, call-route blocker, focus ownership/crash cleanup, call
route protection, service-restart preferences and unchanged audio-server PIDs.
No active playback or capture was interrupted to perform those tests.
The measured short 20-second policy-process overhead was approximately 0.05–0.10%
of one CPU core and about 29 MB RSS; see the exact final evidence values.
This does not measure isolated electrical audio power, DSP offload or latency.

The first implementation exposed a D-Bus connection-close deadlock during
periodic capability queries. The worker now retains its private system-bus
connection, matching the existing EtherPower pattern. The new policy service
alone was recovered; no audio server or kernel module was restarted. Subsequent
service-restart, protocol and periodic-refresh checks passed.

The earlier UI pass completed 319 checks per size across four sizes and both
themes. The final UI pass additionally seeds the isolated, write-disabled UI
with an actual device-state snapshot so endpoint rows are exercised. This is
real observed metadata, not fabricated device information. The live user
session screenshot is separate from isolated UI evidence. Full physical audio,
AR transmission, Bluetooth/USB hotplug, real calls and suspend are not inferred
from screenshots, synthetic tests or active service state.

Evidence and recovery
---------------------

* evidence/etheraudio-audit-2026-10-20.json — read-only original hardware audit.
* evidence/etheraudio-install.json — installed package hash, actual ARM64 tests,
  routes and unchanged server/service PIDs.
* evidence/etheraudio-device-tests.json — reversible control tests and overhead.
* evidence/etheraudio-protocol-tests.txt — synthetic private-bus capture tests.
* evidence/etheraudio-ethersms-tests.txt and
  evidence/etheraudio-bluetooth-policy-tests.txt — actual ARM64 app tests.
* evidence/etheraudio-settings-device/ — four-size UI results/screenshots.
* evidence/etheraudio-shell-stage.json and etheraudio-shell-deployment.json —
  exact package staging, validation and launcher rollback path.
* evidence/etheraudio-live.png — actual user-session screen.
* evidence/etheraudio-button-tests.json and etheraudio-quick.png — existing
  key-owner dispatch and actual Quick Settings.
* evidence/etheraudio-final-regression.json — final enabled state, installed
  source/package hashes, periodic refresh and service/connectivity checks.

To stop only this policy layer use systemctl --user disable --now etheraudio.
Its orderly shutdown restores unchanged ducked stream levels and stops managed
captures. The existing PipeWire/WirePlumber/UCM stack continues to own audio.
The shell deployment record identifies the preserved prior launcher and binary.
Do not unload downstream audio drivers or fabricate a wake-validation record.
