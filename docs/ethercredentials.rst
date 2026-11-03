EtherCredentials development status
===================================

This is a verifier foundation, not completion of Master Task 14. The development package was installed on GM1920 on 2026-11-03. The verifier
service is enabled and active; unprivileged diagnostics and restart were checked.
Ten installed-source tests passed on ARM64. SSH remained active. No production
lock method changes, device login, or publication occurred.
Native Qt Settings/keypad/password management, Debian password changes, protected
lock policy, trusted fingerprint support, notifications, and device acceptance
remain outstanding. The account password can authenticate/recover but cannot be
changed through this implementation. Use the existing interactive passwd tool.

Deployment and recovery
-----------------------
Build the DEB with CMake/CPack on Debian; it depends on python3-argon2 and EtherLock.
The service is deliberately not enabled by package installation. First inspect
root ownership of /usr/share/ethercredentials and /var/lib/ethercredentials, verify
independent SSH and physical recovery, then start ethercredentials.service in a
controlled test session. Run ethercredentials status, set pin, set password,
prefer pin/password/system, or remove pin/password interactively. Every mutation
requires the Debian password. Password input uses getpass; never pass it in argv.
Changing preference keeps both enrolled screen credentials. Debian PAM remains
independent. No-lock and biometric-only methods are unsupported.

Recovery uses the unchanged Debian account password and SSH. Retry reservations
survive crashes; wait up to five minutes after repeated failures. Do not delete
the database to bypass a lock. Administrative recovery must first establish
account ownership via the existing system recovery procedures. Screen credentials
are not disk encryption and do not protect unencrypted storage against extraction.

Integration boundary
--------------------
lock_adapter.py implements the existing EtherLock prompt/result pipe protocol.
It validates the root Unix peer, consults the server's preference and returns
success only after verification. --system forces Debian password fallback. It
is not activated in auth.cpp: a native recovery-method selector and acceptance
of the real locker/PAM/socket path are required before connecting it. No D-Bus
secret methods or unlock booleans exist. Per-UID transport does not establish
logind session binding: requests are intentionally independent and return no
transferable authorization token. Session-bound transaction integration remains
required before a production native UI is enabled.

The serialized prototype transport can be delayed by a local client for its
bounded socket timeout; production requires fair per-peer scheduling. Python
cannot guarantee wiping all immutable secret copies. Core dumps are disabled,
request bodies are never logged, and stored verifiers/events contain no plaintext.
PAM helper input is limited by the existing EtherLock helper (1024 UTF-8 bytes).
Screen passphrases accept up to 16 KiB for bounded transport resource use.

Distribution
------------
distributor.json marks this release development-device-acceptance-required.
Use EtherUpdate/AutoUpdate Center only after native and physical acceptance.
No alternate updater is introduced and no release is published by these sources.
