EtherAudio
==========

EtherAudio adds session audio policy to the working PipeWire 1.4.2,
pipewire-pulse and WirePlumber stack. It does not replace these servers,
reload Qualcomm modules, change DSP calibration, or write mixer gains.
Existing UCM2 Speaker/HandsetMic routes remain owned by WirePlumber/ALSA.
Media retains the sole X11 volume-key listener and on-screen volume feedback.

Audit and reuse
---------------

The 2026-10-20 read-only audit identifies sm8150-tavil-snd-card by ALSA ID,
not by assuming card 0. The machine driver is sm8150-asoc-snd, codec
WCD934x/Tavil with two TFA9874 amplifiers. Earlier speaker playback was
confirmed by the user (docs/audio-2026-10-16.rst). The OEM-derived, already
installed UCM microphone route uses AMIC3/ADC3 through DEC0/SLIM_0_TX.
No routing definition is copied from Android during EtherAudio installation.
Existing firmware and calibration are preserved. The downstream drivers have
unsafe unload behavior; never unload/reload them as a recovery strategy.

The audit captures ALSA PCM/mixer metadata, actual endpoints, backend cards and
profiles and service ownership in evidence/etheraudio-audit-2026-10-20.json.
No acoustic playback or microphone test is initiated by an audit or installer.

API version 1
-------------

Session bus/interface com.etherneco.EtherAudio1, object
/com/etherneco/EtherAudio1. GetState() returns cached JSON. Changed(s JSON)
publishes effective endpoints, playback/capture streams, backend-provided
application attribution, software volumes, mute, focus and policy evidence.
Refresh() requests a coalesced refresh. Backend topology is event-driven via
pactl subscribe with a 60-second fallback and subscription recovery.

Command(s action,s target,s JSON) is asynchronous and returns a string.
Actions include select (target sink/source, name), volume (endpoint or stream
kind, id/percent), mute (kind, id/muted), move (stream/sink), configure (partial
preferences), category (name, percent), focus (priority), release-focus (token),
card-profile (card name, advertised available profile),
result (diagnostic kind, result), and play-test (sink name, consent=true).
All target IDs are checked against current inventory; no arbitrary shell or
sysfs path is accepted. Effective volume/mute/default/stream routes are read
back. Failed route changes restore prior stream/default routes and report
rollback failure. Preferences use atomic, fsynced schema-1 JSON.

Focus priorities: emergency/call, ringtone, alarm, navigation, notification,
media. Lower-priority streams are ducked through real software stream volumes.
FocusChanged events invite cooperative pause/resume. A client must tag its
streams with the appropriate backend media.role (phone for calls). Leases
belong to the requesting D-Bus connection and are released on disconnect.
Restoration respects changed volume and recycled stream IDs. Exclusive device
isolation and forced pause of arbitrary applications are not claimed.
AdjustVolume(i delta) adjusts an active call stream or the default output.
Only the existing Media input owner invokes it; no second key grab is installed.

Categories media/call/ringtone/notification/alarm map to software stream roles,
not independent hardware controls. Existing stream levels are preserved at
service startup. Category edits affect matching current streams, and saved
levels are applied to new streams. Unknown media roles use the media category;
unknown application names remain unknown.

Capture and privacy
-------------------

StartCapture(s source,s purpose,b consent,u seconds) returns (s token,h fd).
The file descriptor streams mono 16-kHz S16LE PCM. The source must be a real
microphone; speaker monitors are rejected. Requests require per-action consent,
are limited to 60 seconds and four concurrent leases, and obey the persisted
deny/ask-each-time policy. StopCapture(s token) checks the requesting connection.
Client disconnect, timeout and suspend stop capture. Resume never restarts it.
The service stores no recordings. The session API is same-user cooperative
policy: the consent assertion comes from the calling application, not a
trusted sandbox prompt. Native same-UID applications can bypass it through
Pulse or ALSA under existing Unix ACLs. No strong microphone isolation is
claimed or granted. No root/PolicyKit action is needed for session controls.

EtherSpeech/EtherSMS uses ``etheraudio capture --consent --seconds 60`` after
the user presses dictation. PCM continues to the existing offline recognizer;
speech recognition is not duplicated. The helper keeps its D-Bus connection
alive for the lease. No automatic capture or level monitoring is used at idle.
Settings requires confirmation for its three-second diagnostic. It can play
and clear the private sample held only in memory; automatic clearing occurs
after one minute or shell exit. No diagnostic recording file is created,
including on a shell crash. Diagnostic history retains only the last 100 metadata results.
MicrophoneActivity events and Settings/Quick Settings show recording activity
and backend-reported applications, including unmanaged Pulse recordings.
Direct ALSA recordings outside the audio server cannot be attributed by this API.

Routing, calls and resume
------------------------

Manual endpoint selection persists and protects that choice while available.
Otherwise automatic output selection prefers exposed Bluetooth and USB audio,
then the existing Speaker endpoint. Disconnect falls back to available output.
Changing output moves current media streams and verifies the result. Live
capture prevents microphone switching. Calls protect output/stream routing.
Clearing preferences restores automatic selection. External display events
preserve audio; USB roles, tethering and recovery gadgets are never modified.
WirePlumber remains responsible for Bluetooth profiles/codecs and hotplug.
Profile selection is available through the existing EtherBluetooth controls;
when EtherAudio is installed, these controls use its same route/call/capture
guards rather than changing endpoints independently. Bluetooth/USB profiles
are checked against advertised availability, read back and rolled back on
failure. Internal codec profiles are not changed through this API.
EtherAudio lists actual advertised backend profiles rather than inventing HFP.

call-route exposes a specific blocker to EtherPhone: Qualcomm modem voice
session control, earpiece routing and a real cellular call are unvalidated.
Speaker/microphone and A2DP do not prove cellular/HFP voice audio. Earpiece,
USB analogue accessory mode, Bluetooth microphone and external devices require
physical acceptance. No unsupported modem mixer values are written.

EtherPower events and logind PrepareForSleep release managed capture and focus;
resume rediscovery restores available preferred endpoints without restarting
working audio servers. Physical suspend/resume remains blocked by EtherPower's
unverified bounded wake path. An API lifecycle test cannot certify actual resume.

Build and use
-------------

Run python3 -m unittest discover -s etheraudio/tests -v, then
cmake -S etheraudio -B /tmp/etheraudio-package -DCMAKE_INSTALL_PREFIX=/usr and
cmake --build /tmp/etheraudio-package --target package. The ARM64 package uses
the existing distributor manifest; no new package manager is introduced.
After installation enable etheraudio.service in the desktop user's systemd
session (systemctl --user enable --now etheraudio). D-Bus activation is also
available. Installation does not restart PipeWire, WirePlumber or kernel audio.
Rebuild EtherShell for Sound & Notifications and Quick Settings integration.
Use etheraudio state or etheraudio command for diagnostics. Service logs are
in journalctl --user -u etheraudio. Settings do not promise physical hardware
verification until the user confirms the interactive test result.
