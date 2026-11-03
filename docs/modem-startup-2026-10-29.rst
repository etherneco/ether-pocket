GM1920 modem startup repair, 2026-10-29
=====================================

Cause
-----

The modem subsystem and ModemManager were both running after startup, but
ipa_fws remained OFFLINING and rmnet_ipa0 did not exist. ModemManager logged
``Failed to find a net port in the QMI modem``. Previous IPA initialization
was manual only; no service replayed the vendor's /dev/ipa startup action
after reboot. The downstream data service was static and inactive.

Repair
------

``ethermobile-ipa.service`` is enabled under multi-user.target and ordered
after etherpocket-modem and before ModemManager. A ModemManager drop-in also
pulls in the initializer when ModemManager is started separately.

``scripts/ethermobile-ipa-start.py`` validates disk identity, board, kernel and
the previously audited firmware hashes, waits for the modem, then performs
the vendor startup write once per boot. The existing manual tool and the
service share an exclusive /run/ethermobile-ipa-attempted marker. Failed
initialization is not retried automatically. If the interface already exists,
the service validates its type and refreshes udev without repeating the write.
Waits and the service startup have finite timeouts.

Install using ``python scripts/install-ethermobile-ipa-start.py`` from the
Windows workspace with its existing USB SSH connection. Existing files are
preserved under /root/ethermobile-ipa-backup-* on the phone. The installer
validates the unit and enables/starts it. Firmware, GSM profiles, PINs and
Android partitions are not changed. This repair initializes the network port;
it does not enable automatic mobile data or change the separate data adapter.

Verification
------------

The initial live start created rmnet_ipa0. A subsequent service restart took
the existing-interface path without another firmware write. The phone was
then rebooted for boot acceptance. The read-only verification command is
``python scripts/verify-ethermobile-ipa-start.py``; its evidence file is
``evidence/ethermobile-ipa-start-reboot-2026-10-29.json``. It checks a changed
boot ID, enabled initialization, the real interface, a detected modem, one
startup write and the supporting services. Registration state is recorded
separately and is not treated as proof of internet access.

Post-reboot acceptance passed all six checks: the interface appeared
automatically, ModemManager detected the modem in registered state on its
home network, and Wi-Fi's network interface, SSH and Bluetooth were available.
Monotonic timestamps confirm IPA completed before ModemManager started.
The separate cellular data service remained inactive.

The handset's clock was a week behind the workstation during diagnosis;
boot IDs and monotonic service timestamps are used to assess the reboot.

To disable future initialization, disable ethermobile-ipa.service and remove
/etc/systemd/system/ModemManager.service.d/ethermobile-ipa.conf, then run
systemctl daemon-reload. Stopping the oneshot service does not unload IPA.
