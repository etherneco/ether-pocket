EtherCredentials architecture audit — 2026-11-03
================================================

Repository evidence
-------------------
* etherlock/service.py coordinates the existing user session; XSecureLock owns
  input capture and enforcement. Only successful auth-module exit permits unlock.
* etherlock/auth.cpp embeds Qt in the XSecureLock parent, launches etherlock-pam,
  and requires both a successful result and successful process exit.
* etherlock/pam.cpp fixes PAM service and account from the real UID;
  packaging/etherlock.pam uses pam_unix, pam_faillock and common-account.
* config/90-etherpocket.conf selects LightDM and an XFCE session.
  scripts/stage-ramboot-rootfs.sh additionally enables ram-test autologin.
  Effective installed LightDM/PAM configuration must be inspected on the device.
* EtherLock uses logind, systemd user services and a per-build/per-boot acceptance
  gate. It blocks suspend pending hardware acceptance. Preserve those gates.
* etherfingerprint/core.py is diagnostic-only: secure transport/enrollment and
  verification are unavailable. Biometric choices must remain unavailable.
* Existing EtherLock stores policy and non-sensitive events, no separate PIN.
  Its policy is user writable; it is not a privileged policy enforcement boundary.

Authentication boundaries
-------------------------
Boot/storage: no pre-boot authentication is implemented here. Existing EtherLock
reports unencrypted ext4. A short PIN hash remains vulnerable to offline guessing;
Argon2id and online delays cannot protect a copied verifier. No hardware secret
protection has been established.
Graphical login: LightDM PAM, independently of screen credentials. Autologin
starts the session before screen authentication and is not equivalent to login.
Session unlock: XSecureLock -> EtherLock auth module -> trusted verifier/PAM.
Privilege: existing system Polkit/PAM rules, never the screen PIN.
Biometrics: unavailable; primary PIN/password or Debian password remains required.
Account password: existing PAM password management, never shadow writes.

Implementation and acceptance boundary
-------------------------------------
The new root Unix socket uses kernel peer UID, fixed operations and a root-owned
SQLite store. Secrets travel only over local Unix socket or PAM conversation
pipes, never D-Bus, argv or environment. Every modification requires the Debian
account credential. Screen credentials never replace that recovery credential.
No generic shell, reset endpoint, UnlockSession method or new locker is added.
Each request is self-contained; there are no bearer tokens or cached authorization.
Socket requests are serialized with time and size bounds. Retry reservations are
committed before authentication, surviving process death and service restart.

Device acceptance must verify effective PAM/LightDM, account expiry, power/resume,
service interruption, permissions, Qt rendering and independent SSH recovery.
No Android partition, LightDM, SSH, global PAM or mandatory-lock setting is changed.
Fingerprint, autologin editing, protected global locking policy, notification and
Settings integration remain outstanding. Packaging is preparation, not publication.
