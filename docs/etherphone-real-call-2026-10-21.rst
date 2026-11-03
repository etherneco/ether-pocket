EtherPhone real call and voice audio diagnosis — 2026-10-21
=========================================================

An outgoing non-emergency call reached Ringing and Active on the real modem.
The recipient confirmed answering, but reported absent or one-way audio.
History contains 98 seconds of observed Active time. Two-way audio and VoLTE
are NOT verified; this is not a completed working cellular telephony release.
The call ended before the final check; no calls remained. The service's first
hangup request was Busy, so successful local hangup is not claimed.

This updates the historical October 20 feasibility/delivery reports. On this
boot, exact existing vendor IPA runtime initialization restored rmnet_ipa0,
ModemManager discovery, LTE home registration and the real Voice interface.
No modem firmware or Android partition was written. The one-shot runtime
initialization is not proof of automatic recovery after a future reboot.

SIM readiness correction
------------------------

The enabled modem reports secondary SIM lock PIN2. EtherPhone incorrectly
treated every non-NONE unlock value as an unavailable SIM. The provider now
accepts NONE, PIN2 and PUK2 for a present SIM on an enabled modem, while still
rejecting primary PIN/PUK, unknown locks and locked/unavailable modem states.
It never submits a PIN2 or changes fixed-dialling restrictions. Policy tests
cover these cases. Only the provider file was replaced on the handset, with
an adjacent backup, followed by an idle EtherPhone service restart.
The ARM64 Debian package was rebuilt with the source fix; the full package
was not reinstalled over other ongoing component changes.

Audio findings
--------------

During the answered call, every ALSA substream was closed, including dedicated
VoiceMMode1 playback and capture (card0 device2). ModemManager exposed an empty
AudioPort and AudioFormat. EtherAudio still correctly gates native call audio.

The installed downstream driver's msm-pcm-voice-v2.c starts the voice session
when both dedicated streams are prepared; START/STOP triggers do not start
voice. A bounded offline probe selected the OEM voicemmode1-call quat_i2s
RX/TX mixer switches, reused the verified speaker/ADC3 backend configuration,
and prepared both dedicated streams at S16_LE mono 16 kHz. No media samples
were written, microphone samples recorded, or further number dialled.

Both streams reached PREPARED, but kernel logs reported missing voice
calibration blocks 7 (stream), 4 (device configuration), 2 (vocproc) and 3
(volume). The DSP rejected the voice volume command with ADSP_EFAILED.
The ALSA driver's prepare callback ignores voc_start_voice_call's return
value, so ALSA success alone cannot establish a working DSP voice session.
Both streams were closed and the original two mixer values were restored.
No calibration data, firmware, audio modules or persisted routes were changed.

Factory ACDB files exist on vendor_b, and its libacdbloader.so exports voice
calibration entry points. ELF inspection, without loading the library, shows
Android libc, HIDL, Binder, OnePlus param and other vendor dependencies.
Debian has /dev/msm_audio_cal but no installed ACDB loader. Copying this one
library into Debian cannot supply its runtime dependencies or select correct
device/session calibration. A compatible loader/runtime and verified ACDB
device mapping are the next implementation dependency; no guessed calibration
or radio NV writes were attempted. The observed missing calibration is a
concrete additional blocker, not proof that it is the only remaining issue.

Evidence and reproduction
-------------------------

Redacted evidence is under evidence/etherphone-*-2026-10-21.json, particularly:

* call-attempt: observed Dialling and Ringing after one dial submission.
* real-call and test-call-ended: Active, closed audio streams, history and
  zero remaining calls. Recipient feedback is recorded above.
* voice-pcm-probe: ALSA operations, mixer restoration and DSP error messages.
* audio-calibration-audit and acdb-loader-abi: read-only factory-file and ELF
  dependency inspection; no vendor binaries are redistributed.
* pin2-fix: backup/deployment hashes and observed ready state.

scripts/probe-etherphone-voice-audio.py is an explicitly mutating, reversible
offline engineering probe. It refuses live calls, busy PCM streams, a different
board/card or a changed speaker/mic backend. It temporarily enables only two
voice route switches, closes its handles and restores both original values.
It does not verify real call audio. It is not installed as a production route
and is not run automatically by EtherPhone.

Incoming physical-call audio, earpiece, speakerphone controls, mute, Bluetooth
HFP, screen-off wake, IMS registration, VoLTE and emergency calling remain
unverified. Further silent calls do not resolve the missing loader dependency.
