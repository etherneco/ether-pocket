EtherPhone feasibility audit — 2026-10-20
=======================================

Phase 0 completed before implementation. Evidence is
evidence/etherphone-audit-2026-10-20.json, collected over pinned USB SSH.
The actual board is GM1920, device-tree SDX50M MTP 18827 15, rather than
an assumed LTE-only OnePlus 7 Pro. Debian's existing ModemManager 1.24.0,
NetworkManager, EtherHardware, EtherPower and EtherAudio are reused.
oFono is absent and is not installed. No firmware, NV, carrier configuration,
Android partition, modem-manager ownership or network state was changed.

============================ =================== =====================================
Capability                   Assessment          Evidence / blocker
============================ =================== =====================================
Modem detected               Partially supported QRTR node 0 responds; MM exports none
SIM detected                 Supported           UIM USIM ready, PIN1 disabled
Network registered           Blocked             NAS not-registered; CS/PS detached
Voice control available      Partially supported QMI call enumeration works; no MM Voice
IMS registration available   Blocked             IMSA query returns InvalidOperation 70
VoLTE call control available Blocked             No usable IMS/control/audio combination
Voice audio routing          Blocked             EtherAudio callAudio.operational false
Incoming call indication     Not tested          No exported MM modem/call; no live call
Real call verified           Not tested          No call placed; no two-way audio test
============================ =================== =====================================

Current MM journal reports 'Failed to find a net port in the QMI modem'.
NetworkManager sees Wi-Fi but no rmnet_ipa0. This differs from the earlier
one-shot IPA initialization; its previous success is historical evidence,
not current availability. Restoring cellular data/startup is a separate
prerequisite and is not attempted by this audit.

Follow-up read-only libqmi GI Voice Get All Call Info succeeds with zero calls;
see evidence/etherphone-voice-query.json and scripts/probe-etherphone-voice.py.
Thus supported-message discovery failure is not evidence that the entire Voice
service is unusable. Enumeration is partially supported; initiation, answering,
indications and audio are still unverified. It does not provide a tested
alternative modem owner or establish VoLTE. No caller numbers were exported.

QRTR advertises Voice service 9 version 2, IMS settings 18, IMS application
33 and IMS private 77. Advertisement does not establish host call control or
registration. Voice Get Supported Messages fails InvalidQmiCommand 71.
Both IMSA registration and service status queries fail InvalidOperation 70.
No IMSA binding, provisioning or configuration writes were attempted.
These errors do not prove the firmware lacks IMS; binding/control ownership,
carrier provisioning and vendor userspace dependencies remain unresolved.
No native IMS owner is visible among system bus names. Android IMS ownership
cannot be deduced from Debian bus names. No working SIP/IMS registration,
carrier support, IMS APN or lawful compatible native IMS stack is established.

EtherAudio reports an unvalidated Qualcomm modem voice session and no native
earpiece UCM path. UCM profiles for other boards are installed; they are not
evidence of compatibility with this downstream sm8150-asoc-snd driver.
Media playback/capture and Bluetooth controller availability do not establish
DSP voice routing, HFP bidirectional audio or any call route.

Implementation decision
-----------------------

Proceed with independent contacts/history/dialer/diagnostics and an adapter
to the existing ModemManager Voice API. No second modem manager, guessed
QMI dial commands or media-to-modem PCM routing. Exposed controls must derive
from backend observations, and command submission never means Active.
IMS stays unknown/unavailable until a real compatible provider reports it.
Hold/conference, DSP routes, ringtone/haptics and lock-screen wake remain
gated where there is no verified integration. A regular session service
cannot promise delivery during suspend; bounded modem wake is unverified.

Emergency calling is unverified. EtherPocket must not be relied on as the
sole emergency telephone; preserve a known-working phone. No emergency test
call is authorized or performed. Physical outgoing/incoming non-emergency,
screen-off wake and two-way audio acceptance require a consenting recipient
and restored, verified modem/network/audio prerequisites.

API references used for the adapter
-----------------------------------

* https://www.freedesktop.org/software/ModemManager/doc/latest/ModemManager/gdbus-org.freedesktop.ModemManager1.Modem.Voice.html
* https://www.freedesktop.org/software/ModemManager/doc/latest/ModemManager/gdbus-org.freedesktop.ModemManager1.Call.html
* https://www.freedesktop.org/software/libqmi/libqmi-glib/1.38.0/index.html

The Voice API requires a ready modem and (for 3GPP) an unlocked SIM.
Its Call objects and state indications are the source of call state.
The libqmi API exposes IMSA queries; library availability alone is not a
working native IMS implementation for this device.
