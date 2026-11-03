EtherShare hardware audit and implementation
===========================================

Current acceptance: Wi-Fi recovered; LTE and AP remain blocked
-------------------------------------------------------------

The separately approved normal reboot completed. The user selected etherPocket,
and USB SSH returned with boot ID 46d7ed2f-bf16-4e08-b8ec-a06d40c6559d.
Wi-Fi-bound HTTPS passes; USB recovery DHCP and storage, NetworkManager,
ModemManager, BlueZ, SSH and EtherShare are active. The guarded existing IPA
initializer verified all ten vendor firmware files and initialized the packet
path once on this boot. ModemManager rediscovery followed the existing targeted
rmnet_ipa0 udev integration; its disconnected qrtr0 device became available.

The cellular owner reached DPM/WDS setup, but bounded session requests failed
with QMI CallFailed. Added credential-free numeric diagnostics identify call end
reason 1, verbose type 3 (CM), reason 1069 (esm-proc-timeout), using the installed
libqmi enum. No radio reset, APN change or automatic retry loop was applied.
Its failed session removed epcell0; LTE internet is not currently accepted.
No new invalid-pipe or WLAN-recovery kernel messages were found on this boot.

Fresh Windows Wi-Fi-to-USB traffic passes DHCP renewal, phone DNS resolution
and bound HTTPS 200. Independent Wi-Fi SSH was verified first. After stopping
sharing, Windows retained its prior gateway despite an ordinary renewal; an
adapter-specific release/renew removed it and USB SSH returned. Sharing is off,
forwarding is 0, no EtherShare firewall rules remain and autostart is false.
Hotspot quarantine remains pending driver stability validation. See
evidence/ethershare-current-acceptance.json, evidence/ethershare-post-reboot.json
and evidence/ethershare-post-reboot-wlan0-usb.json.

Earlier radio fault and recovery attempt
---------------------------------------

After repeated AP lifecycle testing, kernel logs report WLAN stuck in recovery
and rmnet IPA transmit failing with "pipe is not valid". Both phone internet
sources became unavailable, despite connected service metadata. Sharing
is off, IPv4 forwarding is restored to 0 and owned forwarding/NAT rules are gone.
USB SSH, its recovery DHCP and USB storage remain available. Hotspot starts are
quarantined in both the backend and UI; AP activation is not production accepted.
Earlier successful traffic tests below are historical results, not a claim of
currently working or sustained connectivity. See
evidence/ethershare-shared-radio-fault.json.

The installed vendor WLAN module is available and hash verified. The kernel's
rmnet source shows IPA endpoint setup is lost across subsystem recovery; the
existing owner's once-per-boot pipe marker can therefore become stale. A guarded
one-attempt runtime recovery procedure was executed with explicit user approval at
/var/lib/ethershare/radio-recovery/recover.py. Its review copy and manifest are
build/ethershare-radio-recovery.py and evidence/ethershare-radio-recovery-plan.json.
It requires the same boot, board, kernel, module hash and live USB recovery before
reloading WLAN and allowing the existing data owner to recreate invalid IPA pipes.
The existing data service stopped successfully, but WLAN unload blocked inside
hdd_module_exit waiting for firmware recovery. The driver logged "SSR never
completed, error" and remained in the kernel's uninterruptible sleep state.
The recovery coordinator was terminated before driver reload, saved Wi-Fi
activation or IPA marker invalidation. The one-attempt marker is retained;
the procedure must not be blindly repeated. See
evidence/ethershare-radio-recovery-attempt.json for the captured stack and state.

USB SSH, recovery DHCP and storage remain active; forwarding is 0 and no owned
firewall rules remain. The data service is stopped, and hotspot quarantine remains.
A normal systemctl reboot is proposed separately: its preflight confirms the
expected root filesystem, enabled USB recovery and disabled sharing autostart.
The existing boot menu requires physical selection of etherPocket using Volume
and Power, with no automatic timeout. The user approved the normal reboot; its
guarded preflight passed, sync completed and systemctl reboot was issued. SSH
disconnected, and a new boot was verified after the user's etherPocket selection.
No forced restart, firmware/partition
flashing or boot-menu changes are authorized.
See evidence/ethershare-reboot-preflight.json.
The unresolved LTE and AP stability issues mean the master task is not fully accepted.

Implemented and verified on the physical phone
----------------------------------------------

EtherShare 0.1.0 has a native Qt 6 management application, a serialized Python
system D-Bus service, dedicated PolicyKit authorization, existing EtherShell
Settings integration and Quick Settings controls. The graphical UI runs as
mobian. Credentials stay in root-only configuration and NetworkManager profiles;
password display is separately authorized and clears after 30 seconds.

Real Windows traffic succeeded for both LTE -> USB and Wi-Fi -> USB. The host
received 10.77.0.1 by DHCP, with gateway/DNS 10.77.0.2 during sharing. DNS queries
and interface-bound HTTPS were verified, with forwarding/NAT packet counters
on the phone. See evidence/ethershare-lte-usb-traffic.json and
evidence/ethershare-wifi-usb-traffic.json. Modem registration alone is never
treated as internet availability. The USB controller, product ID, RNDIS and
mass-storage links remained unchanged; both USB and alternate Wi-Fi SSH were
verified during DHCP migration. The timed rollback was cancelled only afterwards.

The phone successfully activated a WPA2 2.4 GHz AP on an owned virtual interface
alongside its existing Wi-Fi station, managed by NetworkManager. AP activation
and DHCP/DNS startup are verified; external wireless-client internet acceptance
still requires a connected client. Wi-Fi source and AP may share the radio only
where the driver actually accepts it. The separate replace-Wi-Fi action requires
an explicit warning/confirmation in the UI. Failed AP activation restores its
owned profile/interface where the driver permits cleanup. The later driver
recovery fault above supersedes any unconditional Wi-Fi-preservation claim.

When teardown returns EAGAIN, the controller keeps its down, unaddressed AP
interface and ownership marker rather than adopting another interface or
pretending deletion succeeded. Further hotspot starts are blocked pending
administrator recovery. The parked interface is not active sharing.

Seventeen policy tests and two EtherMobile cleanup tests pass. Real phone Settings
tests cover narrow 360x900, landscape 1000x600 and desktop 1920x1080 in both themes,
with route, geometry, search, keyboard and preference checks. The exact accepted
shell package is staged before per-user activation, with a rollback launcher.
The standalone application renders on ARM64, including a 1920x1080 desktop view.

Physical failure testing removed the active LTE interface while USB sharing was
enabled. Host traffic stopped while Wi-Fi stayed connected, proving that the
selected LTE source was not silently bypassed. LTE restoration restored HTTPS.
A forced sharing-controller crash was followed by journal cleanup, restored
forwarding=0, no remaining owned firewall chains and sharing left off. USB SSH
and foreign default routes survived. See evidence/ethershare-recovery-tests.json.
This is a controller/data-session recovery test, not a physical cable/reboot test.

An initial policy-routing defect also caught locally generated USB SSH replies.
The verified Wi-Fi channel recovered the session. The corrected rule uses an
incoming-interface selector as well as source subnet, and the regression test
requires it. Local USB recovery replies retain their connected route.

The existing EtherMobile data helper had a teardown defect: an unsuccessful
StopNetwork reply skipped Linux interface deletion. A subsequent restart refused
the stale epcell0 interface. Its cleanup now removes only its own created child
before waiting for modem confirmation, and independently releases every client.
The one existing orphan was verified as the exact rmnet_ipa0/mux-1 child while
the owner process was stopped before removing it. The original script remains
backed up as ethermobile-ipa-data.py.before-ethershare-cleanup. Unit tests exercise
failed modem replies and preservation of an interface not created by this owner.
Normal data-session stop/start was then verified on hardware. No modem, QRTR,
firmware subsystem, radio or NetworkManager reset was used as a repair.

Interface inventory, explicit/automatic upstream selection and configurable
priorities are implemented. Connectivity probes are small, bounded HTTPS checks
bound to the candidate interface. Failover is opt-in, and strict egress plus a
terminal unreachable policy route prevent fallback through main. IPv6 forwarding
from sharing interfaces is explicitly blocked. A stopped downstream retains a
drop guard while another sharing method still needs forwarding. Rules are owned
and scoped; unrelated tables/chains are never flushed. Failover updates only
owned forwarding/NAT chains while retaining input protection.

DHCP subnet selection checks all existing routed networks and other shares.
Hotspot/Ethernet DHCP range and lease duration are configurable; USB preserves
the single-host recovery subnet. DNS forwarding uses the selected source's
servers and interface, with no silent public-DNS fallback. Active VPNs require an
explicit policy. VPN-only traffic is guarded on loss, but no real VPN endpoint
was available for acceptance. The default policy requires a decision.

The UI distinguishes configuration, pending operations and effective state. It
reports USB enumeration from discovered UDCs, active methods, addresses, DNS,
interface totals/rates, DHCP leases and real AP station data when present. Local
device names can be edited or cleared. Leases are not presented as proof that a
client is online. Forced client disconnect/block and USB/Ethernet per-client
counters are not certified. Notifications report sharing transitions, failures
and associated stations or lease presence using the existing shell service.

Not accepted yet: external hotspot-client traffic, Ethernet adapter traffic,
Linux/macOS USB hosts, NCM, physical unplug/replug, suspend/resume, reboot,
real VPN forwarding and total device power consumption. Bluetooth PAN and ECM
require kernel changes on this build. No kernel or Android partition was changed.
These limits must remain visible; this is not acceptance of every master-task
requirement or an unconditional production-readiness certification.

Short performance samples
-------------------------

Ten-second samples during UI QA measured controller CPU use of 1.389% idle,
2.577% during LTE/USB configuration and 2.876% during LTE/AP configuration,
expressed as a percentage of one CPU core. These are short samples under test
activity, not sustained-load or battery-life benchmarks. The battery reported
Full while USB powered, so its current/voltage cannot establish total device
input watts. An external meter is still required. Raw sensor samples are in
evidence/ethershare-device-validation.json; no approximately-2-W claim is made.

Recovery and maintenance
------------------------

The generic package installs the idle service and native application. Autostart
defaults off; only an explicitly saved USB autostart preference is honored.
The device-owner rule and USB recovery migration are separate guarded deployment
steps. USB migration artifacts and the rollback program are in
/var/lib/ethershare/usb-migration. To undo that migration after stopping sharing,
use its rollback.py with a verified alternate SSH channel. It restores the
original service command without unbinding the existing gadget.

Stopping sharing withdraws DHCP router/DNS options without dropping USB SSH.
Some Windows leases retain their old gateway until renewed/reconnected; the UI
states this limitation. Firewall/routing guards prevent that stale gateway from
continuing to share through another active method. Preferences are at
/var/lib/ethershare/config.json (0600); the transactional cleanup journal is
active.json. Do not delete the journal to bypass incomplete cleanup.

Relevant primary API references: https://networkmanager.dev/docs/api/latest/settings-ipv4.html
and https://networkmanager.dev/docs/api/latest/settings-802-11-wireless.html.
Kernel/hardware acceptance is based on the local audit and traffic tests.

Initial read-only audit
-----------------------

The physical GM1920 has a configured RNDIS gadget with a mass-storage function.
usb0 carries the existing 10.77.0.2/24 SSH recovery connection; its host receives
10.77.0.1 from BusyBox udhcpd, with no default gateway. Both gadget services own
this configuration. NetworkManager explicitly leaves usb0 unmanaged. EtherMobile
owns epcell0 through its existing WDS/IPA service. NetworkManager owns wlan0.
No second interface manager should take ownership of either existing service.

==================== ====================== ==================================
Capability           Classification         Evidence / limitation
==================== ====================== ==================================
USB RNDIS            Supported              Enumerated on Windows, existing SSH
USB NCM              Not yet verified       Kernel config enabled, not bound
USB ECM              Requires kernel changes CONFIG_USB_CONFIGFS_ECM disabled
IPv4 legacy NAT      Requires configuration Legacy tables readable, NAT built in
nftables             Requires kernel changes CONFIG_NF_TABLES disabled
Wi-Fi AP             Not yet verified       Driver advertises AP, eight stations
STA + AP             Not yet verified       Advertised combinations, not tested
WPA2                 Not yet verified       CCMP advertised, live test required
WPA3                 Not yet verified       SAE advertised, live test required
Bluetooth PAN        Requires kernel changes CONFIG_BT_BNEP disabled
Ethernet downstream  Not yet verified       No physical adapter on phone
IPv6 sharing         Unsupported in release No delegated prefix / verified setup
VPN sharing          Not yet verified       No active test VPN
==================== ====================== ==================================

Wi-Fi has usable 2.4 GHz channels, while many 5 GHz channels prohibit initiating
radiation or require radar detection. The first hotspot mode therefore uses
2.4 GHz WPA2. Regulatory restrictions must remain enforced by NetworkManager.
The kernel supports legacy iptables and masquerading; the installed default
iptables wrapper selects nft and fails. EtherShare must explicitly invoke
iptables-legacy, without changing global alternatives or flushing other rules.

NetworkManager, ModemManager, EtherMobile data, BlueZ and SSH are active.
systemd-networkd, standalone dnsmasq and hostapd are inactive. dnsmasq is installed.
Python D-Bus and GLib are available. Original audit evidence is saved in
evidence/ethershare-audit-2026-10-19.json. No network changes preceded this audit.

USB DHCP integration plan
-------------------------

Retain the existing gadget, addresses and mass-storage function. Replace only
the recovery service's DHCP command, using a reviewed copy of its existing
initialization, with dnsmasq. Preserve its single-host recovery lease and use a
reloadable DHCP options file to advertise a gateway/DNS only during sharing.
An independently verified Wi-Fi SSH channel and on-device timed rollback must
exist before this migration. Service dependency effects must be checked. The
generic application package must not migrate the board's recovery service.

NetworkManager remains responsible for Wi-Fi AP activation and profile storage.
Manual IPv4 configuration is intentional: this kernel cannot use NM's default
nft shared firewall, and strict upstream selection requires owned policy routing
and firewall guards. One scoped dnsmasq instance supplies DHCP/DNS per ordinary
downstream; USB reuses the migrated recovery DHCP owner. No DHCP servers may
compete on an interface. Sharing is IPv4 only with an explicit IPv6 forward block.

Host lease cleanup note
-----------------------

Windows accepted the test USB router/DNS options. An attempt to remove only its
temporary USB default route was denied by Windows permissions. The recovery
address was preserved, and the lease was not deliberately released while phone
Wi-Fi was unavailable. Renew/reconnect that lease after a verified alternate
phone recovery channel is restored. Other Windows uplinks still passed HTTPS.
This cleanup was subsequently completed after the approved reboot: verified
alternate Wi-Fi SSH, released and renewed only Ethernet 4, confirmed 10.77.0.1
returned and the USB default route was absent, then verified USB SSH.

Latest shell staging status
---------------------------

After the approved reboot, the last safety-label shell passed all three isolated
acceptance sizes: narrow, landscape and external, including both themes. The
exact accepted stage /opt/ethershell2/2.1.0-share-ce4541d4d1d2 was activated using
the guarded launcher migration. The previous launcher is retained for rollback;
the live Settings route was verified as sharing. The earlier landscape/external
timeouts did not recur on the fresh boot. See evidence/ethershare-shell-stage.json
and evidence/ethershare-shell-deployment.json. All 17 policy tests and both
cellular cleanup tests pass. The installed ARM64 package also includes the numeric
cellular diagnostics and a hotspot warning that accurately describes quarantine.
