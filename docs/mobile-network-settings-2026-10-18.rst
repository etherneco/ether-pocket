EtherShell Mobile Network Settings — 2026-10-18
==============================================

Scope and baseline
------------------

EtherShell 2.0.2 integrates Mobile Network inside its existing Settings >
Network & Internet navigation, EtherControl/Quick Settings, status header and
EtherDock SIM shortcut. Both shell presentations embed the same QML component;
there is no additional Settings application. EtherMobile 0.1.1 and EtherShell
link the same ethermobile-core implementation. Existing ModemManager and
NetworkManager remain the only modem/connection managers.

The physical phone is GM1920, with a QRTR Qualcomm qcom-soc modem and the
previously initialized rmnet_ipa0 packet interface. Its inserted giffgaff USIM
reports O2 UK as its home network. Registration is searching and packet service
is detached. Cellular internet remains unverified. Recent SIM activation is
only a possible explanation for registration rejection. The observed SDX50M
variant differs from the task's LTE-only hardware assumption. No functional NR
mode selector is provided, and firmware capability is not connectivity proof.

Before editing, Experience.qml and TouchAction.qml contained diagnostic JSON
instead of QML. Their exact working UI was recovered from the existing build's
compiled Qt resource, whose bytes match the active ARM64 binary. Corrupt files
are retained under evidence/ethershell-qml-recovery. The recovery utility is
scripts/extract-shell-qml.cpp. This preserves the existing visual design and
software blanking implementation.

Sources of truth and state
--------------------------

* NetworkManager Settings.Connection: saved GSM profiles, APN/authentication,
  secrets, IP families, DNS, default route, metric, priority, autoconnect and
  home-only policy. No Wi-Fi profile is modified.
* ModemManager ObjectManager and separate SIM Properties.GetAll: effective
  modem/SIM/registration/mode/bearer state. SIM objects are not assumed to be
  included in the modem ObjectManager response. Only operator, active flag and
  operator identifier are retained from SIM properties; IMSI/ICCID/MSISDN are
  never exposed in these pages.
* NetworkManager Device and ActiveConnection: activation, active profile and
  observed IPv4/IPv6 addresses, gateways, DNS and routes. Old IP evidence is
  cleared when the active connection changes.
* Core preferences: selected profile UUID, selected Settings section and last
  requested operator/mode. These are UI/request preferences, not competing
  modem configuration and are never automatically applied at startup.
* Real cellular interface sysfs byte counters: local observed usage history.

D-Bus calls are asynchronous and observe PropertiesChanged, profile changes,
ObjectManager changes and service-owner changes. Missing services clear stale
live state. A modem without registration/IP cannot become Connected. Connected
requires a connected MM bearer, MM connected state, NM activation and observed
IP. Internet remains explicitly Not verified; opening Settings causes no
connectivity probe, scan, registration request, radio change or IPA startup.

Profile workflow
----------------

The editor supports add, edit, duplicate, version-checked delete, explicit
activation/reconnect, credential replacement, automatic/PAP/CHAP authentication,
IPv4/IPv6/dual stack, autoconnect, roaming, default route, priority, metric and
family-specific DNS. Profiles from other applications remain accessible;
duplicate creates a fresh UUID and never overwrites its source.

An edit reads VersionId/GetSettings/VersionId for a stable draft. On save it
checks the draft revision, preserves credentials through NM GetSecrets, checks
public configuration again and uses Update2 with version-id and to-disk plus
no-reapply flags. NM can bump VersionId while resolving secrets; the code uses
the final post-secret revision rather than bypassing version checks. Read-back
compares public fields, verifies stored credentials without displaying them,
and captures the final revision. Saved does not mean that an existing data
session was reconfigured. Timeouts report uncertainty and require reopening
before retrying.

Rollback retains the previous profile, including protected secrets, only in
process memory. It refuses restoration when the post-write revision has changed.
Radio and connection rollback similarly check effective mode/profile revision
and current connection state. Deletion checks the displayed revision immediately
before Delete and verifies disappearance. NM Delete does not accept an atomic
version argument: a competing edit in the final check/delete interval cannot be
excluded. The separately confirmed Clear stored secrets action has the same
API limitation. It is limited to disconnected plain GSM profiles, preserves
the previous credentials for guarded rollback and verifies absence via
GetSecrets; additional setting groups are refused to avoid clearing unrelated
credentials. Empty password replacement is refused on existing profiles;
users clear secrets explicitly. Empty usernames are omitted as NM requires.
Cross-client secret-only changes during GetSecrets also have public
API snapshot limits. No application-level migration rewrites existing profiles.
Custom static IP profiles are refused by the automatic IP editor to preserve
unrepresented configuration. There is no unverified provider-default adapter.

New profiles default to autoconnect off, roaming blocked, default route off,
one autoconnect retry and metric 900. Switching an active profile, scans,
registration/mode requests, SIM operations and charge-relevant policies require
explicit UI confirmation. Roaming now and saved roaming permission are separate.
Unsaved APN drafts remain open across section navigation and require explicit
discard. Fields request the existing EtherShell touch keyboard.

SIM, radio and diagnostics
--------------------------

PIN entry, PIN lock enable/disable, PIN change and PUK unlock use the matching
ModemManager SIM methods once, without guessing or retries. PIN2 is not treated
as an ordinary PIN1 lock. Retry counts appear only for the required PIN/PUK
when actually exposed. Codes are cleared from fields after submission/closure;
Qt strings do not guarantee physical memory zeroization. Multiple-slot selection
is enabled only when multiple usable SIM objects are exposed.

Manual scan displays only returned 3GPP operators; registration accepts an
explicit scanned, non-forbidden operator or automatic selection. Network modes
are generated from backend-supported allowed/preferred pairs with NR selectors
excluded. Requested preferences and effective mode are displayed separately.
Mode retention across reboot is not asserted or implemented by replaying UI
preferences. Advanced Settings shows exposed ports/protocols, drivers, firmware,
power, modes, IP details and available signal metrics. Unavailable metrics stay
unavailable. Doctor remains a fixed, read-only diagnostic allowlist.

Usage and security
-------------------

Usage samples only the selected cellular device's real active IpInterface,
never wlan0. A shared QLockFile and QSaveFile history at
~/.local/share/ethermobile/usage.json avoids counting the same interface delta
twice when both frontends run. Baselines include boot/interface identity,
counter values, day and time. Reboots, decreasing/wrapped counters, day changes,
clock reversal and sampling gaps over 65 seconds start a new baseline; missing
traffic is excluded rather than assigned to an invented billing interval.
Session/daily/billing-cycle download/upload totals and an optional warning are
local estimates, not carrier billing. Billing days are clamped to month length.
Warnings never disconnect data. There is no hard usage-limit control.

The GUI runs as mobian, not root. Interactive D-Bus authorization uses existing
NetworkManager/ModemManager PolicyKit policies and the session's existing agent.
No new privileged helper, broad allow rule, arbitrary shell/modem command,
daemon restart or firmware/calibration write is added. APN passwords remain
under NM secrets storage, not Core preferences or logs. Diagnostics/errors
expose safe fields and error names, not raw credential-bearing messages.

Build and acceptance
---------------------

Build the normal ethermobile and ethershell CMake projects; both include
ethermobile/Core.cmake. ARM64 packages are build/ethermobile_0.1.1_arm64.deb and
build/ethershell_2.0.2_arm64.deb. The shell requires EtherMobile >= 0.1.1 for its
Doctor and NetworkManager >= 1.44; stable VersionId is runtime-gated.

scripts/test-ethermobile-configuration-device.py runs the real ARM64 backend
against actual NM: create/read-back, PAP and IPv4/IPv6 DNS, credentials preserved,
edit/rollback, external-change refusal, fresh-instance persistence, duplicate,
secret clearing, IPv6-only save/read-back, delete and unsupported NR mode
rejection. Fixtures use reserved .invalid APNs,
autoconnect off/default route off and are never activated. It also verifies
unprivileged denial without an agent and unchanged active connections. Evidence:
evidence/ethermobile-configuration-2026-10-18.json.

scripts/test-ethermobile-device.py covers existing standalone profile workflows,
state/technology/APN policy, usage counter resets/billing boundaries, permission
denial and three standalone renders. Evidence:
evidence/ethermobile-acceptance-2026-10-18.json.

scripts/test-ethershell-mobile-ui.py renders the real shared module with the
real system D-Bus as an unprivileged user on a private, authenticated Xvfb server.
It isolates app preferences, usage data, session bus and runtime sockets. It
checks Settings navigation, all nine pages in both themes, Quick Settings state,
the APN editor and draft retention. Device acceptance also checks real modem,
SIM readiness/operator and persistent profiles. Portrait 480x1000, landscape
1000x600 and external-size 1920x1080 evidence is under
evidence/ethershell-mobile-device. Host tests cover modem-unavailable rendering.
External-size rendering does not prove EtherAir transport or physical touch.

Deployment and remaining hardware acceptance
--------------------------------------------

scripts/deploy-mobile-settings.py stages the new shell beside the verified
working stage, renders it first and optionally switches the existing user
launcher with --activate. It preserves ETHERSHELL_SOFT_BLANK=1, the old stage,
XFCE/xfwm4 and the launcher backup
/home/mobian/.local/bin/ethershell2-start.before-mobile-settings. A failed startup
restores the old launcher automatically. Machine-readable stage/deployment
records are in evidence/mobile-settings-stage.json and
evidence/mobile-settings-deployment.json. No shared network service is restarted.

The deployed stage is /opt/ethershell2/2.0.2-mobile-e3e469e6a8eb; its binary
SHA-256 is caa0ce1f1c174aa8a6910e25f54c80a9f292745fda66826ac7244cbd62283ca0.
The previous stage and launcher remain available. EtherMobile 0.1.1 is installed
through dpkg. EtherShell is switched through the existing side-by-side user
launcher; the system's older ethershell package is deliberately retained.
scripts/verify-mobile-settings-device.py confirms the running UID/stage/hash,
soft blanking, normal navigation to the integrated Mobile page, active NM/MM/
SSH/Bluetooth/modem services, connected wlan0, powered hci0 and running Xfwm4.
Evidence: evidence/mobile-settings-regression.json. These are state checks,
not Bluetooth pairing, touch interaction or an EtherAir transmission test.

API references:
https://www.networkmanager.dev/docs/api/latest/gdbus-org.freedesktop.NetworkManager.Settings.Connection.html
and https://www.freedesktop.org/software/ModemManager/api/latest/.

After explicit user approval, a real system reboot and one IPA initialization
were performed. A changed boot ID confirms the reboot. The existing persistent
GSM keyfile (including NM-owned credentials), launcher, binary and all ten
firmware files have identical pre/post SHA-256 values. No explicit mobile UI
request preferences had been set before this reboot; their empty-state hash
matches, which is not evidence of modem-mode persistence. SSH returned, the
normal-user shell autostarted from the deployed stage, Wi-Fi reconnected,
Bluetooth remained powered and Xfwm4 ran normally. The manual one-shot IPA
startup loaded successfully; rmnet_ipa0 appeared asynchronously, followed by
the MM modem at a new object path. The giffgaff SIM is readable and ready;
registration remains searching, packet service detached, without a data bearer.
All 29 portrait UI/SIM/profile checks passed again after reboot. Evidence:
evidence/mobile-settings-reboot-before.json,
evidence/mobile-settings-reboot-after.json,
evidence/mobile-settings-reboot-comparison.json and
evidence/mobile-settings-reboot-ui/portrait/results.json. Reproduction uses
scripts/test-mobile-settings-reboot.py; its reboot action requires explicit
authorization and does not automatically initialize IPA.

Acceptance does not include cellular data activation, DNS/internet over cellular,
successful LTE registration, PIN/PUK changes, actual scans/mode changes,
SIM switching, metered traffic accounting, physical touch/EtherAir transport,
suspend/resume. Service-stop failures are handled in code but were not
induced on the shared phone. A normal-user PolicyKit denial is tested; successful
interactive approval still requires the real desktop agent/user interaction.
NM disk persistence, fresh-backend/application/shell reads and the existing APN's
system reboot persistence are verified. IPA startup remains one-shot/manual;
automatic packet-path startup at boot is not implemented or certified. Further
reboots or repeated IPA initialization require fresh authorization. The full
task's hardware Definition of Done still awaits the remaining checks above.
