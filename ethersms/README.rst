EtherSMS 0.1.0
==============

Native Qt 6/QML application using the existing EtherMobile ModemManager backend.
No AT commands, direct QMI manager, synthetic production messages or radio changes.
Initial release: live SMS, microphone routing, recognition quality and display
acceptance require the device validation described in docs/ethersms-2026-10-19.rst.

Build with CMake/Ninja and Qt6 Core/Gui/Qml/Quick/QuickControls2/DBus/Network/Sql.
Run CTest for the isolated repository, controller and encoding suite.
Debian package: cpack -G DEB. Models are never bundled or automatically downloaded. Downloads require an
explicit confirmation and a trusted publisher SHA-256.

Settings live in EtherShell: Network & Internet -> SMS & Messaging. Rebuild
EtherShell to install the integration. EtherKeyboard is the existing shell
keyboard; focus text fields and use its dock toggle. No new keyboard is installed.

Dictation uses parec (PulseAudio or PipeWire compatibility server), at most 60s
of 16-kHz mono capture, followed by an offline whisper-cli subprocess, four CPU
threads and a five-minute timeout. Install whisper-cli separately, then import a
multilingual tiny/base/small GGML model with its publisher SHA-256 in Settings.
English-only .en models are rejected. No remote speech service is used. Speaker monitors are explicitly rejected.
Recognition is limited to 3 GiB address space and five minutes of CPU time.

Message history: ~/.local/share/Etherneco/EtherSMS/messages.sqlite, mode 0600.
Config: ~/.config/Etherneco/EtherSMS.conf. Backups use SQLite VACUUM INTO and
refuse to overwrite files. To recover: stop EtherSMS, preserve the original DB,
check the backup with sqlite3 'PRAGMA integrity_check', then restore it with mode
0600. Backups contain private SMS content and contacts. No database encryption
is claimed. Deleted incoming-message fingerprints prevent modem rescans from
resurrecting deleted local messages. History loads in pages of 200 messages. More recent database schemas are refused; migrations are transactional.

Submitted to network never means Delivered. Uncertain sends are never retried
automatically. Verify with the recipient before creating another send. Ten SMS
segments per send is the UI limit. ModemManager handles actual encoding,
segmentation and incoming multipart assembly. Delivery reports currently
correlate only with sends observed during the current modem-service session.
Unmatched or ambiguous reports never produce Delivered. Estimates count GSM extension
characters and UTF-16 surrogate pairs. Sender IDs are shown as received; outgoing
numbers accept explicit digits and optional + without inventing a country code.

Local AI uses only http://127.0.0.1:11434/api/generate, no redirects. Enable it
explicitly and choose an installed Ollama model. Original and suggested text are
reviewed before acceptance. Neither recognition nor AI sends messages.

Read aloud requires optional eSpeak NG and paplay. Playback is explicit. The app
must remain running for incoming storage, notifications and dock unread updates;
there is no independent modem daemon or automatic startup added.

EtherPocket integration update
------------------------------

On the physical GM1920 the owner confirmed real SMS receipt. A board-specific
Messaging-only polkit rule bridges the existing launcher outside logind's seat.
The exact rule and OEM microphone UCM configuration are supplied under
/usr/share/ethersms/integration for review, not automatically applied on arbitrary
Linux devices. The existing device audio installer consumes config/audio/HiFi.conf.
The microphone route must be set before the downstream PCM capability probe;
the updated HiFi verb does this without starting a capture stream. The speaker
route is preserved. Microphone idle state was verified SUSPENDED with PCM closed.

A checksum-verified multilingual base model is now installed on the test phone.
English human audio (11 s) transcribed in 6.12 s at about 283 MiB peak RSS.
The Polish synthetic fixture contained recognition errors; real dictation quality
still needs a microphone test. Incoming reply validation remains pending.
