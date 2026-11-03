EtherMobile hardware baseline — 2026-10-18
=========================================

Current verified status after approved startup and SIM insertion
---------------------------------------------------------------

The user explicitly approved the one-shot IPA startup and then inserted a SIM.
The exact startup write completed once. Kernel logs confirm IPA firmware loaded,
IPA driver initialization succeeded and rmnet_ipa completed initialization.
The real raw-IP interface rmnet_ipa0 (ARPHRD 519) now exists. NetworkManager,
SSH, Bluetooth and the modem service remain active, and Wi-Fi stays connected.
Evidence: ``evidence/ethermobile-ipa-initialize-2026-10-18.json`` and
``evidence/ethermobile-after-ipa-2026-10-18.json``.

This vendor driver creates rmnet_ipa0 under /devices/virtual/net without a driver
ancestor, so upstream ModemManager's DRIVERS==ipa udev rule cannot associate it.
``config/78-mm-ethermobile-gm1920.rules`` matches only that exact real path and
raw-IP type and supplies the existing qcom-soc association. The board-checked
``scripts/integrate-ethermobile-ipa-port.py`` installed it and triggered only this
network device. No daemon or shared subsystem restart was needed. ModemManager
then exported /Modem/2 with qrtr0 (qmi) and rmnet_ipa0 (net). NetworkManager
exposes qrtr0 as a GSM device and automatically enabled its radio.

The inserted SIM's USIM application is present and ready. PIN1 is disabled;
PIN2 being unverified is not a request for the ordinary SIM PIN. The SIM reports
giffgaff, home PLMN 23410 (O2 UK), active slot 1. Identifiers and telephone
numbers are not exposed in reports. The app now shows real signal quality and
modem/SIM state. A live-modem render test exposed a Qt D-Bus structure-reading
bug; the read-only QDBusArgument is now const, and all three phone UI tests pass
with the real modem and SIM present.

LTE registration remains blocked: NAS reports limited-regional, no normal
service domain, packet detached and reject reason
no-suitable-cells-in-location-area. A signal reading or an operator name is not
registration. The user reports SIM activation about 20 minutes earlier.
Pending carrier provisioning is plausible, not proved by this reject code.
giffgaff's official troubleshooting guidance says new service may take from
30 minutes and, rarely, up to 24 hours to fully connect:
https://help.giffgaff.com/en/articles/639659-network-service-troubleshooting

The carrier profile is prepared from the official APN/PAP settings at
https://help.giffgaff.com/en/articles/245215-internet-apn-settings-guide
and stored by NetworkManager with file mode 0600. Roaming, autoconnect and
default-route takeover are disabled. Credentials are not printed in evidence.
No data session has been activated. The user's latest steering requests reading
the SIM and detecting the operator; data activation is not inferred from that.
Evidence: ``evidence/ethermobile-giffgaff-profile-2026-10-18.json`` and
``evidence/ethermobile-after-sim-2026-10-18.json``. A safe allowlisted live
summary can be collected with ``python scripts/probe-ethermobile-state.py``.

The kernel now demonstrably supports modem/IPA initialization and a real net
port. Working cellular IP traffic is still unverified. WDA data-format queries
return InvalidArgument (without endpoint and with embedded endpoint 1); the
upstream qcom-soc bearer code also selects IPA/BAM-DMUX by driver name, whereas
this vendor netdev has no driver ancestor. No driver spoofing, guessed WDA
configuration or unverified ModemManager patch has been applied. Bearer/packet
configuration remains a separate integration gate after registration succeeds.

Startup is deliberately a one-shot runtime test, not an enabled boot service.
Cold boot, reconnection, end-to-end cellular DNS/internet and 5G remain untested.
The udev association and copied firmware persist; automatic IPA startup does not.
Existing Wi-Fi profiles and Android/calibration partitions remain unchanged.

Original read-only baseline before initialization (historical)
-------------------------------------------------------------

The actual phone was inspected over the project's pinned USB SSH connection.
The host is Debian 13.7 ARM64, kernel 4.14.117-perf #6. No kernel, boot image,
Android partition, radio configuration, subsystem power state or network
configuration was changed for this audit. The user confirmed no SIM is inserted.

Cellular internet is NOT working. The current kernel has a working QMI-over-QRTR
control plane, but no cellular network interface. ModemManager 1.24.0 discovers
qrtr0 and selects qcom-soc, then rejects it with "Failed to find a net port in
the QMI modem". Whether this kernel can carry cellular traffic remains unverified;
the evidence does not justify declaring the whole kernel unsupported or working.

Evidence: ``evidence/ethermobile-audit-2026-10-18.json``, collected by
``python scripts/audit-ethermobile-device.py``. The Doctor can also run directly
on the phone: ``python3 ethermobile-doctor.py --output NEW-REPORT.json``.
Reports use exclusive creation and mode 0600. Queries have bounded timeouts;
missing commands and paths produce Unknown/Missing instead of invented results.

Hardware identity discrepancy
-----------------------------

The task assumes the LTE-only OnePlus 7 Pro. This workspace's previous Android
discovery instead identified GM1920 / OnePlus7ProNR. Today's live device tree
reports ``SDX50M MTP 18827 15``, SoC 339/SM8150; the command line includes
project 18827 and baseband mdm. Therefore an LTE-only retail model must not be
assumed. QMI DMS returns model "0", which does not identify a retail modem SKU.
An external esoc0 subsystem exists and is OFFLINING. Its working state, firmware
and data transport have not been established. Neither X24 nor working X50/5G
is established merely by the SoC name or the device-tree label.

QMI advertises cdma20001x, evdo, gsm, umts, lte and 5gnr. This is firmware
capability metadata, NOT a claim of working NR, an active NR radio or a tested
5G data connection. No 5G-only control is enabled on that basis.

Verified subsystem assessment
-----------------------------

* Hardware/control: Working. Modem subsystem ONLINE, /dev/subsys_modem present.
  QRTR node 0 exposes DMS, NAS, UIM, WDS, WDA, DPM, IPA and other services.
  DMS revision is MPSS.HE.1.5.3.c1-00017-SM8150_GENFUSION_PACK-1.299167.1.399259.3
  (May 16 2021). The firmware responds to real read-only queries.
* Kernel: Partially working. QRTR, QRTR_SMD, QRTR_MHI, QRTR_FIFO, RMNET,
  IPA3, RMNET_IPA3, MHI_BUS, MHI_QCOM, MHI_NETDEV, MHI_UCI, QCOM_QMI_HELPERS,
  QCOM_GLINK and MSM_SUBSYSTEM_RESTART are built in. CONFIG_REMOTEPROC,
  CONFIG_USB_NET_QMI_WWAN and CONFIG_RMNET_DATA are disabled. This downstream
  platform uses msm_subsys, so absent mainline remoteproc is not proof that
  the modem cannot boot. lsmod alone would miss the built-in drivers.
* Firmware: Partially working. Copied modem firmware is available in Linux and
  its control plane responds. No ipa_fws* or ipa_uc* files were found in
  /lib/firmware. ipa_fws subsystem reports OFFLINING. This is a verified gap
  in the currently inspected firmware directory, not proof that suitable
  firmware is absent from the original device or every possible search path.
* Packet path: Blocked. IPA and rmnet_ipa3 platform devices are bound, /dev/ipa
  exists, but there is no rmnet/wwan/MHI network device. Binding does not
  establish that initialization completed. Existing IPA IPC logs also show
  DMA allocation failures while configuring WLAN offload; causality for the
  cellular failure is not established.
* SIM: Blocked. User confirms no SIM. UIM slot 1 reports error:no-atr-received;
  provisioned applications do not exist. Uninitialized zero PIN/PUK counters
  must not be presented as remaining retries. Slot switching and dual-SIM
  operation are unverified; eSIM is unverified.
* Radio: Blocked. DMS reports shutting-down, hardware restriction no. This
  differs from the kernel modem subsystem being ONLINE: firmware being up
  does not imply the cellular radio is online.
* Registration: Blocked. NAS not-registered-searching, CS/PS detached, no
  selected radio interface or serving service. No signal value is fabricated.
* Data session: Blocked. WDS disconnected. No cellular IP, route, DNS or
  external access is verified. Wi-Fi connectivity is not cellular evidence.
* Services: Working for the existing setup. ModemManager, NetworkManager,
  QRTR namespace, rmtfs, pd-mapper, tqftpserv and etherpocket-modem are present.
  oFono is not needed for this selected backend; installing competing modem
  control stacks is not proposed. Package availability is in the report.
* SMS/voice/IMS/VoLTE/hotspot: Unknown or blocked by the prerequisite stack.
  Service advertisement does not establish send/receive, call audio, IMS
  provisioning, AP mode or sharing support. No SMS, calls or sharing performed.

Device-specific initialization investigation
--------------------------------------------

The matching local vendor kernel source at
``/opt/etherpocket/kernel/drivers/platform/msm/ipa/ipa_v3/ipa.c`` contains
ipa3_write(), ipa3_load_ipa_fw() and ipa3_post_init(). Userspace writes to
/dev/ipa can schedule firmware loading and post-initialization; non-MSM
platforms distinguish MHI mode. rmnet_ipa.c:ipa3_wwan_probe() explicitly
registers a ready callback when IPA is not initialized, before creating the
network device. This provides a plausible initialization path to investigate,
not permission to blindly write "1" or "MHI" to /dev/ipa.

Next integration gates:

1. Inspect this exact device's original vendor init rules and firmware names
   read-only, establish platform type, IPA/MHI mode and required userspace
   dependencies. Use only firmware from this device or verified matching
   vendor releases. Record hashes and provenance before copying into Linux.
2. Resolve the observed IPA DMA/SMMU allocation failures and assess whether
   userspace initialization can succeed with the existing kernel. A kernel
   change requires a separate engineering proposal, matching ABI/signing,
   explicit deployment authorization and recovery plan. No force-loading.
3. Validate an IPA startup action without stopping the modem or its WLAN
   protection domain. Stop if the existing Wi-Fi/SSH connection is threatened.
   Do not bypass initialization by creating a dummy net port for ModemManager.
4. Establish a real net port, correct QRTR/udev association and qcom-soc
   provider acceptance. Generic USB QMI/MBIM/AT procedures do not establish
   support for this downstream integrated modem.
5. Insert a user-supplied working SIM. Enable the radio only as an explicit
   operation, verify SIM/PIN status, then register without guessing credentials.
6. Use a trusted carrier APN or user-entered APN in NetworkManager; default
   roaming off, autoconnect off, cellular route priority below existing Wi-Fi.
   Verify bearer, real interface, IP, route, interface-bound DNS and external
   connectivity, disconnect/reconnect, then check Wi-Fi/Bluetooth/SSH.

Preservation constraints
------------------------

The existing modem service supports WLAN. Do not restart shared Qualcomm
subsystems, NetworkManager, QRTR or firmware services as a generic repair.
The current rmtfs override uses -r -P, preserving NV writes in RAM; do not
remove that safeguard. No EFS, modemst1, modemst2, persist, boot, bootloader
or calibration partitions may be modified by EtherMobile. Airplane mode
requires coordinated EtherShell policy; global rfkill is not an implementation.

Implementation and firmware staging
------------------------------------

The baseline above predates application installation and firmware staging.
EtherMobile 0.1.0 is installed on the physical phone. The desktop-user Qt 6/QML
GUI uses asynchronous system D-Bus calls and property events. The XDG entry
and Diagnostics action integrate with EtherShell's existing application
discovery. Full Quick Settings/airplane-mode integration is pending. All nine
requested navigation sections explain available or unsupported functionality.

Read-only debugfs inspection of vendor_b (without -w, mount or journal replay)
found /etc/init/ipa_fws.rc, whose post-fs action writes 1 to /dev/ipa. IPA firmware
is in /firmware in that same vendor partition. Sizes, SHA-256 hashes, init
definitions and source are recorded in
``evidence/ethermobile-vendor-2026-10-18.json``. No vendor code is executed.

``scripts/ethermobile-ipa-init.py`` defaults to read-only preflight. Its --stage
operation copied exactly ten verified ipa_fws/ipa_uc MDT/segment files into
/lib/firmware on the Linux root filesystem. It checks board identity, kernel,
original startup-rule hash, services and every firmware hash, and refuses
symlinks or conflicting firmware. Staging does not trigger IPA startup or write
Android partitions. See ``evidence/ethermobile-ipa-stage-2026-10-18.json``.
Firmware availability is improved; firmware loading and packet initialization
remain unverified. The missing-network-port blocker remains.

The separately opt-in --initialize action writes the vendor's byte to /dev/ipa
once per boot, guarded by an exclusive /run marker. It requires staged hashes,
modem ONLINE, IPA OFFLINING and no cellular port. It performs no reset, radio
enable, module load or reboot. At this staging checkpoint it had not yet run;
it subsequently completed after explicit approval, as described above.
Confirmation was requested under the task's Phase 1 disruptive-operation rule: IPA/WLAN share
hardware with observed DMA allocation errors, so kernel instability or a Wi-Fi
interruption is a material risk. No timeout counts as approval.

Validation and acceptance limits
--------------------------------

Native amd64 and cross ARM64 builds succeed. Policy tests pass on host and
phone. Python Doctor tests cover identifier redaction, missing tools, no-ATR
handling and avoiding false registration success. The phone loads the GUI as
mobian, collects twelve diagnostic stages without root and renders Pocket light,
Diagnostics and 1920x1080 dark screenshots without QML warnings. Offscreen
rendering does not prove physical touch or glasses output. Root GUI is refused.

Installation uses a dpkg dry-run and transfer SHA-256 verification. Before/after
records confirm Wi-Fi remains connected and NetworkManager, SSH, Bluetooth and
modem services remain active. No service restart, reboot or cold-boot test was
performed. Active Bluetooth service is not new pairing/audio acceptance.

The real NetworkManager suite checks unprivileged denial without a PolicyKit
agent and separately runs a QCoreApplication profile lifecycle as administrator.
This is not a root GUI or installed helper. It creates a disposable .invalid
APN with autoconnect off and never-default on, checks stored settings, edits and
deletes it. It also checks preservation of a generated test secret. No profile
is activated and no carrier credentials are invented. Final test exit codes
and unchanged-active-connections results are in
``evidence/ethermobile-acceptance-2026-10-18.json``. Interactive desktop PolicyKit
authentication still needs acceptance with a visible agent.

Final automated acceptance passed: policy on amd64 and ARM64, all three Python
Doctor tests, the real NetworkManager authorization-denial and administrator
profile/credential lifecycle, and all three phone UI render checks. No test
cellular profile remained after the lifecycle, and active NM connections were
unchanged. Screenshots are ``evidence/ethermobile-pocket-device.png``,
``evidence/ethermobile-doctor-device.png`` and
``evidence/ethermobile-desktop-dark-device.png``.

Milestone 1 has an evidence-based baseline and concrete runtime blockers.
Milestone 2 subsequently gained successful approved IPA startup, a real netdev
and a usable exported MM modem. SIM reading is verified after insertion;
registration and internet remain blocked/unverified as detailed at the top.
The UI/backend/package
foundation is installed; connection controls remain hardware-unaccepted. SMS,
voice/VoLTE, hotspot, usage history, reconnection, suspend/resume, full SIM
administration, network/mode selection, Quick Settings and release regression
tests are not complete. No tested 5G support is claimed.

References
----------

* https://modemmanager.org/docs/modemmanager/wwan-device-types/
* https://modemmanager.org/docs/modemmanager/port-and-device-detection/
* https://www.freedesktop.org/software/ModemManager/api/latest/gdbus-org.freedesktop.ModemManager1.Modem.html
* https://networkmanager.dev/docs/api/latest/settings-gsm.html

Upstream support describes interfaces, not acceptance of this particular
4.14 vendor kernel. Local source inspection and device results take precedence
over assumptions based on generic supported-device lists.
