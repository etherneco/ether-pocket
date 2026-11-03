EtherBackup device audit — 21 October 2026
=========================================

The read-only pinned SSH audit is evidence/etherbackup-audit-2026-10-21.json.
The device is GM1920, native Debian 13.7 ARM64, kernel 4.14.117-perf #6.
Six UFS LUNs sda–sdf are parts of the SAME internal storage, not independent
backup devices. Debian root and home share /dev/sda21, ext4, 208467374080 bytes,
UUID e96c95a2-a935-47b0-94f1-78c7b412eed4; free space was 183511154688 bytes.
No dm-crypt mapping, Btrfs, ZFS, LVM snapshot or Debian root A/B was discovered.
Android userdata is sda20 (32 GiB); Android system/vendor and boot/firmware
partitions remain outside backup sources and restore targets. No ordinary
PC-style EFI/USB boot path is established. No external disk was attached.
USB gadget networking provides the verified SSH path; Wi-Fi was disconnected.

Existing protection: dpkg-db-backup.timer, historical host-side GPT header and
boot image copies, boot menu recovery scripts and EtherUpdate's versioned app
link rollback. None establishes a verified user-data or bare-metal recovery set.
No installed Restic or Borg was found. Debian's configured ARM64 candidates are
Restic 0.18.0-1+b4 and Borg 1.4.0-5. Both offer encryption, compression,
deduplication, incremental backup and repository checks. Restic is selected:
SFTP needs no server-side backup program and JSON output fits the existing
Python/D-Bus service architecture. Actual mobile resource use requires testing.
References: https://restic.readthedocs.io/en/stable/ and
https://www.borgbackup.org/ . No custom crypto or archive format is introduced.

Application paths were cross-checked against current source, including
/home/mobian/.config/ethershell, Etherneco/EtherSMS.conf, etherphone,
.local/share/ethercontacts, etherphone, etherlocation, ethernotifications,
Pictures/EtherCamera, /var/lib/etherpower and /var/lib/etherupdate/history.sqlite.
Source contracts must enumerate exact paths; credentials, caches, location
history and lock secrets are excluded by default. SQLite online backup is
required even for databases with unusual filename extensions.

SSH is verified now. Historical docs/bootmenu-2026-10-15.rst records physical
Android/Mobian switching and a prepared trusted host Fastboot bridge. The rescue
SSH mode depends on a Mobian-side debug flag; this cannot be the sole disaster
path. No reboot, USB boot, corrupted-root repair or bare-metal restoration was
tested here. Bootloader unlock state, spare storage, independent repository,
independent recovery key and a compatible trusted rescue image remain recovery
acceptance gates. Android is not assumed able to restore Debian. No partition,
bootloader, modem, mount or filesystem-repair command was issued by this audit.
