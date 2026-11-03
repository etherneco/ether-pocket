EtherNotifications engineering release
======================================

Architecture and migration
--------------------------

EtherShell previously owned org.freedesktop.Notifications inside its graphical
process and retained only 50 in-memory cards. EtherSMS and EtherPhone already use
the standard bus API. No second desktop daemon was observed in the device audit
on 20 October 2026. The new unprivileged service owns that name and the extension
com.etherneco.EtherNotifications1 at /com/etherneco/EtherNotifications1.
Both names are acquired without queuing, replacement or takeover. Exit 73 means
another daemon owns the name. No installation hook stops an existing owner.

Upgrade the shell and service together: stage and test the replacement shell,
stop the old graphical notification owner, start ethernotifications, then launch
the replacement shell. Keep the previous launcher for rollback. Do not start a
second daemon under a different bus name as a workaround. The package includes
activation files and a systemd user unit; enable the unit only during coordinated
migration. Disable the new unit and restore the prior shell to roll back.

The persistent SQLite store lives in $STATE_DIRECTORY/history.sqlite when
systemd supplies that directory, otherwise
$XDG_STATE_HOME/ethernotifications/history.sqlite (default ~/.local/state).
Directory mode 0700, database mode 0600, umask 0077, secure deletion and bounded
retention apply. Sensitive previews remain only in memory; their durable records
contain a generic title and no body/conversation. Secret/transient notifications
are not stored. Already-written public data cannot be retroactively protected by
changing an application's subsequent privacy hints; delete its history instead.

Standard API and extensions
---------------------------

Notify(susssasa{sv}i)->u, CloseNotification(u), GetCapabilities()->as and
GetServerInformation()->ssss implement the freedesktop 1.2 interface. Advertised
capabilities: body, actions, persistence. No markup, arbitrary image data,
hyperlinks, inline reply or sound capability is advertised. The UI always uses
plain text. Only safe theme icon names are accepted; local paths and URLs are
discarded. NotificationClosed(uu) uses reasons 1 expiration, 2 user/action close,
3 application close, 4 policy-disabled. Disabled apps create inactive history
only and never appear in the current center. ActionInvoked(us) and close signals are directed to the
original unique sender. Default action keys require registration in Notify.
Resident notifications survive actions and bulk clear, but may be individually
dismissed or expired. Timeout -1 is 8 seconds, 0 never expires, positive values
are milliseconds up to one day. Expired/dismissed records remain in History.

Extension GetState()->s returns JSON only to the verified installed EtherShell.
Changed() contains no content. Banner(u) carries an ID only. Command(sus)->s
accepts an action, notification ID and a bounded JSON object. Supported actions:
session, configure, read, invoke, dismiss, clear, delete-history, restore, export.
Restore creates a read-only card without reviving old application actions.
Export returns metadata only, excluding all titles, bodies, conversations and
action labels. Deleting history removes inactive records; active persistent
warnings remain. Settings are unavailable while locked. Notification IDs are
durable monotonically increasing uint32 values; exhaustion fails safely.

Application hints: x-ether-privacy public/sensitive/secret (default sensitive),
x-ether-thread, x-ether-group, x-ether-event-id, category, resident, transient,
urgency. Event keys deduplicate within verified executable identity; use opaque
hashes rather than phone numbers or secrets. Desktop-entry and display name are
never used as authenticated identity. Identity uses the bus sender PID, UID and
resolved executable/script path; a hash of that path scopes settings. Interpreted
applications sharing an interpreter without a script path share that identity.
This is same-session process attribution, not a sandbox against malicious code
already running with the user's full Unix privileges.

Security and policies
---------------------

Apps can replace/close only their own live notification IDs. Unique sender loss
invalidates actions. Restarts preserve records and strip stale action ownership;
applications should emit new events when meaningful, not replay old requests.
Limits: 32 KiB request, 4096 body characters, 256 title characters, eight actions,
20 requests/10 seconds/sender, 100/10 seconds total, 512 active, 2000 retained.
Retention: 1–365 days (default seven). History pruning is hourly and on new data.
Expired notifications are scheduled by their nearest deadline. DND schedules
check minute boundaries only when enabled, in local time; overnight schedules
use the day on which the interval starts. Manual override takes precedence.
Settings writes are validated before committing. Priority is low/normal/high/
critical; third-party urgency cannot grant critical priority. Authenticated user
per-app overrides are bounded for untrusted applications. Priority DND permits
only explicit user exceptions; Alarms mode requires trusted alarm provenance;
Total Silence suppresses every interruption. Critical system exceptions are
opt-in. A generic urgency flag never grants emergency-call handling privileges.

The mobile Notification Center offers application/thread/category groups,
collapse, search, filters, read/dismiss, clear, history, restore and redacted
export. Status-area access, Quick Settings and Settings use the same client and
backend. Banners have a bounded queue, timeout, swipe, default action and action
buttons. Active calls suppress ordinary interruption. No transient banners are
replayed after restart/resume. There is no notification-driven screen wake.

Integrations and explicit release limits
----------------------------------------

EtherSMS continues to use its existing conversation repository; it supplies
opaque conversation/event hashes and supports Open and Mark as read. No message
is sent by a notification action. Controlled inline reply is not yet available;
opening the conversation is the supported reply path. EtherPhone retains its
dedicated incoming-call overlay and emits no generic incoming-call banner.
Missed-call notifications continue over the standard API, with an Open call
history action. EtherShell launches the fixed EtherPhone binary with --history;
the phone UI uses a private single-instance socket to focus existing history.

EtherAudio PlayNotification(s) accepts only default/soft built-in cues from the
installed notification policy owner, uses notification category volume, existing
audio focus and paplay through PipeWire, and suppresses playback during calls or
suspend. It never executes application-supplied sound paths. Physical audibility
must be verified separately. Audio servers are not replaced or restarted.

Verified system-bus EtherPower Notice events create persistent system cards.
Power Saver suppresses banners. logind PrepareForSleep suppresses interruption;
resume expires stale cards and refreshes visibility without replay. D-Bus queued
messages are handled after resume. Deep-suspend wake and radio wake are NOT
verified or promised. No Android partition, modem or network configuration is
modified by this component.

The existing homeLocked preference is a UI restriction, NOT authenticated
EtherLock. Privacy-redacted/count-only lock cards are implemented; actions require
an unlocked, verified shell session. The service starts locked and returns to
locked when its shell owner disconnects or its 90-second session lease expires.
A coarse 60-second shell heartbeat renews that lease. Existing local-seat logind
Lock/LockedHint signals independently enforce redaction; a shell heartbeat cannot
override an externally locked session. No locker is installed or simulated.
An authenticated EtherLock
provider and tap-to-open-after-authentication remain pending. A real screen
locker must cover the graphical session; this release cannot certify an absent
authentication service.

A vibrator sysfs interface exists on the phone, but EtherHardware has no verified
haptic operation. No direct vibrator writes are made. Vibration preferences are
reserved in the validated policy schema; activation is intentionally unavailable
in Settings until hardware operation is tested. Selected-contact/repeated-call
DND exceptions and a trusted alarm producer also require their respective
verified providers. A user-attended reboot was verified on 20 October 2026,
including automatic service/shell startup, preserved settings/history and Wi-Fi
HTTPS. The boot menu still requires manual EtherPocket selection. Deep suspend
remains blocked by the existing power policy and unverified; it is not implied
by restart, screen blanking or reboot tests. See the delivery assessment.

Build and verify
----------------

Run python3 -m unittest discover -s ethernotifications/tests -p 'test_*.py' -v.
On Linux run dbus-run-session -- python3 ethernotifications/tests/service_fixture.py.
Build via scripts/build-ethernotifications.sh in EtherPocketBuild. The same ARM64
toolchain builds EtherShell and the notification UI fixture. Device verification
uses a private bus/store before a coordinated production ownership migration.
Tests do not send SMS, make calls, toggle networking or exercise haptics.
Publish the engineering Debian package using the existing Etherneco distributor
manifest; no separate updater or distribution service is introduced.
