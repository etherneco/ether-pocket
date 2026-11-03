EtherShare
==========

Native Qt 6 management UI with a system D-Bus controller. The graphical client
runs as the desktop user. Mutations require the dedicated PolicyKit action.
The controller serializes work off the D-Bus event loop and uses NetworkManager
for downstream Wi-Fi/Ethernet profiles. Credentials are stored root-only and
passed to NetworkManager through D-Bus, never process arguments.

USB reuses the existing RNDIS gadget and recovery address. It never unbinds the
controller, changes USB descriptors, removes mass storage or replaces recovery
addresses. Board-specific DHCP integration is required separately and is not
performed by a generic package installation. Linux/macOS USB compatibility and
NCM are unverified. ECM and Bluetooth PAN need kernel support on this board.

If Windows sees the USB device but has no internet after sharing is started,
renew that USB adapter's DHCP lease (for example, ``ipconfig /renew "Ethernet 4"``
on the current workstation). A lease obtained before sharing starts has no
internet gateway. The controller reloads DHCP options, but the host must request
them again. USB status now reports packets forwarded in both directions using
the owned firewall counters, rather than counting recovery SSH as internet
traffic. This reports observed traffic, not guaranteed ongoing connectivity.

Routing is IPv4 only, using explicit legacy iptables binaries on this kernel.
Each downstream has owned chains and an independently guarded routing table.
A terminal unreachable route prevents fallback to the system default route.
Downstream administrative access is blocked, with a deliberate exception for
the established 10.77.0.1 USB recovery host's SSH connection. DHCP leases are
reported as leases rather than proof of current client presence. Traffic totals
are per interface, including recovery traffic. Wi-Fi station counters and local
client names are supported. Forced client disconnect/block,
WPA3, live STA+AP, delegated IPv6 and VPN compatibility are not certified.

Preferences, requested operations and effective backend state are distinct.
Autostart is off by default. No radio, roaming or mobile-data session is enabled
by EtherShare. Explicit USB autostart still checks an already working upstream.
Connectivity checks contact 1.1.1.1 with a bounded small HTTPS response and are
bound to the selected interface. DNS servers are inherited or explicitly set;
there is no silent public-DNS fallback. A detected VPN requires a user policy.

Source-policy routing and a fixed egress guard prevent silent upstream fallback.
Auto failover is opt-in and may interrupt existing TCP connections. The controller
persists a cleanup journal before mutations and cleans it on service restart.
Do not delete the journal to suppress a failed cleanup; inspect diagnostics.

Build with CMake/Qt 6. ARM64 uses ethershell/cmake/debian-arm64.cmake.
Run tests/test_ethershare.py with Python. See docs/ethershare-2026-10-19.rst for
physical audit, test evidence, verified capabilities and remaining limitations.
