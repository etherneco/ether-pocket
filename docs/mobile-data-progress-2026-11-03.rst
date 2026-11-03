Mobile data controls and visible failure reasons, 2026-11-03
==========================================================

Observed cause
--------------

The handset's IPA service was active and had a real epcell0 address and default
route. Interface-bound HTTPS returned 200. The UI still used the stock
NetworkManager/ModemManager bearer path and showed disconnected, because the
separate WDS owner is not an MM connected bearer. Current MM logs repeatedly
reported ``Unsupported QMI kernel driver for 'net/rmnet_ipa0': (null)``.
One saved giffgaff profile also had NM autoconnect enabled, causing repeated
incompatible attempts. Its autoconnect was disabled after preserving complete
keyfiles in a root-only backup. The existing IPA boot service stays enabled.

Changes
-------

The shared EtherMobile backend detects the actual rmnet_ipa0 control port and
uses systemd StartUnit/StopUnit for ethermobile-data.service. Other modems retain
the NM path. PolicyKit allows the existing desktop account to start/stop/restart
only that exact service, without permissions over other units. APN editing
and secrets remain under NM ownership. The IPA adapter remains configured for
giffgaff.com/IPv4, with roaming blocked; the UI explains this and rejects other
APNs and IPv6-only activation instead of silently using a different profile.

The startup helper and WDS adapter atomically publish a schema/boot-scoped,
readable status file at /run/ethermobile-data-status.json. It contains stage,
message, code, safe details, timestamps, at most twenty history entries and
observed connection metadata. It never contains credentials, subscriber IDs,
raw command errors or QMI requests. The private existing owner state stays
root-only. Successful service state is checked against MainPID and the actual
epcell0 interface before the UI claims a data session.

Progress covers modem/SIM, registration, packet attach, competing NM ownership,
QRTR, DPM, QMAP, hardware pipes, WDS, APN session, IP and DNS. Failed stages
remain visible after cleanup; SIM PIN/PUK, roaming, registration denial,
timeouts, QMI errors and carrier call-end numeric reasons have safe messages.
ExecStopPost supplies a failure for systemd termination/timeouts. Normal stop
clears connected status. No automatic retry loop is added.

Mobile Settings shows a prominent progress/error card, spinner, elapsed time
and expandable history. Local validation/permission errors also appear there.
The standalone app has the same service status and the quick toggle shares
the real IPA state. Interface accounting uses the observed IPA interface.
Session establishment still does not itself certify internet reachability.

Verification and deployment
---------------------------

Ten Python tests passed: stage history, limits, stale boot rejection, redaction,
QMI numeric details, cleanup preservation, systemd timeout, locked SIM,
competing owner timeout and roaming refusal. ARM64 builds passed. The real
unprivileged backend client stopped and restarted the service through the same
methods as the UI; state changes and successful completion were observed.
HTTPS bound to epcell0 returned 200 afterwards.

On-device isolated QML acceptance passed at 420x1000 and 1000x600 in light and
dark themes, including a real invalid-profile validation error displayed in
the progress card. No malformed test APN was saved or sent to the carrier.
Evidence is in mobile-data-progress-final-qa.json, the final connect/disconnect
JSONL files and the deployment report under evidence/.

Use scripts/deploy-mobile-data-progress.py stage, verify the staged UI, then
activate to clone the exact current shell stage and switch the launcher with
rollback on startup failure. Original backend files, keyfiles and shell
launcher are retained. Android, kernel and firmware are not changed.
This repair was tested by a service stop/start, without a further reboot.
