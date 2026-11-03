Native cellular ping — 2026-10-19
================================

Result
------

Real giffgaff LTE data traffic now works on the phone. Wi-Fi remained disabled
throughout acceptance. Two stop/start cycles each returned 5/5 ICMP replies
from 1.1.1.1 through epcell0. The normal unprivileged user's existing ping
returned 3/3 replies from example.com, verifying system DNS as well. An IPv4
TCP connection bound to epcell0 reached 1.1.1.1:80. The final service is active.
Exact outputs: ``evidence/cellular-ping-2026-10-19.json``.

Corrections
-----------

The modem's initial LTE bearer used MOBILE.O2.CO.UK while the saved data profile
used giffgaff.com. ModemManager SetInitialEpsBearerSettings applied the official
giffgaff APN, PAP and IPv4v6 settings. Registration changed from searching to
home and packet service from detached to attached immediately afterwards.
No PIN was sent. Earlier network rejection was not proof of an inactive SIM.

The existing GSM profile now stores the initial EPS bearer settings and allows
internet routes at metric 900. Its original keyfile is backed up on the phone
under ``/root/ethermobile-backup-2026-10-19``. Credentials stay root-owned.

Stock ModemManager 1.24 then rejected the downstream virtual rmnet_ipa0 port:
``Unsupported QMI kernel driver for 'net/rmnet_ipa0': (null)``. A data session
therefore uses the explicit downstream adapter ``scripts/ethermobile-ipa-data.py``.
It keeps a dedicated libqmi WDS client alive while MM continues registration
management. It refuses to start while NM's qrtr0 device is activating/connected.
It does not restart NetworkManager, ModemManager or Qualcomm firmware services.

The adapter reads the real endpoint and pipe pair through this exact kernel's
msm_rmnet.h ioctl ABI. DPM opens embedded endpoint 1 with pipe pair 2/11. A real
kernel rmnet child epcell0 uses QMAP mux 1, bound to the WDS client. The modem
supplies the IP, gateway and DNS; these are not static sample addresses.
systemd-resolved receives per-link DNS, reverted when the session ends.

WDA requests must include uplink maximum datagrams and size (1 and 16384).
Without those fields the firmware returned aggregation disabled despite a
successful SetDataFormat result. With them, both negotiated protocols are
QMAP. The adapter verifies the returned protocols before starting data.
Both hardware pipe setup ioctls use format flags 14 and are guarded by a
per-boot marker to prevent duplicate pipe allocation.

Current boot migration
----------------------

During diagnosis the producer was initially opened without QMAP deaggregation.
The driver's allocation ioctl cannot reconfigure an already-open pipe.
``kernel/ether_ipa_qmap.c`` uses the exported IPA configuration API to apply
the driver's QMAP producer settings to the existing endpoint, with restoration
on unload. It was built against the exact current kernel and signed with its
existing key using ``scripts/build-ipa-qmap.sh``. This small module remains
loaded in the current boot and is not installed for automatic loading. It
does not replace the kernel, reload firmware, or write boot/Android partitions.

The current ``/run/ethermobile-ipa-pipes.json`` records both configured pipes
and this runtime migration. Removing the module restores the previous producer
format and interrupts working data. A fresh boot is intended to initialize
the correct format directly through the adapter's ioctls; that path has not
been cold-boot tested. No reboot was performed for this repair.

Operation and limits
--------------------

Installed adapter:
``/usr/local/lib/ethermobile/ethermobile-ipa-data.py``.
Installed unit: ``/etc/systemd/system/ethermobile-data.service``.
Added Debian ARM64 gir1.2-qmi-1.0 and gir1.2-qrtr-1.0 for Python GI bindings.

Data is currently active. Explicit controls on the phone::

    sudo systemctl stop ethermobile-data
    sudo systemctl start ethermobile-data
    ping -c 3 1.1.1.1

The unit has no boot enablement and requires an already initialized rmnet_ipa0.
Automatic IPA startup, reboot persistence and the new data adapter's GUI
integration are not verified or implemented by this change. The existing
Mobile Data toggle still uses the unsupported stock MM bearer path; it does
not control this service and may show disconnected despite the adapter's
working data session. Use the explicit service controls above.

IPv6 data setup returned CallFailed; working IPv4 does not establish IPv6
support. An earlier four-packet probe lost one packet, so the passing final
acceptance is not a guarantee of loss-free radio service.

NetworkManager, ModemManager, SSH, Bluetooth and etherpocket-modem remained
active after both final cycles. No SIM lock/PIN, roaming, modem firmware or
Android partition was changed. No automatic data retries or boot activation
were enabled.

References
----------

* https://help.giffgaff.com/en/articles/245215-internet-apn-settings-guide
* https://www.freedesktop.org/software/ModemManager/doc/latest/ModemManager/gdbus-org.freedesktop.ModemManager1.Modem.Modem3gpp.html
* https://github.com/linux-mobile-broadband/libqmi/blob/1.36.0/data/qmi-service-dpm.json
