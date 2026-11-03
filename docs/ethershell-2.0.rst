EtherShell 2.0 experimental experience
=====================================

Status and safety boundary
--------------------------

Update: version 2.0.1 replaces the following QML application headers with
real XFWM-owned frames. See ``ethershell-2.0.1-native-frames.rst`` for the
current architecture, deployed version and device validation. The 2.0.0
description below records the earlier prototype and its limitations.

The user's latest direction supersedes the original isolated-session default:
normal use now starts with ``ethershell2-start`` in the existing X11 session.
It shares the normal D-Bus, application profiles and user settings, retains
the existing WM and opens real applications with free window geometry. The
launcher stops only the verified previous EtherShell UI on that display and
restores it when the new UI exits. It starts no X server or window manager.
The --enable-surface flag opts this invocation into decoration management
without deleting the existing fallback safe-mode marker. Maximise and split
remain explicit actions; floating windows have their own draggable headers.
The nested preview remains an optional developer test tool, not the intended
user experience.

Current-session deployment has now been validated on the phone. The running
binary is staged at ``/opt/ethershell2/2.0.0-88bcd6f7c2dd/usr/bin/ethershell``;
``/usr/bin/ethershell`` remains the installed 0.4 fallback. The launcher shares
the existing :0.0 display, normal Firefox profile, user settings and D-Bus.
Xorg PID 1415 and xfwm4 PID 1572 remained unchanged. Ten current-session
checks passed, including the pre-existing Thunar client, native Firefox and
terminal decoration removal, switching, keyboard restoration and overview.
Three additional current-device geometry checks passed: multi-step header
drag, grip resizing and stable header identity. They use XTest pointer events;
physical-finger acceptance is still a user/device check. Terminal geometry
was restored after the test and the browser was reactivated.
The ARM64 release passed all 15 floating-window build-host checks; a native
AddressSanitizer build passed the same checks and theme/switch stress without
a sanitizer report. Results are under ``evidence/ethershell2-current-results.json``,
``ethershell2-floating-arm64.json`` and ``ethershell2-floating-asan.json``.

Header delegates now retain identity across geometry updates. Dragging does
not recreate the window or accidentally open its long-press menu. Phone
headers/grips use the phone UI scale. Resizing uses absolute gesture targets,
so a terminal's character-cell size increments do not discard small movements.
Free phone windows reserve their header/grip and restore their size after the
keyboard closes. Native dialogs remain under XFWM.

The supported external Firefox preference file was applied and Firefox closed
and reopened normally to remove its duplicate client-side window buttons.
Its actual tabs, address bar and security controls remain native. The browser
showed its recovery page after the user's hard reboot; this was not treated
as a shell crash. Opaque surfaces are currently selected for legibility where
floating headers overlap; transparency remains user configurable.

Current-session staging/start/status/stop from the Windows checkout::

    py -3 scripts/deploy-ethershell2-current.py stage
    py -3 scripts/deploy-ethershell2-current.py start
    py -3 scripts/deploy-ethershell2-current.py status
    py -3 scripts/deploy-ethershell2-current.py stop

Stop restores the verified previous shell UI; Xorg, XFWM and ordinary apps
remain running. No default login-session switch or automatic startup of the
experimental UI has been enabled. Source/package backup and the additional
current-session settings backup are retained under
``/var/backups/ethershell/before-current-2.0/``.

A normal XFCE application-menu entry named ``EtherShell 2`` and user launcher
``~/.local/bin/ethershell2-start`` are installed. The launcher supports
``start``, ``status`` and ``stop``. After reboot, use this entry to resume the
new experience in the normal session. After seven minutes, the shell used
about 196 MiB RSS and 2.1 percent lifetime-average CPU; system swap remained
unused and SSH responded. This short observation does not establish sustained
stability or identify the earlier freeze's cause.

This is a functional native X11 companion to xfwm4, with real Firefox and
terminal clients. It is experimental, not a completed hardware acceptance
release. The original Main.qml experience remains the default binary path;
the new experience requires the isolated preview or the explicitly selected
experimental login session. Neither helper changes the default login session.

The device session was audited before implementation; see
``ethershell-2.0-audit.rst``. The host :0 session, its Firefox profile, the
AutoUpdate implementation, Xorg configuration, networking, kernel, bootloader
and Android partitions were not changed by this development work. The new
binary has not yet been installed as the host shell. The existing 0.4 safe-mode
marker remains in place.

Architecture
------------

``Pocket`` sends EWMH requests to the existing WM. It does not own
SubstructureRedirect, the compositor selection, or reparent application
windows into Qt. Ordinary clients receive reversible Motif decoration hints
and optional XShape rounded bounding regions. Pre-shaped clients retain
their own shape. Terminal rounding is disabled to protect text at the top
left. Dialogs retain WM modality and native decorations; oversized or stranded
phone dialogs are repaired within the usable area.

Non-focusing native Qt header windows show compact identity and actions.
Phone chrome, navigation and EtherKeyboard reserve their actual struts.
External windows have independent free geometry, draggable headers and
resize grips. Top/bottom splits are available. Desktop workspace activation
follows the WM's existing EWMH desktop assignment when switching clients.

Root/client property and structure events trigger debounced policy updates;
a two-second fallback scan covers missed changes. No root input overlay
captures browser scrolling. Gestures are confined to the reserved dock strip.
Preview images are snapshots on overview opening, not continuously refreshed
video. They require Composite, a running compositor and a viewable client.
Capture is bounded to 4096 pixels per dimension and the resulting cards are
420 pixels wide. Unsupported or minimised clients show icon/title cards.
Low-power mode releases capture redirects and disables rounded shaping and
animations. Rendering uses Qt Quick software mode until GPU support is verified.

Files
-----

* ``ethershell/qml/Experience.qml``: home, search, favourites, dock, sidebar,
  overview, application menu, settings, quick settings and keyboard integration.
* ``DesignTokens.qml``, ``GlassPanel.qml``, ``TouchAction.qml``,
  ``SurfaceHeader.qml`` and ``GestureStrip.qml``: reusable native presentation.
* ``src/pocket.*``: actual X11 discovery, geometry, decoration and recovery journal.
* ``src/core.*``: existing application/service backends, settings, XTest text
  input and optional asynchronous AT-SPI editable-focus detection.
* ``packaging/profiles.json``: schema 1 application policies, identified by
  WM_CLASS and desktop entry; generic policy handles unrecognised clients.
* ``tools/development.py``: authenticated nested server and recovery supervisor.
* ``tools/surface_restore.py``: identity-checked restoration of hints, shape,
  geometry, state and temporary Unicode keyboard mappings after a crash.

Preview and selectable session
------------------------------

After installing the experimental package, run as mobian from the existing
graphical session::

    ethershell2-preview start
    ethershell2-preview status
    ethershell2-preview stop

Desktop layout check, after stopping the phone-sized preview::

    ethershell2-preview start --desktop --size 1920x1080

This is a nested desktop-layout test, not proof of physical AR hotplug. The
preview owns :93 with a private Xauthority cookie and disables TCP X11.
Closing its Xephyr window returns immediately to the original desktop.
Do not start a development binary directly on :0. Its development guard
rejects starts without the preview environment.

Preview configuration and logs are scoped to
``~/.local/share/ethershell2-development/`` (``config/ethershell/``,
``session.log``, ``xserver.log`` and ``processes.json``). A dedicated Firefox
profile there protects the normal browser profile. Applications use a separate
D-Bus session, XDG settings and XFCE settings service. Preview brightness and
hardware controls that cannot safely be isolated are disabled.

The optional LightDM entry is ``EtherShell 2 (experimental)``. Select it only
after preview validation; XFCE remains separately selectable. It uses one
xfwm4 instance and configuration rooted at ``~/.config/ethershell2-session``.
Do not select the legacy EtherShell login entry when intending to test 2.0.

Controls and preferences
------------------------

The dock provides Home, Applications, Recent windows, Keyboard, Touchpad and
System controls, with visible Back and More alternatives. Swipe horizontally
on its handle to switch applications, up for overview, down for quick settings,
and hold for the application menu. The configurable central gesture range
defaults to 8–92 percent of the strip; touches in excluded ranges do not switch
applications. Application content remains under its own touch handling.

More exposes minimise, fit, restore, fullscreen, split, move/resize, external
placement and protected close. Desktop headers drag; their external corner
grips resize. Native WM move/resize is also offered. Firefox controls use actual
browser shortcuts for back/forward, zoom, previous/next tab and new tab.
Terminal copy/paste uses Ctrl+Shift+C/V, with scrollback keys and its dedicated
keyboard layer. Full titles remain available in the overview/menu.

Settings persist in ``config/ethershell/preferences.json``: Light, Dark or
time-based Auto (dark before 07:00 and after 19:00), accent, wallpaper path,
glass opacity, font/interface/keyboard scales, terminal font size, high contrast,
reduced motion, low power, previews, gestures, auto keyboard, sidebar pinning,
dock order and auto-hide. Core preferences are range-checked on changes.

AT-SPI focus detection requests only interface names, never text contents.
Applications exposing EditableText can request the keyboard automatically.
Unsupported clients retain a manual keyboard button. This does not provide
Android-style caret geometry; compatible phone windows resize to reserve the
keyboard, and fullscreen returns after keyboard dismissal. English, Polish,
terminal, number and function-key layers reuse the existing keyboard.

GTK 3/4 settings, XFCE preferences, cursors/icons and the Qt GTK platform
theme bridge are applied reversibly within the session. Third-party widgets
may differ. Firefox preferences use Debian's supported external preferences
directory and XInput2, touch density and titlebar settings; browser binaries
and internal files are not modified. An existing Firefox process may need a
normal restart before external defaults take effect. User preferences can
override defaults.

Application profiles
---------------------

Copy ``/usr/share/ethershell/profiles.json`` to the session's
``config/ethershell/profiles.json`` before customisation. Invalid schema,
missing names/classes or unsupported geometry policies select safe mode.
Policies include ``maximize``, ``fit``, ``fullscreen``, ``split-top`` and
``split-bottom``; ``placement`` is phone/external, and ``decoration: native``
opts a client out of EtherSurface. ``rounding: false`` preserves a rectangle.
Launch environment scaling is restricted to validated GDK/Qt scaling and
MOZ_USE_XINPUT2 values. Orientation follows XRandR; profile orientation and
descriptive touch/scale labels do not promise per-application rotation or
arbitrary application UI control.

Firefox, terminal, Thunar, XFCE settings and six Etherneco profiles are supplied.
Etherneco profiles are matching rules, not replacement applications. Their
launchers/catalogue continue through the existing Distributor; no new update
service or URL was introduced. Actual class names should be verified after
each application is installed.

External display
----------------

The existing EtherAir helper retains responsibility for physical XRandR mode
selection, including 1920x1080. The companion observes Qt screen changes,
preserves the phone policy and permits free external placement. Phone touchpad
and keyboard controls reuse the existing backends. On disconnect, unreachable
clients return to phone geometry. External placement, dual-output struts and
reconnection require physical acceptance testing with the glasses attached;
a nested 1920x1080 server cannot validate cable, driver or firmware behaviour.

Recovery and rollback
----------------------

The supervisor restores saved app state after a shell exit and restarts once
in safe mode after an abnormal exit. A second failure closes the preview or
returns the login session to LightDM. Recovery can be invoked as the desktop
user::

    ethershell2-recover --safe
    ethershell2-recover --stop-preview

``--reset`` renames the scoped preference file to a timestamped backup.
``--restore-apps`` restores session-scoped application settings from their
backup. From the experimental login session use its own terminal so the
correct XDG configuration environment is inherited. From the host these tools
target only the isolated preview. The recovery script never broadly pkills
EtherShell, the WM or the user's browser.

For package rollback, stop the preview and return to XFCE before reinstalling
the preserved 0.4 package with ``sudo dpkg -i ethershell_0.4.0_arm64.deb``.
Local source rollback is ``build/ethershell-before-2.0.tar``. Device binary and
profiles are backed up under ``/var/backups/ethershell/before-2.0/``. Preserve
the existing host safe-mode marker. Do not reset Xorg, networking or boot
configuration as part of rollback. Closing a nested preview does not require
rebooting the phone.

Build and validation
---------------------

Native Debian 13 ARM64 build::

    cmake -S ethershell -B build/ethershell2 -DCMAKE_BUILD_TYPE=Release -DCMAKE_INSTALL_PREFIX=/usr
    cmake --build build/ethershell2 --parallel 1
    cd build/ethershell2
    cpack -G DEB

Qt 6 Core/Gui/Qml/Quick/QuickControls2/DBus/Network development packages and
X11/XTest/XInput/XScreenSaver/Xext/XComposite headers are required. Runtime
QML/SVG/Xephyr/xfwm4 dependencies are declared in CPack.

The Debian 13 amd64 WSL build host uses arm64 multiarch Qt development
packages, native Qt code generators and g++-aarch64-linux-gnu. Run
``sh scripts/build-ethershell-cross.sh`` there. Build output is separate from
device source and the Windows checkout. The build log records compiler and
package diagnostics. Use one native compile job on the phone: a four-job
build stalled and new SSH banner exchanges subsequently became unavailable;
the cause has not been established. No network configuration was changed.

Run ``python3 ethershell/tools/experience_test.py`` as the desktop user while
the isolated phone preview is running. It is deliberately restricted to :93.
It drives real Firefox and terminal clients, native XTest input and EWMH,
captures screenshots and simulates a SIGKILL of only the nested shell.
Results live in the preview ``validation/`` directory. This test modifies only
the test browser profile and the preview's preferences.

The first device run passed 34 of 36 checks. Failures were XComposite capture
and a test that incorrectly assumed Firefox originally requested decorations;
fixes are present but await a device rerun. Passed checks included native
Firefox Unicode input and back/forward/tab actions, terminal execution,
keyboard workarea/restoration, dock gestures/exclusion zones, overview,
quick settings, themes, fullscreen recovery and preservation of host processes.
The latest AT-SPI path and external layout corrections also await runtime
verification. New QML components parse successfully with Qt 6.8.2 tooling.

Pending acceptance: actual finger scrolling through YouTube comments, physical
AR connection/disconnection and window transfer, portrait/landscape hardware
interaction, long-duration power/memory behaviour, final package/device
regression, and final preview capture/recovery rerun. The first real YouTube
page was its cookie-consent flow, so opening that page is not reported as
successful comments scrolling. Do not promote this build to the normal session
until those checks pass.
