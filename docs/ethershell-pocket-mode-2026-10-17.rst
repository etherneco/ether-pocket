EtherShell Pocket Mode prototype — 17 October 2026
================================================

Current device status
---------------------

The functional 0.4.0 prototype is installed. It is currently running in
safe mode: automatic fitting is disabled by
``~/.config/ethershell/safe-mode``. Do not treat this as a production-ready
release or as completion of every acceptance criterion.

After the successful functional and lifecycle suites, the original XFCE
session unexpectedly exited with status 1 during preparation for an
additional input regression run. Xorg logged a segmentation fault during
the session teardown. The available log does not establish the initiating
cause. The additional input run did not complete; its empty log is not a
passing result. The earlier 23-check input regression result is preserved.
The original application windows ended with that session; continuity through
this failure is not claimed.

XFCE was recovered by restarting LightDM using its existing configured
autologin, without changing that configuration or rebooting. An orphaned
EtherAir watcher from the ended session was stopped; the watcher started by
the recovered XFCE session remains active. In the recovered session, eight
focused checks passed: safe startup, manual enabling/window fitting,
fullscreen dock visibility/stacking, dock access on another workspace,
keyboard resizing, returning to safe mode and xfwm4 liveness. Results are
``evidence/pocket-recovery-results.json``. Automatic fitting was disabled
again after this check. Enable Pocket Mode manually in Settings for a
controlled test; the persistent marker still protects the next startup.

Failure logs are retained on the phone under
``/var/backups/ethershell/before-pocket-mode/session-failure-*`` and the
Xorg excerpt is copied to ``evidence/pocket-session-failure-Xorg.txt``.
Session stability and physical glasses/touch tests remain open work.

Implementation
--------------

EtherShell 0.4.0 adds a native C++ X11 companion to the existing xfwm4.
It does not acquire the window-manager selection, select
SubstructureRedirect, replace XFCE, or alter application binaries.
The companion sends EWMH client messages for activation, workspace
selection, maximisation, fullscreen, moving/resizing and close. Minimise
uses XIconifyWindow. WM_TRANSIENT_FOR, window types, frame extents,
window state and partial panel struts determine the policy.

Normal phone windows maximise. Dialogs retain their normal geometry
unless outside the available area. Desktop, panel, utility and
skip-taskbar windows are excluded. The controller scans every 650 ms,
but sends geometry requests only for a changed policy/work area or a
stranded window. Switching activates existing windows; it does not
relaunch applications or discard their state. A normal shutdown or
disabling Pocket Mode restores the captured geometry and max/fullscreen
states of surviving windows. This is an in-memory snapshot; after a
crash, the fitted windows remain under xfwm4 and can be moved normally.

EtherShell uses native pixels for its own geometry and manually scales
its touch UI. X11 struts use the same coordinates. This avoids applying
XFCE's 264-DPI scaling a second time to reserved screen space. Other
applications retain their normal toolkit scaling. A C/POSIX launch
locale is upgraded to C.UTF-8 for child applications so terminal input
can represent accented characters.

Touch operation
---------------

The persistent dock has large Back, Minimise, Close, Previous and Menu
controls, plus the existing Home, Apps, Overview, Keyboard, Touchpad and
Notifications buttons. Back sends Alt+Left to desktop applications and
Escape to terminal profiles; applications decide how these keys behave.

Swipe horizontally from the labelled dock strip to switch applications.
Swipe upward from the strip to reveal system settings. Hold the strip
or a window-action button for the application menu. Gestures begin only
on this strip; they do not intercept application scrolling. The default
excluded areas are the left and right 8 percent of the strip.

The application menu offers fullscreen, maximise, top/bottom split,
Firefox previous/next tab, and scroll controls. Terminal profiles get
Ctrl+Shift+C/V copy/paste and Shift+PageUp/PageDown scrollback controls.
The overview lists application titles and matched profiles with large
activation, minimise and close controls. No live-thumbnail compositor
is included. There is no floating navigation button in this prototype.

EtherKeyboard remains a non-focusing X11 dock. Showing it reduces the
work area; hiding it restores the area. Terminal profiles automatically
select the terminal keyboard layer. Fullscreen is temporarily removed
on the phone while the keyboard is visible and restored when it hides.
Keyboard opening is manual: X11 does not supply a universal signal for
focused text fields in arbitrary third-party applications.

Profiles
--------

Defaults are installed at ``/usr/share/ethershell/profiles.json``.
Copy the entire file to ``~/.config/ethershell/profiles.json`` to override
it, then restart EtherShell. A missing or malformed policy file disables
automatic window fitting. The schema version is 1.

Profiles match the WM_CLASS resource class case-insensitively. Desktop
entry IDs associate launch-only preferences with discovered applications.
Firefox, XFCE Terminal/XTerm, Thunar, XFCE Settings and a generic fallback
are included. Fields:

* ``geometry``: ``maximize``, ``fit``, ``fullscreen``, ``split-top`` or
  ``split-bottom``. Dialog handling takes precedence over automatic fitting.
* ``external``: ``desktop`` routes newly discovered phone windows to an
  active external output and leaves external windows resizable. Use
  ``phone`` to keep a profile on the phone.
* ``keyboard``: ``terminal`` selects the terminal keyboard/actions;
  ``manual`` selects standard manual keyboard operation.
* ``scale``: preferred scaling description; for the Terminal profile this
  is the actual configured font, initially ``Monospace 12``. Other
  profiles use the existing system DPI by default.
* ``launchEnvironment``: optional string values for ``GDK_SCALE``,
  ``GDK_DPI_SCALE`` and ``QT_SCALE_FACTOR`` (0.5 through 4), or
  ``MOZ_USE_XINPUT2=1``. These apply to desktop entries launched through
  EtherShell. An existing application's single-instance server may keep
  its original environment until that application is restarted.
* ``orientation``: declared preference, initially ``follow-display``.
  Automatic app-specific rotation is not implemented; use Display settings.
* ``touch``: records intended interaction adaptations; the native dock
  supplies the implemented controls described above.
* ``gestures.start`` and ``gestures.end``: allowed horizontal start region
  as fractions of the dock strip width, initially 0.08 and 0.92.

Firefox and terminal
--------------------

Firefox receives MOZ_USE_XINPUT2=1 when launched from EtherShell or a new
Xsession. Distribution defaults in ``/etc/firefox-esr/etherpocket-touch.js``
enable touch events and touch UI density (browser.uidensity=2). These are
user-overridable preferences, not binary, omni.ja, userChrome.css or
application-internal-file patches. Existing Firefox user preferences
can override distribution defaults; an already-running browser keeps
its startup environment. Toolbar and font sizing inherit system DPI;
the browser menu also retains page zoom controls. A separate disposable
Firefox profile was used for the new-window test so user tabs were kept.

The terminal settings helper uses Debian 13's xfce4-terminal Xfconf
channel: Monospace 12, 48x24 initial size, 10,000 scrollback lines, a
visible scrollbar and no initial menu/toolbar. It also writes the legacy
terminalrc format for older XFCE versions. Existing windows may retain
some chrome settings until reopened. Native GTK/VTE touch support is
retained; dock scroll buttons provide explicit touch scrollback actions.

Themes
------

The existing Light/Dark switch updates EtherShell and runs
``ethershell-app-settings light|dark`` as the desktop user. This applies
Adwaita/Adwaita-dark through Xsettings and GTK 3/4 user settings, Adwaita
icons and cursors, a 48-pixel cursor, and Default-xhdpi xfwm4 decorations.
Large dock actions supplement applications' smaller native title buttons.
Qt applications launched through EtherShell use qt6-gtk-platformtheme
when installed. Qt Quick's native shell colours remain explicitly managed.
Third-party applications may retain custom palettes or require restarting.
Uniform third-party theming is not promised.

Before the first change, original files and typed Xfconf values are
recorded in ``~/.config/ethershell/application-settings-backup.json``.
The helper serialises changes with a user-level file lock. Restoring
settings reads this original backup rather than inferring defaults.

EtherAir
--------

The existing ``etherair-x11 watch`` process remains responsible for
connector state, advertised 1920x1080 mode selection, desktop layout and
touch mapping. The new companion does not issue competing xrandr modesets.
The phone keeps its dock and keyboard. External windows remain normally
resizable; new desktop-profile windows can be placed on the external
screen. On disconnect, surviving windows are fitted back to the phone.
Partial struts are evaluated per output instead of treating the phone
keyboard as an overlay on every display. EtherShell stays on the internal
DSI/eDP panel when Qt reports screen changes.

DP-1 was disconnected during validation. Physical glasses hotplug,
external placement and touchscreen mapping still need a hardware test.
No claim of a completed physical external-display acceptance test is made.

Validation and limits
---------------------

Device validation passed all 26 Pocket Mode checks and all 7 lifecycle
checks: all five profiles, real-window fitting, keyboard focus and size
restoration, fullscreen/keyboard transitions, split modes, synthetic dock
gestures/exclusions/hold menus, Light/Dark, state restoration, both safe-mode
startup mechanisms and normal restart. The keyboard/input regression suite
also passed its 23 checks, including real terminal Unicode input.
Machine-readable results are ``evidence/pocket-live-results.json``,
``evidence/pocket-lifecycle-results.json`` and
``evidence/pocket-input-results.json``. External display command generation
has a separate fixture-only check in ``evidence/pocket-display-rules.json``;
this is not a physical hotplug result.

Build on the actual Debian ARM64 device with::

    py -3 scripts/deploy-ethershell.py --build

The live test is ``ethershell/tools/pocket_live_test.py``; run it as
the logged-in desktop user with DISPLAY, XAUTHORITY, XDG_RUNTIME_DIR
and DBUS_SESSION_BUS_ADDRESS. It uses disposable application windows,
an isolated Firefox profile, real EWMH requests, XTest pointer events,
xwininfo geometry checks and screenshots. It temporarily switches
workspaces and themes. Results and screenshots are saved under
``~/ethershell-validation/`` and selected evidence is copied to this
workspace's ``evidence/`` directory. The existing ``--integration-test``
also checks non-focusing keyboard input, ordering, Unicode and a real
terminal receiver.

Synthetic pointer gestures validate dispatch; physical finger gesture
comfort and Firefox/VTE kinetic scrolling need user testing on the phone.
Some applications enforce minimum sizes larger than a split or the
keyboard-reduced area. ICCCM minimum sizes remain owned by the WM and
application; use maximise, hide the keyboard, adjust the profile's launch
scaling or use the external display for these cases. The companion cannot
guarantee that arbitrary applications scroll focused fields into view.
Persistent keyboard occlusion is avoided by reversible work-area changes.

Safe mode and rollback
----------------------

From a terminal as mobian::

    ethershell-recover
    ethershell --safe-mode

Safe mode skips automatic application settings and automatic window fitting.
For a persistent safe-mode startup, including the existing XFCE autostart::

    mkdir -p ~/.config/ethershell
    touch ~/.config/ethershell/safe-mode
    ethershell-recover
    ethershell

Remove that marker to re-enable normal behaviour on the next launch.
To restore application appearance and terminal settings as well::

    ethershell-recover --restore-apps

Disable EtherShell's existing per-user autostart (Hidden=true in
``~/.config/autostart/ethershell.desktop``) to remain in XFCE after login.
XFCE and xfwm4 remain installed and active. EtherShell never replaced the
window manager; the recovered session is again XFCE with xfwm4.

The pre-prototype binary, recovery helper, Firefox defaults and EtherShell
preferences are retained on the device at
``/var/backups/ethershell/before-pocket-mode/``. For a binary rollback,
run::

    ethershell-recover --restore-apps
    sudo cp /var/backups/ethershell/before-pocket-mode/ethershell /usr/bin/ethershell
    sudo cp /var/backups/ethershell/before-pocket-mode/ethershell-recover /usr/bin/ethershell-recover
    sudo cp /var/backups/ethershell/before-pocket-mode/etherpocket-touch.js /etc/firefox-esr/etherpocket-touch.js
    ethershell

For package-level rollback instead, upload the previous
``build/ethershell_0.3.0_arm64.deb`` from this workspace and install it with
``sudo dpkg -i`` after restoring application settings and stopping EtherShell.
``windows.txt`` records the pre-change
window positions for diagnosis; its XIDs are meaningful only in that X
server session. Appearance restoration uses the user backup described above.

No bootloader, kernel, firmware, partition, Xorg driver configuration,
Wi-Fi or SSH changes were made. No reboot was needed or performed.

Protocol references
-------------------

EWMH: https://specifications.freedesktop.org/wm/latest-single/
Mozilla XInput2 tracking: https://bugzilla.mozilla.org/show_bug.cgi?id=1601850
