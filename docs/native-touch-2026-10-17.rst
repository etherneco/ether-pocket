Native direct touch on X11, 2026-10-17
=====================================

The physical touchpanel already exposes XI2 direct touch with ten contacts.
The Firefox process started in XFCE did not have MOZ_USE_XINPUT2 set. A
temporary uinput touchscreen and isolated Firefox profile reproduced the
reported mouse-like behavior: pointerType=mouse, no touchstart, scrollY=0.
With MOZ_USE_XINPUT2=1 and dom.w3c_touch_events.enabled=1 the same swipe
produced pointerType=touch, one touchstart and scrollY=7855.83, including
kinetic scrolling. This is native touch delivery, not wheel-event synthesis.

Installed configuration
-----------------------

* /etc/X11/Xsession.d/80-ethershell-touch enables XI2 for Firefox and mobile
  Qt Quick controls, removing explicit GTK/Qt switches that disable XI2.
* /etc/firefox-esr/etherpocket-touch.js enables Firefox touch events.
* EtherShell initializes these environment variables before launching apps;
  the separate EtherShell/Openbox session sets them as well.
* The current user's firefox-esr.desktop override explicitly sets the XI2
  variable, so launchers from the existing XFCE login also work immediately.
* The D-Bus/systemd user activation environment has the new variables.

EtherShell was rebuilt on the ARM64 device, installed and restarted. Firefox
was gracefully restarted with one-time session restoration; the same three
browser windows reappeared. No LightDM restart or phone reboot was needed.
Device-side backups, including browser session recovery files, are under
/var/backups/etherpocket-touch-20261017T004502Z. They contain private browser
state and remain on the phone in a root-only directory.

Verification and limits
-----------------------

scripts/test-native-touch.py performs the browser test using real kernel
uinput/Xorg/XI2 delivery and a local HTTP page. scripts/test-native-gtk-touch.py
tests a GTK 3 ScrolledWindow; the same swipe moved its adjustment to 2423.68.
The temporary devices and test processes were removed automatically. Tests
require python3-evdev, installed on the phone for this verification.

The installed Firefox process has MOZ_USE_XINPUT2=1. The deployed EtherShell
binary and build output have matching SHA256:
1b8520e473fe8c4a3720a28be1e7fafdb89ab27b134798f7b88c5fd7180f07d5.

These are synthetic-touch integration tests on the physical phone, not a
human finger acceptance test. Pinch zoom and every installed application
have not been verified. navigator.maxTouchPoints reported zero in the test
profile even though touchstart and pointerType=touch worked; websites may
still choose their desktop interface. GTK kinetic scrolling is already
native; programs with legacy widgets or custom mouse handlers may require
application-specific changes. Existing non-browser programs inherit the
login environment only after restarting them or logging in again.

Xorg's core-pointer compatibility remains available for older programs and
window decorations. Detaching the physical touchscreen from the master
pointer would break their taps and dragging. No global gesture interception,
evdev grab or mouse-wheel conversion was introduced.

Reapply after source changes with::

    python scripts/deploy-ethershell.py --build
    python scripts/apply-native-touch.py

XFCE cursor and interaction follow-up
-------------------------------------

The user confirmed that the visible mouse cursor was still undesirable.
Installed Debian unclutter-xfixes 1.6-1+b2 with --hide-on-touch,
--start-hidden and --timeout 3600. It uses XFixes without grabbing input.
The cursor starts hidden, remains hidden for touchscreen gestures and
returns on mouse motion. A session lock prevents duplicate managers.
XFCE starts /usr/bin/ethershell-touch-cursor through /etc/xdg/autostart;
the EtherShell/Openbox session invokes the same helper. The helper and
dependency are also included in the build packaging and X11 installer.

Applied live through the mobian user's Xfconf session:

* xfwm4 scroll_workspaces=false and mousewheel_rollup=false to prevent
  scrolling from changing workspaces or shading window titlebars.
* GTK drag threshold and double-click distance: 24 pixels; GTK and xfwm4
  double-click time: 500 ms; xfwm4 double-click distance: 24 pixels.
* Single-click activation for xfdesktop icons and Thunar files.

scripts/configure-xfce-touch.py deploys these settings and cursor files.
The original per-property values are saved in
/var/backups/etherpocket-xfce-touch-20261017T012140Z/xfconf-before.json.
A later repeat deployment has its own backup under the 012323Z suffix.
To revert Xfconf, restore recorded values using xfconf-query; properties
recorded as null must be reset with xfconf-query --reset.

The final integration test, with the cursor manager active, recorded
one GTK touch-begin, forty touch-update events, one touch-end, and
2428.43 pixels of kinetic scrolling. Cursor debug output recorded
Hiding -> Showing after simulated mouse motion -> Hiding after touch,
with no subsequent Showing during the swipe. The production manager
was then restarted without debug logging and with the cursor hidden.
The debug log remains at /tmp/etherpocket-cursor-final-test.log.

The GTK test now keeps its swipe above the open EtherKeyboard window;
tests starting on that always-on-top keyboard were intercepted before
reaching the test window. This was a test placement issue, not a failure
of GTK touch scrolling. Human finger and physical USB mouse acceptance
remain for the user. These changes do not add gesture handling to custom
widgets in every legacy application.
