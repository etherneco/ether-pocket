USB Mass Storage on native Mobian
================================

Installed on the GM1920: an 8 GiB FAT32 exchange disk named ETHERPOCKET.
It is a regular image at /var/lib/etherpocket/usb-storage.img, not an
Android partition or the active Mobian root filesystem. No repartitioning.
FAT32 supports individual files smaller than 4 GiB.

Connect USB-C to a computer: ETHERPOCKET appears as a USB disk. On the
tested Windows host it received drive E:. Safely eject that disk before
unplugging. After eject, or three seconds after physical disconnect,
the phone checks FAT and mounts it at /media/mobian/ETHERPOCKET.
Open ~/USB or the Pliki USB / USB Files desktop shortcut. Reconnecting
unmounts the phone's copy before exposing it to the computer. Open files
which prevent unmount also prevent export; close them and retry.

Home files are now mirrored at the root of this USB disk. Documents,
Downloads, Pictures, Desktop and other visible files/directories in ~/
are copied before export. Changes made by the computer are imported after
safe eject or disconnect. This is synchronization at handover, not live
access to the same filesystem. Hidden names, Linux symlinks, special
files, the ~/USB link and Windows volume metadata are excluded. FAT32
incompatible names or files over its size limit stop export with an error
in the service journal rather than silently dropping data.

The synchronizer compares SHA256 with the previous successful handover.
When both sides change a file, it preserves the phone version at its
original name and adds a .usb-conflict-<timestamp> copy from the computer.
Deletions and replaced home versions are backed up under
~/.local/share/etherpocket/usb-home/backups/. Empty-directory deletion
never recursively removes files. A failed sync blocks USB export.
The helper runs as mobian, and does not change the home filesystem,
ownership or Linux login credentials. Its baseline is outside the disk.
Remove /etc/etherpocket/usb-home-sync to disable this optional mirroring.

Concurrent filesystem ownership is forbidden by the kernel's Mass
Storage Gadget documentation:
https://www.kernel.org/doc/html/latest/usb/mass-storage.html

The service preserves the existing RNDIS USB SSH connection. The composite
gadget uses PID 0105 to avoid cached Windows RNDIS-only descriptors.
OnePlus's kernel defaults mass_storage to a virtual CD-ROM; configuration
explicitly clears cdrom and ro and keeps FUA enabled (nofua=0).

Install/reinstall with ``python scripts/install-usb-storage.py``. Existing
images are preserved. The enabled systemd service configures the gadget
after the USB debug service and runs the ownership watcher. The rootfs
builder does not yet include this optional exchange disk automatically.

Verified on the physical phone and Windows on 2026-10-16:

* USB composite, RNDIS and Mass Storage drivers report OK.
* Windows mounts the 8 GiB disk as FAT32, label ETHERPOCKET.
* A random 1 MiB Windows write matches SHA256 on Mobian after SCSI eject.
* A file written as user mobian matches SHA256 on Windows after a software
  USB disconnect/reconnect. The watcher releases the local mount first.
* USB SSH remains operational after re-enumeration.
* Ownership gate tests: ``python -m unittest discover -s tests -p test_usb_storage.py``.
* Home synchronization and ownership tests: 12 passed on the physical
  Linux phone, including two-sided edits, recoverable deletion, hidden
  config exclusion, symlink rejection and FAT32 filename validation.

The attempted SMB home share was removed at the user's request. Samba
server packages, its enabled service, mapped M: drive and the dedicated
saved Windows credential were removed. Home mirroring uses USB Mass
Storage only.

Automatic screenshots on Windows (2026-10-17)
-------------------------------------------

The current Windows host now runs ``scripts/windows-screenshot-sync.py``
through a per-user Startup shortcut named ``EtherPocket Screenshot Sync``.
Install or refresh it with ``scripts/install-windows-screenshot-sync.ps1``.
It polls the phone over pinned USB SSH every two seconds and copies missing
``Screenshot-*.png`` files into ``E:\Pictures\Screenshots`` while E: is the
FAT32 volume labelled ETHERPOCKET. SSH must remain reachable. It retries
after disconnects; screenshots taken offline are copied on reconnection.
This requires this Windows helper on the connected PC.

Only Windows writes to the exported disk. The phone's backing image is
never mounted or modified by this helper. Downloads use temporary files
and SHA256 verification before becoming visible under their final names.
Existing destination names are preserved. Deleting a screenshot only on
Windows while connected causes this additive copier to copy it again;
stop the helper before relying on deletions through the handover sync.
Other files retain the existing handover synchronization behavior.

To disable autostart, remove the ``EtherPocket Screenshot Sync.lnk`` file
from the Windows Startup folder (``shell:startup``). Stop the matching
``pythonw.exe`` process to disable the current run. Logs are written under
Python's ``LOCALAPPDATA/EtherPocket/screenshot-sync.log`` (Store Python may
redirect this into its package's LocalCache directory).

Verified against the running EtherShell on the phone: an XTest-injected
Power + Volume Down chord created a new screenshot, which arrived on E:
after 2.01 seconds with matching SHA256. Evidence is in
``evidence/windows-screenshot-sync-2026-10-17.json``. Targeted tests cover
an absent/replaced USB volume, incomplete-transfer recovery, and preservation
of existing Windows files. Login autostart is installed but has not been
tested by signing the user out.

macOS/Linux hosts, a physical unplug/replug, and a full phone reboot have
not been tested in this session. Standard USB Mass Storage plus FAT32 is
intended for all three hosts. A forced cable removal cannot guarantee that
the computer has finished flushing its writes; always use safe eject.
