EtherMobile 0.1.1
=================

Native Qt 6 / QML cellular manager and EtherModem Doctor for X11, with a shared
backend embedded in EtherShell Settings > Network & Internet > Mobile Network.
This is an engineering release, not a verified working cellular stack.
Read ../docs/ethermobile-2026-10-18.rst for the actual hardware baseline.
Read ../docs/mobile-network-settings-2026-10-18.rst for the current configuration
architecture, deployment, test evidence and remaining hardware acceptance.
The IPA boot repair is described in ../docs/modem-startup-2026-10-29.rst.
The separate system initializer now creates the modem network port before
ModemManager starts. The separate IPA data adapter is now enabled at boot
after home-network packet registration; see ../docs/mobile-data-startup-2026-10-29.rst.
The application's stock NetworkManager controls remain a separate path.

The 2026-11-03 repair connects the IPA modem's GUI controls to the existing
data service instead of the unsupported stock MM bearer path. The interface
now shows real connection stages, elapsed time, bounded history and redacted
error details. See ../docs/mobile-data-progress-2026-11-03.rst for deployment,
validation and the current giffgaff/IPv4 adapter limits.

Build on Debian with Qt 6 Core/Gui/Qml/Quick/QuickControls2/DBus development
packages, CMake and Ninja::

    cmake -S ethermobile -B build/ethermobile-native -G Ninja
    cmake --build build/ethermobile-native
    ctest --test-dir build/ethermobile-native --output-on-failure

ARM64 build uses the existing EtherShell cross toolchain::

    sh scripts/build-ethermobile-cross.sh

Use ``ethermobile --compact`` for Pocket sizing, ``--dark`` for dark surfaces,
or ``--doctor`` for diagnostics. Run as the desktop user. The application never
requires a root GUI. There is no root helper, new PolicyKit rule, startup radio
action, background scan, dummy modem, fabricated signal or automatic retry.

Runtime backend
---------------

ModemProvider defines the observed-state contract. The initial Mobile provider
uses asynchronous ModemManager ObjectManager and NetworkManager D-Bus calls,
PropertiesChanged signals and owner-change notifications. QMI/MBIM modems are
managed through ModemManager rather than opening competing control clients.
The downstream Qualcomm adapter is diagnostic-only until its real packet path
is usable. No direct AT/QMI mutation is implemented.

The integrated Settings component adds a complete versioned APN editor,
credential preservation/replacement, duplicate/delete, read-back verification,
guarded rollback, autoconnect/roaming policies, connection/reconnection controls,
SIM PIN/PUK management, explicit operator scan/registration, supported non-NR
mode selection and local usage history. Hardware mutation acceptance remains
pending where documented. All disruptive UI actions require confirmation.
Credentials are never displayed or logged; NM owns secrets storage. Existing
profiles are not rewritten on migration. The standalone compact frontend keeps
its simpler controls and uses the same backend. Provider-default restoration,
SMS, calls, VoLTE, sharing and airplane-mode coordination remain unavailable.

Profiles use NetworkManager storage and existing PolicyKit authorization.
Defaults: home-only, autoconnect=false, one autoconnect retry, metric 900,
never-default=true for IPv4/IPv6. Choosing a default internet route is an
explicit user configuration and can change routing; inspect existing priorities.
The integrated editor offers IPv4, IPv6 and dual stack; saving/read-back is
tested separately from unverified carrier connectivity. Existing Wi-Fi profiles
are never edited or deactivated.

Connected requires ModemManager connected state, a connected bearer,
NetworkManager activation and observed IP address data. Internet status remains
Not verified until real interface-bound DNS and external acceptance is added.
Registration alone never becomes Connected. No active connectivity probes run.

Security and packaging
-----------------------

The package adds an XDG desktop entry (automatically discovered by EtherShell)
and Diagnostics desktop action. Existing AutoUpdate infrastructure is unchanged.
No service is installed or restarted. Existing backend daemons enforce D-Bus
authorization; a denied action fails without automatic retries or shell fallback.
PINs are transient QML/D-Bus values, cleared from the field after submission;
Qt does not guarantee zeroization of implicitly shared string memory. Do not
enable D-Bus message tracing around credentials. No identifiers or raw daemon
errors are logged. The Doctor asks only read-only commands from a fixed allowlist.

Install/upgrade the reviewed ARM64 package with ``sudo apt install ./ethermobile_0.1.1_arm64.deb``.
Remove with ``sudo apt remove ethermobile``. Removal leaves user-created
NetworkManager profiles intact; remove them explicitly in the UI or NM editor.
Rollback means removing this package or reinstalling a previously retained
package; no kernel or partition rollback is needed. There is no configuration
migration rewriting existing profiles. EtherShell Core persists selected UI
preferences; NetworkManager persists actual profiles and credentials.

Acceptance limits
------------------

Policy tests verify that registration/partial sessions cannot claim Connected,
LTE cannot imply 5G/LTE Advanced and malformed APNs are rejected. They do not
mock a modem or establish radio support. Hardware data/PIN-unlock/roaming/NR,
manual touch, suspend/resume, billing counters, external-display interaction
and cold-boot testing remain pending. The approved one-shot IPA initialization
now creates rmnet_ipa0, the board-specific udev association exposes a real MM
modem, and the inserted giffgaff SIM is readable and ready (PIN1 disabled).
Registration is rejected with no-suitable-cells-in-location-area; the user
reports recently activating the SIM. Carrier provisioning is a possible cause,
not a verified diagnosis. Bearer setup and actual IP traffic remain unverified;
no data session has been activated. Automatic IPA startup is not enabled.

On 2026-10-18, native/ARM64 policy tests and three Doctor tests passed. The
physical phone passed real NM profile create/edit/delete and credential
preservation via an administrator QCoreApplication test, unprivileged rejection
without a PolicyKit agent, and three GUI render checks as mobian. Test profiles
were never activated; active connections stayed unchanged. Full acceptance
evidence is in ../evidence/ethermobile-acceptance-2026-10-18.json.
