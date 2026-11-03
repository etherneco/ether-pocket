EtherBackup commissioning delivery — 21 October 2026
==================================================

Status: commissioning; master task incomplete. The final backup coordinator,
USB commissioning CLI and mandatory EtherUpdate hook are installed. EtherShell
Backup & Restore is active in /opt/ethershell2/2.1.0-backup-2ade5239844d, built
from current sources to preserve the newer EtherMAP integration. The previous
map shell and rollback launcher remain available. No production repository,
password, automatic schedule or signed release was invented.

Implemented
-----------

* Restic encrypted v2 adapter; compressed incremental/deduplicated repositories.
* Explicit source registry and four profiles; consistent SQLite online exports
  including live WAL, recorded database schema identity, private regular-file
  staging, forbidden path/repository/credential exclusion and no-follow traversal.
* Local, USB UUID/transport-checked, pinned-key SFTP and mounted NAS adapters.
  USB discovery/commissioning commands never format or mount storage.
* Metadata, integrity, representative restore and full isolated file drill levels;
  actual checksum/database validation, failed-verification status revocation.
* Private alternate-destination restore, preview and explicit confirmation;
  protected restore points and verified/calendar-based retention.
* Independent root CLI, system-bus worker with eight privileged operations,
  noncached Polkit authorization, logind lock checks and generic notification
  events through the existing EtherShell/EtherNotifications bridge.
* Packaged persistent systemd timer, charging/Wi-Fi/power/thermal conditions,
  flock serialization, bounded worker/engine resources and suspend inhibition.
* EtherUpdate installation blocked without a sample-verified data recovery point;
  reference journaled before activation; update health outcome/safety hold/pinning.
  No automatic older database apply or schema downgrade is allowed.
* Machine-readable encrypted recovery manifest, signed release references from
  existing EtherUpdate history and trusted-host recovery instructions. No backup
  or key upload to AutoUpdate Center; no separate updater or EtherFleet dependency.
* EtherShell System → Backup & Restore source and ARM64 shell package. The active
  shell exposes the page; current-map sources were preserved in the rebuilt package.

Verified evidence
-----------------

The final handset run passed 35 backup tests and 39 update tests. Real repositories were
created/restored; tests cover two backup versions, live SQLite WAL with committed
and uncommitted records, wrong password rejection, deliberately missing data
packs, traversal/symlink/special-file rejection, overlap, protected retention,
pre-update backup failure and durable references before activation. A disposable
loopback SFTP server verified encrypted backup/restore, exact host-key rejection,
disconnect and reconnect. This is not an independent remote repository test or
an interruption during an active data transfer.

Eight real calls from nobody were rejected by the installed system-bus service;
public status contained no private paths/history/credentials. Root inspection
worked. SSH/NetworkManager/modem/Bluetooth/power/hardware PIDs and service states
were unchanged by native backup tests and backend provisioning. No device reboot,
Android partition write, filesystem repair, format, firmware or bootloader write
was performed.

On a disposable 8396840-byte handset fixture: first backup plus full verification
8.29 seconds; incremental plus full verification 4.90 seconds; original-version
restore 2.93 seconds. Initial stored bytes 8411636, incremental stored bytes
22237; child peak RSS 97604 KiB. Charging was present. These small-fixture values
do not establish large-media throughput, battery impact or network consumption.

The final shell passed route, rendering and geometry checks in light/dark at
360x900, 1080x2340, 1000x600 and 1920x1080. The accepted package SHA256 is
2ade5239844d5b676980d9ff3708d1e14bbb6c45482233120726f66735a5b47e.
Live Backup and Location routes work; a real screenshot is saved at
evidence/etherbackup-live/backup-live.png. The screen was initially
software-blanked; the existing wake command restored it without changing locking
or power settings.

Authorization commissioning found that the adopted shell belongs to the root
SSH launcher's cgroup. Its direct bus subject was denied with no challenge.
The final service derives the caller UID from D-Bus, resolves its active unlocked
logind display, verifies a same-UID process in that exact kernel session scope,
and supplies its PID/start time/UID to Polkit's supported unix-process subject.
The unique caller and display state are rechecked before work starts. Root CLI
calls retain their system-bus-name subject. No policy defaults or administrator
password requirements were relaxed. The real probe returns authorized=false,
challenge=true. Eight real nobody calls still fail. A compatibility probe using
unix-session in CheckAuthorization aborted the installed Polkit 126; the service
was restored, its agent re-registered, and that unsupported subject is absent
from the final implementation.

Evidence: etherbackup-audit-2026-10-21.json, etherbackup-device-tests.json,
etherbackup-authorization.json, etherbackup-benchmark.json,
etherbackup-install.json, etherbackup-session-polkit.json,
etherbackup-ui-package.json, etherbackup-deployment.json,
etherbackup-live/regression.json and etherbackup-delivery.json in evidence/.

USB and access handoff
----------------------

The user confirmed storage attachment, then restored the original USB SSH link
and restarted SSH. Final deployment, UI activation and regressions completed over
that restored pinned connection. No USB storage is visible now (usb-devices=[]).
Wi-Fi is enabled but disconnected. A single retry of the existing saved profile
failed because its network could not be found; no new credentials or profile were
created. The USB gadget link and USB host storage cannot currently be supervised
simultaneously through the available connection. Use the local private CLI below,
or provide a working independent network link before attaching the disk again.

The updated USB helper is installed. Attaching storage can be commissioned
from the phone's private local terminal, avoiding dependence on gadget SSH::

  sudo etherbackup usb-devices
  sudo etherbackup commission-usb usb /actual/mount/path --confirm
  sudo etherbackup init usb --confirm-independent-password
  sudo etherbackup backup usb --profile complete
  sudo etherbackup list
  sudo etherbackup verify POINT --level drill

Replace the mount path and POINT with observed values. Mount through the existing
Linux storage infrastructure first. The password is entered privately by getpass;
retain it independently of the phone and backup disk. Never paste it into chat.
Do not enable the timer or automatically enforce retention before this acceptance.
Safely remove/reconnect the disk, re-verify and repeat an isolated restore. Record
these results and independent key retention before reporting production protection.

Remaining gates
---------------

* Physical USB detection, filesystem/mount audit, private password provisioning,
  real-data backup, removal/reconnect and restore acceptance.
* Independent remote host recovery and active-transfer interruption testing.
* In-place app/database/configuration apply, migration compatibility and real
  application functional checks after apply. Isolated restore is implemented.
* Charging/Wi-Fi/USB event triggers, automatic deferred-job retries, richer UI
  destination editing/progress, next-run display and notification relay while
  EtherShell is closed. Timer and policy support are packaged; scheduling is off.
* Spare-device/root reconstruction, actual rescue-image procedure, boot round
  trip, external display and complete functional regressions. File-level backups
  do not preserve every OS ACL/xattr/link/special-file attribute.
* Signed AutoUpdate Center publication: existing publisher credentials, trusted
  signing keys and component/project mappings are not commissioned. No release
  was published and no old cached API credential was reused.

Full-system disaster recovery is explicitly not complete. See etherbackup.rst
for the detailed operating model, safe offline apply and honest rescue limitations.
