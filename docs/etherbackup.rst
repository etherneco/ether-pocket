EtherBackup 0.1.0 — encrypted backup and recovery commissioning
============================================================

This component uses Restic's maintained encrypted v2 repository format. It
provides incremental deduplicated compressed backups, private source staging,
SQLite online exports, metadata/data checks, representative and complete isolated
file restore drills, retention, administrator CLI, system D-Bus service and the
existing EtherShell Settings → System → Backup & Restore page. No EtherFleet
dependency, update distributor, custom archive or custom cryptography is added.

Commissioning and truth of protection
------------------------------------

The packaged policy intentionally has no destinations, component mappings or
automatic schedule. It cannot silently select a local disk or invent a recovery
password. An administrator must register the intended backup storage, enter a
password interactively and retain it independently. Never commit passwords,
private SSH keys, API tokens or exports to this workspace. No key-read/export
method exists on D-Bus or MCP. A local same-device repository is useful for file
mistakes but cannot establish storage-failure protection. The dashboard never
labels it Protected. An isolated file restore drill is not bare-metal recovery.

Read docs/etherbackup-audit-2026-10-21.rst and the delivery evidence for what was
actually tested. USB physical attach/remove, independent remote recovery, battery
impact, boot recovery and application health after live apply require separate
acceptance. Supported adapters are not evidence that an unavailable device was
tested. Location history is opt-in by adding an explicit history.sqlite source;
sensor calibration has no persisted path until EtherSensors implements it.

Provision /etc/etherbackup as root-owned 0755 or more restrictive, policy.json
0600, and /etc/etherbackup/credentials as root-owned 0700. Config and every
ancestor must be root-owned and not writable by others. After reviewing the
actual paths and exclusions, add a destination to policy.json, for example::

  "destinations": {
    "local": {"kind":"local", "repository":"/var/backups/etherbackup/repository",
              "passwordFile":"/etc/etherbackup/credentials/local-password"},
    "usb": {"kind":"usb", "repository":"/mnt/backup/etherpocket-restic",
            "mount":"/mnt/backup", "uuid":"ACTUAL-FILESYSTEM-UUID",
            "passwordFile":"/etc/etherbackup/credentials/usb-password"}
  }

Create the parent directory with appropriate permissions, then::

  sudo etherbackup init local --confirm-independent-password
  sudo etherbackup backup local --profile personal
  sudo etherbackup list
  sudo etherbackup verify POINT --level sample

The init command prompts twice using getpass, never a command-line password.
Restic passwords enter only via a protected password file, not an environment
value, process argument value, log message or API response. An already existing
credential is reused for initialization; repository init does not overwrite an
existing repository. After independent export is checked by the operator, set
independentKeyConfirmed true on that destination. Do not set this merely because
a file exists on the handset. Authorized key export requires an existing private
root-owned destination directory and exclusive creation::

  sudo etherbackup export-key usb /mnt/separate-key/recovery/password --confirm

Keep this separately from the repository. To rotate, use Restic's established
``key add --new-password-file`` workflow with private files on a trusted host,
verify a restore with the new key, update the protected password file atomically,
retain the old independent recovery material until verified, then explicitly
remove the obsolete key with ``restic key remove``. Key removal is never automatic.

Destinations and interruption
----------------------------

USB and NAS use existing Linux mount infrastructure. EtherBackup never formats,
mounts, unmounts or flashes storage. USB requires an exact mounted path and
filesystem UUID; a disconnected mount never falls back to root. Safely remove
using the existing storage UI or administrator umount only after the job finishes.
For a phone whose USB port is shared with the SSH link, commission locally after
attaching/mounting storage. These commands detect USB transport and pin its UUID;
they never format or mount it::

  sudo etherbackup usb-devices
  sudo etherbackup commission-usb usb /actual/mount/path --confirm
  sudo etherbackup init usb --confirm-independent-password
  sudo etherbackup backup usb --profile complete

The init command privately prompts for the recovery password. Retain it away
from the phone and drive before relying on recovery. A USB host-role switch may
disconnect the existing gadget SSH path. Use an independently tested Wi-Fi or
other recovery connection for remote supervision of USB jobs.

NAS supports mounted NFS/NFS4/CIFS/SMB3. Check free space before staging and
repository write; remote SFTP free space is unknown and is not advertised as known.

SFTP destinations use a root-managed SSH alias::

  {"kind":"sftp", "repository":"sftp:backup-nas:/srv/etherpocket",
   "passwordFile":"/etc/etherbackup/credentials/nas-password",
   "sshConfig":"/etc/etherbackup/ssh_config",
   "knownHosts":"/etc/etherbackup/known_hosts",
   "sshKey":"/etc/etherbackup/credentials/nas-ssh-key", "uploadKiB":2048}

All SSH configuration/key/known-host files and ancestors must be root-owned,
not symlinks and not writable by others. Provision the expected host key through
an independent authenticated channel. SSH runs BatchMode, IdentitiesOnly and
StrictHostKeyChecking=yes with the commissioned known-hosts file. There is no
accept-new or host-key bypass. Review SSH config as executable administrator
policy; it can include SSH ProxyCommand directives and is not user input.
SFTP is encrypted by SSH and the repository remains encrypted by Restic.

Restic owns repository locks and atomic snapshot commits. A nonzero exit,
including partial-source errors, never grants operational status. Retry the job
after fixing connectivity; deduplication reuses committed content. Byte-offset
resume is not claimed. Stale locks require an administrator to establish that
no writer exists before using Restic's unlock; no automatic unlock is performed.
The local flock serializes CLI, D-Bus, scheduler and EtherUpdate operations.

Application contracts and consistent databases
---------------------------------------------

Source contracts in the protected policy contain application ID, exact paths,
exclusions, explicit secret policy, schema version declarations, preparation,
completion and restore validation descriptions. They cannot supply executable
archive hooks. Implemented preparation is regular-file staging plus SQLite
online backup; completion closes source handles. No application daemon is stopped.
Applications requiring non-SQLite transactional export must add a reviewed adapter;
unsupported consistency types fail closed. No duplicate runtime database is added.
Staged SQLite exports are backup artifacts and are removed at job completion.

The service walks source ancestors using no-follow directory FDs, skips symlinks
and special nodes, excludes SQLite journal/WAL/SHM files, recognizes SQLite by its
header even with unusual extensions and invokes the SQLite backup API. A user DB
is opened by a helper running as its owning UID/GID with supplementary groups
cleared; it is never opened as root. The helper handles the live WAL, exports
only committed records and checks integrity. Ordinary changing files cause a
retry rather than a silent inconsistent copy. Source mutations across multiple
files are not an atomic application-wide transaction. Add a reviewed app export
contract before relying on multi-file invariants or migration rollback.

This ext4 implementation needs a temporary staged copy of selected sources;
Restic network/storage writes remain incremental/deduplicated. A stable staging
pathname and preserved file mtimes allow unchanged-content reuse. Default bounds
are 100000 files, 16 GiB staged data, two Go CPUs, one worker and 2 MiB/s upload;
systemd assigns low CPU/I/O priority and a 768 MiB memory budget. These are bounds,
not measured mobile performance promises. Empty directories, symlinks, ACLs,
xattrs, capabilities and special files are not restored by this safe file export
path; modes/owner IDs are recorded for administrator review but isolated restored
files stay 0600 and non-executable. This is another reason it is not an OS image.

Verification, retention and restore
----------------------------------

Every successful backup immediately runs repository metadata discovery, full
Restic read-data integrity verification and an isolated sample restore containing
one regular file from each included application contract and every SQLite DB.
SHA256, size, timestamps and database integrity are validated. Full data read
may be expensive on mobile/remote storage; no verification is implied by upload.
The manifest is encrypted in the repository and its digest is persisted privately
with the snapshot identity. A failed verification revokes verified status.

``verify --level metadata`` checks snapshot and manifest presence/identity;
``integrity`` adds Restic metadata check; ``sample`` adds full data read and
representative file/DB restore; ``drill`` restores all staged regular files into
an isolated directory. These levels never claim a boot recovery drill.

Retention uses calendar daily/weekly/monthly buckets (default 7/4/6), groups by
profile and destination, preserves protected/update points and the newest
verified point for every profile. Cleanup is allowed only after a fresh successful
verification of the newest backup; forget uses explicit locally journaled IDs,
then prune/check. Unmanaged snapshots are never deleted. Automatic cleanup is
off by default. ``etherbackup protect POINT`` pins a restore point.

Use the CLI independently of EtherShell::

  sudo etherbackup status
  sudo etherbackup list
  sudo etherbackup preview POINT --path home/mobian/Documents
  sudo etherbackup restore POINT --path home/mobian/Documents --confirm
  sudo etherbackup recovery-info POINT > /private/export/recovery.json

Restore writes exclusively into a new root-private /var/lib/etherbackup/restores
directory and does not overwrite originals. It uses Restic dump into exclusively
created regular files, never generic archive extraction or archive-provided code.
Traversal, absolute selections and symlink components are refused. Each restored
file is checksum-checked and each SQLite database integrity-checked. If a job
fails, its isolated output remains unapproved; no apply operation follows.

The UI provides restore points, file/directory selection, preview, explicit
confirmation and isolated restore. Authenticated administrators may export
the files to a chosen destination after review. Live overwrite, schema migration,
application restart/health validation and automated contact import are not
implemented. Before manual apply: stop only the affected app, preserve a safety
copy of its current database/config under a private directory or verified
encrypted point, evaluate schema versions and newer-data loss, replace only
reviewed paths, set correct owner/permissions, restart and run functional checks.
Do not overwrite a running database or auto-apply restored systemd/network files.
System-level apply requires explicit administrator authorization outside this
isolated-restore API. No privileged script is executed from any backup.

EtherUpdate and AutoUpdate Center
--------------------------------

EtherUpdate calls ``etherbackup pre-update TRANSACTION COMPONENT...`` after
signed artifact verification and safety checks, before engine preparation or
activation. Every component must be mapped to known source contracts in
updateComponents and updateDestination must identify a commissioned repository.
An absent/unverified backup blocks installation. The full snapshot ID and verified
recovery-point ID are persisted in EtherUpdate's durable transaction document
before installation. Bundle link rollback remains EtherUpdate's responsibility.

Health success records healthy in EtherBackup and keeps the recovery point for
30 days. Failure pins it. A lost outcome notification leaves the point pinned.
There is no automatic database downgrade: newer records and schema compatibility
must be evaluated before data apply. Interrupted update transactions retain
their recorded references and the existing EtherUpdate recovery-required state.

Recovery manifests record OS/kernel, read-only partition/mount metadata, package
inventory, user/group metadata without password hashes, installed signed release
references, dependency versions, artifact hashes and signing-key IDs. The existing
https://autoupddate.etherneco.com remains the signed artifact authority. EtherUpdate
must independently verify retrieved signatures and compatibility; a backed-up
public key does not become a new trust root. No private backup, credential or
encryption key is sent to that service or exposed through MCP. No alternate
release service is created. Signed publication requires the existing commissioned
publisher trust, component/project mapping and release authentication.

Scheduling, authorization and notifications
------------------------------------------

After commissioning a destination set schedule.enabled true and enable
etherbackup-scheduled.timer. It is independent of EtherShell and catches missed
daily runs. Use a systemd timer drop-in OnCalendar=weekly or an explicit reviewed
calendar expression for weekly/custom schedules. The optional charging-only and
selected NetworkManager connection UUID conditions defer a job. Low battery,
unknown/stale power telemetry or thermal warning fail closed. Conditions changing
mid-file are checked at the next staged file, at most every ten seconds; this is
abort-and-retry rather than thermal pause/resume. EtherPower's existing logind
sleep/shutdown inhibitors protect backup/verification/restore and are released
when the job exits. No indefinite wake lock is created.

Charging/Wi-Fi events and USB-attach-triggered runs are not wired automatically;
the administrator may start the oneshot service after a mount is validated.
A deferred daily job waits for its next scheduled/manual invocation. No indefinite
polling or automatic storage mount is used. The timer is packaged but not enabled
before configuration. No exact next-run timestamp is advertised by the UI.

Public system-bus state/signals contain only coarse status. Private history,
paths, repository IDs, preview, restore and backup execution need separate
noncached Polkit administrator authorization and an active unlocked logind
session. For adopted shells, the service derives a same-UID graphical process
from the kernel session scope and supplies its PID/start-time/UID to Polkit;
it rechecks the bus caller and unlocked display before starting work. Root CLI remains usable over independent SSH. EtherLock publishes the
logind lock hint; the Qt client also clears private details and ignores pending
private replies on lock or service loss. Credentials are never returned.

The existing EtherShell client bridges generic backup events into EtherNotifications
which owns privacy, Do Not Disturb and history. Repeated service events are
deduplicated for one hour. No private filenames, destinations or secrets occur in
notification text. When EtherShell is closed there is no session notification
bridge; persisted CLI/status remains the authority. Rich progress is collected
by the engine but UI streaming and independent notification relay need further work.

Independent disaster recovery procedure and limitations
------------------------------------------------------

1. On a trusted Linux host install a compatible Restic (0.18 or newer), obtain the
   independent repository and separately retained recovery password. Verify the
   intended repository identity from an independently exported recovery manifest.
2. Use restic snapshots and restic check --read-data with private password-file
   access. Restore the selected snapshot into a NEW private host directory.
   The encrypted snapshot contains files/ and manifest.json under the staging
   tree path recorded in recovery-info. Never restore directly over host /etc.
3. Check the manifest digest, file hashes and SQLite integrity; review exact OS,
   device compatibility and signed release references. A host-side file restore
   does not prove the phone can boot. Use EtherUpdate's independently trusted
   signing policy to obtain compatible application releases from AutoUpdate Center.
4. If Debian boots, use independent SSH for service/configuration diagnosis and
   the isolated CLI restore. Preserve current data before any reviewed offline
   apply. Incorrect systemd files should be reviewed against the known-good copy
   before replacement/reload; network changes can disconnect recovery access.
5. If root will not boot, use only the previously prepared device-specific trusted
   host rescue procedure in docs/bootmenu-2026-10-15.rst after verifying current
   image/device identity. The historical boot menu and Fastboot bridge were tested
   previously; restoring a corrupted root with EtherBackup has NOT been tested.
   Rescue SSH cannot be assumed when it depends on a flag on the damaged root.
   No phone USB-disk boot, Android-based Debian restore or partition imaging is
   assumed. Obtain a verified compatible rescue image before filesystem repair.
6. Full root reconstruction, user replacement, new-device identity, package
   reinstall order and boot round-trip remain a controlled spare-device recovery
   drill. No raw partition restore/flash command is supplied or run by EtherBackup.
   Android partitions, bootloader, modem firmware and calibration remain untouched.

If internal storage fails and no independent repository/key exists, local backups
cannot recover it. Until an actual root rebuild and boot/application health drill
succeeds, full-system disaster recovery and the overall master-task definition
of done remain incomplete.
