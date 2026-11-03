EtherShell on the physical EtherPocket — 2026-10-16
=================================================

Delivery status
---------------

Version 0.4.0 adds the native Pocket Mode companion. Current implementation,
validation limits, safe mode and rollback are documented in
``ethershell-pocket-mode-2026-10-17.rst``.

Version 0.3.0 adds global side-button volume control, Power + Volume Down
screenshots and the native Images/Screenshots gallery. See the media
validation section below for device verification and limitations.

Version 0.2.0 adds a live native AutoUpdate catalogue client. The corrected
host is ``autoupddate.etherneco.com``. After the initial Cloudflare 1010
rejection, the user explicitly requested retrying with the honest client
User-Agent ``EtherShell-Autoupdate/1.0 (+https://etherneco.com)``. MCP
initialize and tools/list returned HTTP 200 and accepted Authorization:
Bearer. No query-string token fallback was needed. The management token
stays in a local access-restricted file outside source control and is not
installed on the phone or packaged in the DEB. See the initial diagnostic
and the subsequent ``distributor-mcp-success.txt`` for the request status
and Cloudflare ray IDs.

Version 0.1.0 is a working native ARM64 Qt 6 / QML application installed
on the USB-connected GM1920. It runs unprivileged as ``mobian`` in the
existing X11/XFCE session. An additional LightDM session entry starts it
with Openbox. XFCE remains installed and remains the default. This is an
incremental implementation, not completion of the entire supplied specification.

Implemented functionality
-------------------------

* Touch-sized home screen, application grid, search and persistent favourites.
  Hold an application icon to pin or unpin it. Application discovery reads
  XDG desktop entries, including user overrides, visibility and TryExec.
  Launching delegates desktop-entry execution to GIO.
* A persistent navigation dock: Home, applications, window switcher,
  EtherKeyboard, phone touchpad, and notifications.
* Real EWMH window activation, minimisation, closing and workspace selection.
* Separate X11 keyboard window that does not take input focus. English and
  Polish input, Shift, Caps, Ctrl, Alt, AltGr, Super, symbols, arrows, Esc, Tab, Home,
  End and an additional terminal layer with F1–F12, Page Up/Down, Insert
  and Delete. Hold Polish letters to enter their diacritics (x gives ź).
  Input uses XTest. A temporary unused keycode supports Unicode and is
  restored after delivery. Input events are queued to preserve ordering.
  Typed user text is not written to diagnostic logs.
  Keyboard size is adjustable. Holding Backspace repeats deletion.
* Native settings for NetworkManager scan/connect/radio operations;
  existing native editors for connection details, Bluetooth pairing,
  audio routes and display configuration. Volume and mute use pactl.
  Unsupported services report errors rather than simulated success.
* Battery level, charging state and battery temperature from kernel sysfs;
  memory, load, hostname and kernel version from procfs. These readings
  do not establish whole-device power consumption.
* Light/dark theme, interface scale, keyboard language, atomic JSON
  preferences and schema checks. Invalid scale values are rejected.
* A freedesktop notification service when another notification daemon
  does not already own the session bus name. It does not replace XFCE's
  existing service. The history view retains at most 50 notifications.
* Per-output EtherAir background/panel creation using Qt screen events,
  workspace buttons and manual mirror/extend integration with the existing
  etherair-x11 helper. Phone touchpad provides relative movement, click,
  right click, held-button dragging and scroll buttons.
* Single-instance control: launching EtherShell again opens the existing
  home screen. SIGTERM/SIGINT close through the Qt event loop. Normal exit
  restores the temporary keyboard mapping and the previously visible
  Onboard keyboard. Onboard is temporarily hidden while EtherShell runs.
* Reproducible CMake/CPack ARM64 DEB, desktop launcher, session launcher,
  recovery command, capability audit and an idle-process benchmark.
* Native Qt Network AutoUpdate client using the existing public
  ``/api/projects`` and ``/api/releases/check`` endpoints, complete
  pagination, Stable versions, artifact platforms/formats, SHA-256 and
  signature availability metadata. All programmatic HTTP clients send
  the explicit User-Agent, Accept and Content-Type headers. The phone
  needs no management token for public catalogue access. App Centre
  displays the six requested families and their real public variants.
  It does not install artifacts without verified Debian ARM64 compatibility.
  Cached metadata survives failed refreshes; Cloudflare 1010 stops new
  requests for that client instance. TLS verification remains enabled,
  and redirects are restricted to the same origin.

Installed device baseline
-------------------------

Debian reports 13.7 (trixie), architecture aarch64, kernel
``4.14.117-perf``. The active session user is mobian (UID 1000), display
``:0``, LightDM/XFCE/xfwm4. The phone panel is DSI-1, 1440 x 3120.
XInput exposes touchpanel. DP-1 was disconnected throughout this work.
Native USB RNDIS/SSH is reachable at ``10.77.0.2``.

NetworkManager and the existing Wi-Fi connection are active. No Bluetooth
controller appears in sysfs. UPower fails because its service cannot set
up user namespacing on the existing kernel. EtherShell reads battery sysfs
directly and does not modify the kernel or UPower's service protections.

Before installing dependencies, the installed-package list and copies of
``/etc/X11``, ``/etc/lightdm``, ``/usr/share/xsessions`` and the mobian
configuration directory were saved under
``/var/backups/ethershell/baseline`` on the phone. No boot partitions,
partition tables, boot images, firmware or Android files were changed.
No reboot or dual-boot round trip was performed in this task.

Build and installation
----------------------

Sources are in ``ethershell/``. From the Windows workspace::

    py -3 scripts/deploy-ethershell.py --build

This uploads sources over the existing SSH key and compiles as mobian.
On Debian ARM64, install build-essential, cmake, qt6-base-dev,
qt6-declarative-dev, libx11-dev, libxi-dev and libxtst-dev, then run::

    cmake -S ethershell -B build/ethershell -DCMAKE_BUILD_TYPE=Release -DCMAKE_INSTALL_PREFIX=/usr
    cmake --build build/ethershell -j4
    cd build/ethershell
    cpack -G DEB
    sudo apt install ./EtherShell-0.1.0-Linux.deb

Keep ``scripts/etherair-x11.py`` beside the ethershell source directory
as in this repository. Runtime dependencies are declared in the DEB.
Firefox ESR and Mousepad were additionally installed on this device;
they are ordinary discovered applications, not Etherneco substitutes.

Start, recovery and removal
---------------------------

At the user's subsequent request, the top XFCE panel (panel-1) was
removed from the active panel list. The list is now ``[2]``; the lower
XFCE panel configuration and EtherShell navigation dock are preserved.
The panel process was restarted to apply the change, and the Pocket
window was moved to the top edge to fill the released space. Before
this change, the panel XML was copied to
``/var/backups/ethershell/before-top-panel-removal/xfce4-panel.xml``.
To restore the top panel from the logged-in mobian session::

    xfconf-query -c xfce4-panel -p /panels -a -t int -s 1 -t int -s 2
    xfce4-panel --restart

Run ``ethershell`` from the logged-in desktop user, or select EtherShell
at LightDM. Do not run the graphical process as root. The application
forces the xcb platform and software Qt Quick renderer for this device;
there is no Wayland dependency. There is no new autologin configuration.

At the user's subsequent request, EtherShell was added to mobian's XFCE
login autostart using
``/home/mobian/.config/autostart/ethershell.desktop``. Its source is
``config/ethershell-autostart.desktop``. It starts ``/usr/bin/ethershell``
as the desktop user after XFCE login, including after a reboot into Mobian.
The existing XFCE session and LightDM autologin configuration are retained.
To disable this autostart, set ``Hidden=true`` in that desktop entry or
disable EtherShell in XFCE's Session and Startup settings. This does not
change the currently running temporary preview service.

After the user reported Onboard reappearing following a reboot, both
Onboard startup entries were disabled through per-user XDG overrides:
``~/.config/autostart/etherpocket-onboard.desktop`` and
``~/.config/autostart/onboard-autostart.desktop``, each with ``Hidden=true``.
The ``org.gnome.desktop.a11y.applications screen-keyboard-enabled`` setting
was changed from true to false and the existing Onboard process was stopped.
The custom XFCE Onboard entry had been starting after EtherShell, bypassing
EtherShell's one-time hide of an already running keyboard. The Onboard
package remains available for manual fallback; EtherShell autostart and
EtherKeyboard were preserved. Original system entries and the previous
accessibility setting are recorded in
``/var/backups/ethershell/before-onboard-autostart-disable``. No reboot
was performed to verify this change in this task.

The current preview is a transient user service called
``ethershell-preview``. Its environment contains DISPLAY, XAUTHORITY and
the existing user bus. From the mobian user::

    systemctl --user status ethershell-preview
    systemctl --user stop ethershell-preview
    ethershell-recover
    ethershell-recover --reset

The settings screen also has a close/return-to-XFCE button. ``--reset``
backs up the preferences file before the next launch uses defaults.
For the Openbox session, exiting returns to the login screen; choose
XFCE there. Remove the added package with ``sudo apt remove ethershell``.
Dependencies remain installed unless separately removed through APT.

Preferences are in ``~/.config/ethershell/preferences.json``. Diagnostics
omit credentials and saved Wi-Fi secrets. Synthetic input used by the
test runner is clearly separated from normal operation.

Architecture
------------

``src/main.cpp`` owns application lifecycle, single-instance IPC, graceful
termination, the QML engine, screen events and notification bus ownership.
``src/core.*`` provides the QObject interface for XDG applications,
asynchronous system commands, hardware telemetry, preferences, X11 input
and window properties. ``qml/Main.qml`` implements Pocket, native settings,
window switcher, unavailable-distributor view and per-screen Air panels.
``qml/Keyboard.qml`` is a separate non-focusing input window.

Commands are passed as executable/argument arrays. Wi-Fi passwords are
sent to nmcli stdin, not put on the process command line. No new root
daemon, policykit bypass or privileged input service is installed. The
Openbox session starts the system's existing MATE authentication agent.

Validation
----------

``ethershell --integration-test`` runs in the physical X11 session as
the desktop user. It renders all seven main pages and the keyboard,
discovers actual installed applications and DRM outputs, checks theme
changes and invalid preferences, clicks an actual onscreen key with
synthetic pointer events, verifies Unicode delivery to a Qt window,
checks focus preservation, Ctrl+C, arrows and input ordering, then launches
a disposable xfce4-terminal and verifies its UTF-8 input bytes. It closes
its own test terminal and leaves existing applications intact.

Results and screenshots are in ``evidence/ethershell-validation/``.
``results.json`` records each assertion. ``system-audit.json`` captures
read-only XRandR, XInput, CPU, services, power, network and audio discovery.
The integration test temporarily changes and restores the theme. An idle
benchmark is saved separately as ``idle-benchmark.json``; it measures
only EtherShell's process, with XFCE still running and USB connected.

The installed build passed all recorded integration assertions, including
actual onscreen-key clicking and Unicode input in xfce4-terminal.
``lifecycle.json`` also verifies that the navigation dock remains mapped
when Home is minimised, a second launch restores Home, and only one
EtherShell process runs. Stopping the preview changed Onboard's Visible
property from false back to true before the next preview launch.

``ethershell --catalog-test`` fetched both public catalogue pages and
the current Stable releases directly from the phone, with HTTP 200,
zero errors and real Cloudflare ray IDs. ``--catalog-offline-test``
blocked only this test process through an unreachable local proxy;
Wi-Fi and device networking were not disabled. It confirmed that the
last successful catalogue remains available after the refresh fails.
Evidence is in ``distributor-live.json/png`` and
``distributor-offline.json/png``. The full X11 integration suite also
passed after the new catalogue view was added.

The 30-second home-idle sample measured 0.93% of one CPU core and
121,984 KiB resident memory for EtherShell itself, with a reported battery
temperature of 31.0 degrees C. This is one sample, not an estimate of
total device power or sustained thermal behaviour.

SSH, LightDM, NetworkManager and the existing XFCE process were checked
after installation. These checks do not replace physical touch, glasses,
Bluetooth or boot-cycle acceptance tests.

Incomplete work and external blockers
-------------------------------------

* AutoUpdate connectivity and real catalogue discovery now work. The
  authenticated registry contains 38 projects. None of the six requested
  families has a confirmed native Debian ARM64 package in the inspected
  metadata. Public discovery includes seven EtherRemote variants and two
  EtherFleet variants; the EtherDeck projects are private Windows/Android
  projects, and EtherMCP/EtherAIR/EtherTrust have no matching project in
  the inspected registry. Some older EtherRemote artifacts labelled
  Linux/macOS in their names are tagged Windows/.exe in the API. These
  inconsistencies do not establish ARM64 compatibility. Installation,
  updating and configuration of the six real apps remain incomplete;
  no incompatible packages or placeholder applications were installed.
  Only read-only API/MCP operations were performed. Public catalogue
  data is projected onto a small field allowlist; account/owner records
  are not retained in the phone's cache or reports.
* Glasses: no external display was attached. Air UI, pointer controls,
  manual display profiles and hotplug code exist, but independent display
  placement, output recovery and 1920 x 1080 operation remain unverified.
  The previous repository report documents a DP-related kernel issue;
  this work does not assert it has been fixed. Air is one shared X11
  window-management context, not separate isolated sessions.
* Bluetooth has no active controller. Audio and network settings call
  real services, but pairing, audio routing, changing Wi-Fi credentials
  and manual display reconfiguration were not exercised destructively
  against the user's working connection/session.
* Home folders, drag/drop ordering, multiple home pages, configurable
  widgets/dock, global gesture navigation, automatic sensor rotation,
  brightness policy integration, system tray embedding and plugin loading
  still require implementation. Native display settings remain available.
* Keyboard auto-show is manual; there is no universal X11 input-focus
  protocol. Repetition for keys beyond Backspace, haptics and arbitrary
  multilingual layout handling still need additional UI work and tests.
* Notification actions/persistence, complete per-output theme profiles,
  guided app configuration, signed app installation and separate modular
  DEBs are not implemented. The current package contains the cooperating
  components in one executable.
* The Openbox login entry is installed, but the current XFCE session was
  deliberately not logged out to test it. A login-cycle test, actual
  human touch acceptance and the remaining hardware/performance scenarios
  remain necessary before making EtherShell the default desktop.

Next implementation order is to validate direct touch and login recovery,
complete keyboard/navigation behaviour, test connected external hardware,
then supply/build and validate real ARM64 packages and their existing
configuration workflows. Read-only discovery also found local source
directories ``C:/projects.local/etherTrust``,
``C:/projects.local/etherRemoteAI`` and ``C:/projects.local/nreal``;
these were not modified or built during the HTTP client correction.
Do not mark the full EtherShell specification complete
from the existence of these screens.

Side buttons, screenshots and gallery (0.3.0)
-------------------------------------------

``src/media.*`` observes only the three side-key codes using XInput2 raw
events in the user's X11 session. Passive X11 grabs consume volume keys
so focused applications do not apply a second adjustment. Core grab events
also supply releases and chord keys while the passive grab is active.
Steps are 5 percentage points, bounded to 0–100%; held buttons repeat.
The current default PulseAudio/PipeWire sink is queried before each step.
The settings slider and volume popup read actual sink volume/mute state.

Power + Volume Down accepts either press order, with a 180 ms window before
an initial volume adjustment. It captures once until both chord keys have
been released. The screenshot uses XGetImage on the whole X11 root at native
pixel dimensions, avoiding Qt's logical/physical scaling mismatch. PNGs
are saved atomically in the XDG Pictures directory's ``Screenshots`` folder
with a timestamp and unique suffix. Previous EtherShell feedback is hidden
before capture. After a successful save, a white flash covers each screen,
``paplay`` plays the freedesktop camera-shutter sound, and a tappable toast
opens the gallery. Sound follows the system's current audio route and mute.
Failed captures/saves show an error and do not emit success feedback.

While EtherShell runs, it temporarily sets XFCE's power-button action to
Nothing and takes a logind handle-power-key inhibitor when available. The
previous XFCE property is restored on normal exit and SIGTERM/SIGINT. A
Power press without the chord turns the display off on release through
X11 DPMS. A forced kill cannot restore the XFCE property; this restoration
is only guaranteed for the normal lifecycle. No evdev permissions, root
input daemon, boot files or kernel changes are required.

The home screen's ``Obrazy i zrzuty`` opens ``qml/Gallery.qml``. It lists
readable supported image formats recursively under XDG Pictures, newest
first, with thumbnail decoding, an all-images/screenshots filter, refresh,
previous/next navigation and pinch/button zoom. New captures refresh the
model immediately; external additions appear on reopening or Refresh.

``ethershell --media-test`` exercises real XTest side keys in the device's
X11 session, including short taps, held repeat, 100% limit, both chord press
orders and both release orders. It checks that a chord captures once without
changing volume, that the saved dimensions equal the X11 root, and that a
separate magenta test window appears in the saved image. It also checks the
flash and gallery thumbnail/preview paths, restores the initial volume, and
removes only its own temporary screenshot files. Results and visual evidence
are written to ``~/ethershell-validation/media-*``. These are synthetic key
events on the physical device, not manual physical-button acceptance tests.
The standard integration suite now also renders the gallery page.

The physical phone now has package 0.3.0 installed and one active
``ethershell-preview`` user service. All 18 media assertions, the full
integration suite and dock/single-instance lifecycle checks passed.
The integration runner requires a UTF-8 locale for terminal Unicode;
the successful run used ``LANG=C.UTF-8 LC_ALL=C.UTF-8``. A separate
``paplay`` invocation of camera-shutter.oga returned exit status 0.
Local evidence is in ``evidence/media-results.json``,
``evidence/media-integration-results.json`` and ``evidence/media-*.png``;
the reproducible package is ``build/ethershell_0.3.0_arm64.deb``.
The previous installed binary is backed up on the device under
``/var/backups/ethershell/before-media-0.3.0/ethershell``.
