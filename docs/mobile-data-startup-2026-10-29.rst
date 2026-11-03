Cellular data startup repair, 2026-10-29
======================================

Cause and repair
----------------

After the modem startup repair, the modem registered on LTE but
ethermobile-data.service was still static and inactive. There was no epcell0,
no internet route and no active data session. The previously working downstream
adapter immediately restored real internet when started explicitly.

The data unit now requires and follows ethermobile-ipa, ModemManager,
NetworkManager and systemd-resolved. Its startup helper waits up to 120 seconds
for home-network registration, attached packet service and a disconnected
NetworkManager modem before allowing the dedicated WDS owner to connect.
Roaming is refused. The existing adapter's per-boot pipe allocation guards,
data cleanup and DNS management are retained. There is no automatic retry loop.

The service is enabled for multi-user.target, so mobile data now connects at
boot. This changes the previous manual-only policy as requested by the user.
The APN, credentials, firmware and Wi-Fi profiles were not modified. The Qt
application's stock NetworkManager connection buttons still use their existing
path; this change concerns the actual downstream internet service.

Deployment and verification
---------------------------

Run ``python scripts/install-ethermobile-data-start.py`` to install the helper
and unit, save previous files under /root/ethermobile-data-start-backup-* and
enable the service. Run ``systemctl disable --now ethermobile-data`` on the
phone to stop data and disable future boot connections.

Before reboot, three IP pings and three DNS-name pings succeeded without loss;
HTTPS explicitly bound to epcell0 returned HTTP 200. A stop/start cycle also
restored data and passed two IP pings. After reboot, run
``python scripts/verify-ethermobile-data-start.py``. Its report is
``evidence/ethermobile-data-start-reboot-2026-10-29.json`` and checks the changed
boot ID, enablement, connection state, supporting services, IP/DNS and HTTPS
bound to the real cellular interface.

Post-reboot acceptance passed all seven checks. Data connected automatically
with a new carrier-assigned IPv4 address, default route and DNS. IP ping
returned 3/3 replies and interface-bound HTTPS returned HTTP 200. DNS resolved
the hostname successfully; its ping returned 2/3 replies, so this verification
does not establish a loss-free radio link. The service was left active.
