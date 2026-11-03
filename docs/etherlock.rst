EtherLock engineering implementation
===================================

Status: staged; automatic locking disabled pending attended acceptance.
This is not a completed Task 06 hardware security release.

Trust boundary
--------------

Debian XSecureLock owns keyboard/pointer grabs, root/composite coverage and
RandR handling. EtherLock's Qt6 authentication child is embedded below its
authentication window. The child exits successfully only after its fixed-service
PAM helper authenticates the current Unix user AND passes pam_acct_mgmt.
Crashing/cancelling the authentication child does not authenticate. No public
Unlock method or authentication-success signal exists. A UI-only preview is
never treated as a lock. The coordinator waits for XSecureLock's post-grab,
mapped-and-visible acknowledgement before reporting enforcement.

X11 clients and processes belonging to the same user are trusted. They can
inspect/interfere with each other; a malicious same-user application can kill
the locker. The audited phone also grants mobian NOPASSWD: ALL sudo, making
same-user compromise equivalent to root compromise. This implementation does
not remove that development/recovery privilege. Root, kernel compromise,
X server termination, VT/boot access and offline storage are outside screen
lock protection. Android-equivalent isolation is not claimed.

XSecureLock upstream is archived; Debian supplies version 1.9.0. This reuses
reviewed enforcement code but is not evidence of ongoing upstream maintenance.
Release requires a security-maintenance decision and device acceptance.

Authentication policy
---------------------

Only the existing Linux account credential is enabled. Numeric keypad input is
an input layout, not an independent PIN. A separate PIN, minimum-length
enrolment and PIN changes are unavailable rather than storing a shell-local
hash or weakening the Linux password. Use passwd through an existing trusted
terminal to change account credentials. Password expiration/account restrictions
fail closed. Empty passwords are refused. No setuid helper is introduced.
The platform's PAM/unix_chkpwd handles privileged credential verification.

The dedicated /etc/pam.d/etherlock stack has a two-second PAM failure delay,
five-attempt limit over 15 minutes and a 120-second temporary lockout through
pam_faillock. These controls live in PAM, survive authentication child and
coordinator restarts and never delete data. Progressive delays are not yet
implemented. PAM auth events use authpriv without secret or module message
text. The coordinator stores at most 1000 event names/timestamps in a private
SQLite file; export contains no notification text, credentials or contact data.
Root journal retention follows the existing system journal policy.

Qt/PAM conversation strings necessarily have transient memory copies. Core
dumps are disabled and input buffers are cleared after submission/failure;
complete forensic memory erasure of Qt's implicitly shared allocations is not
claimed. External keyboard input supports the locker forwarding protocol;
touch keyboard supports ASCII letters/digits/symbols. The trusted auth child observes XI2 raw pointer events and delivers local Qt mouse events inside its own window; it never releases the locker grab or uses XTest to inject input into other X11 clients. Physical touch-to-pointer emulation still requires device acceptance. Unicode input and physical
touch/hotplug acceptance require device tests.

Deployment and recovery
-----------------------

1. Build with scripts/build-etherlock.sh in EtherPocketBuild. Install the Debian
   ARM64 package without enabling a user unit or automatic locking.
2. Keep a separate root SSH connection open. Independently reconnect over USB
   and Wi-Fi, verify device identity, and test administrator recovery commands.
3. Record root-owned /etc/etherlock/validation.json with current bootId and hashes
   for all files in core.FILES. Set recovery=true ONLY after successful
   independent recovery tests. Use etherlock-validate --recovery through that administrator channel. This permits an attended manual Lock request.
4. Start the unit as mobian with DISPLAY, XAUTHORITY and the existing session bus
   imported into the user manager; do not create a new login or display.
5. Test wrong/correct credential, repeated unlocks, child crash and coordinator
   restart, screen off/wake, external keyboard and every active output/hotplug.
   Do not use production authentication secrets in scripts or chat.
6. Test power/suspend only after EtherPower's separate hardware wake gate passes.
   Suspend remains blocked by EtherLock while enabled. An expiring delay inhibitor
   cannot veto failed locking; no resume protection claim is made.
7. Only an administrator may attest authentication, repeatedUnlock, recovery,
   screenOff, resume and externalDisplay as true for this boot/build. Configure
   enabled=true is refused until all pass. A changed boot or executable/PAM hash
   invalidates the evidence. Revalidation after reboot is intentional at this
   engineering stage; unattended mandatory lock startup is not shipped.

If the UI fails, use the verified independent root SSH channel. Inspect
``pgrep -u mobian -a xsecurelock`` and ``journalctl -t etherlock-auth``.
Stopping/restarting etherlock.service deliberately leaves the locker alive
(KillMode=process). A restarted coordinator with an active marker reports
unknown/private, never unlocked. Repair the authentication component while the
locker remains active and retry. If administrator recovery must forcibly remove
the locker, explicitly terminate only its verified PID through that root SSH
session, then remove /run/user/1000/etherlock-active and restart the coordinator.
That is a privileged forced recovery, not an authentication success; record it
in the system journal using logger -p authpriv.notice. Restore/retest the build
before reattesting. No master PIN or unauthenticated recovery command exists.
Do not restart LightDM/Xorg or reboot to recover without saving protected work.

APIs and integration
--------------------

Session D-Bus com.etherneco.EtherLock1, /com/etherneco/EtherLock1:
GetState() -> JSON; Lock(reason) -> bool acknowledgement; Configure(JSON) -> JSON;
ExportEvents() -> JSON; Changed(JSON). Only the session uid may call methods.
There is no Unlock or public success callback. locked is the privacy-required
state; enforced is separate and only true after locker acknowledgement.
Applications must hide sensitive controls in locking/locked/fault/unknown states.
Same-user D-Bus impersonation is within the documented X11 trust limitation.

EtherShell Security & Privacy uses the existing Settings component system.
The sole existing Media power handler requests enforcement before explicit
blanking when automatic policy is enabled. X11 idle locking is monitored by the
coordinator. Display blanking alone never constitutes proof of authentication
locking. The hardware software-blank wake workaround is preserved.

Notifications are hidden by the opaque locker; no preview content is supplied
to the auth child in this release. Existing EtherNotifications privacy modes
remain available in its settings. Calls, emergency calling and fingerprint
controls are deliberately absent from authentication: the telephony backend
has no verified cellular call/audio path and fingerprint support is unverified.
No call action unlocks the device. Locked incoming-call interaction, power menu,
battery/network UI, notification previews and EtherTrust adapters are outstanding.
SSH is neither disabled nor disconnected. Remote administrative controls retain
their own authorization policies. No certificate material reaches this UI.

Encryption assessment
---------------------

The live root is ext4 on /dev/sda21, without a dm-crypt/LUKS mapping. A screen
credential does not protect these files against offline extraction. Android and
bootloader partitions remain separate and untouched. LUKS feasibility needs a
separate migration plan: verified full backup/restore, boot/initramfs crypto
support, touch/USB unlock input, kernel dm-crypt support, key custody and recovery
boot acceptance. No encryption, repartition, boot change or key enrolment occurs.

Primary references
------------------

* https://packages.debian.org/trixie/xsecurelock
* https://github.com/google/xsecurelock (README/security design and main.c)
* https://github.com/linux-pam/linux-pam (pam_faillock and application API)
* https://www.freedesktop.org/software/systemd/man/latest/org.freedesktop.login1.html


Audit on 20 October 2026
------------------------

Evidence: evidence/etherlock-audit.json, etherlock-audit-extra.json,
etherlock-security-boundaries.json and etherlock-recovery-channels.json.
The active session is c1, uid 1000 mobian, seat0/VT7, type x11. Root-owned Xorg
uses -nolisten tcp and LightDM authority; xhost access control is enabled with
SI:localuser:mobian. LightDM's 95-etherpocket-ramtest.conf enables immediate
autologin into XFCE. XFCE starts the unprivileged staged EtherShell launcher.
The existing PolicyKit agent is polkit-mate. EtherPower and EtherShare system
services are root-owned; EtherHardware runs as etherhardware. Their own D-Bus
and PolicyKit boundaries remain intact. SSH allows root public-key access,
prohibits root password login and permits non-root password authentication.
Passwordless sudo for mobian and autologin are security release blockers,
particularly because restarting Xorg/LightDM/rebooting could reopen the session.
No statement here treats an existing authenticated SSH connection as a local
unlock. Fresh key-authenticated USB and Wi-Fi reconnections both pass.
The console login service exists, but physical local-terminal recovery was not
exercised during this task. USB recovery, Android and bootloader history exists
in earlier project evidence; none was reboot-tested during this task.

The current output is DSI-1, 1440x3120, one logical monitor. Physical EtherAIR
hotplug is not connected and is untested. The coordinator refuses X servers with
multiple independent roots rather than partially locking a Zaphod configuration.
RandR multi-monitor support comes from XSecureLock, not shell window stacking.

/sys/bus/platform/devices/soc:goodix_fp advertises goodix,fingerprint and
soc:fingerprint_detect advertises oneplus,fpdetect. These are kernel device-tree
nodes, not evidence of a working libfprint enrollment or secure authentication
path. fprintd is absent; no verified user-space driver, firmware path or template
storage has been established. libfprint's development support list is primarily
USB/SPI device/driver specific and does not establish support for this platform
node: https://fprint.freedesktop.org/supported-devices.html . Biometrics remain
unavailable. No fingerprint acquisition or enrollment was attempted.
