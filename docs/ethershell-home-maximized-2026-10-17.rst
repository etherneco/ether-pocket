EtherPocket Home screen coverage
================================

Home now fills the complete phone work area between the header and dock,
with an opaque square background. It uses the X11 dock layer so ordinary
application frames stay underneath it and Home is excluded from the WM's
movable application list. Geometry changes are repaired through queued
geometry notifications. Screen, scaling and keyboard changes recalculate
the target rectangle. The bottom dock is opaque to cover the XFCE panel.

Launching an application or explicitly choosing one in the shell hides Home;
the Home button shows it again. This preserves application launching and
the shell overview when the kiosk preference is disabled.

Built the ARM64 package and deployed it through the existing current-session
launcher. Nine device checks passed: work-area coverage, shell layer,
coverage after application activation and Alt+Tab, forced geometry repair,
keyboard shrink/restore, explicit app launch, Home return and preservation
of the existing XFWM/Xorg processes. Evidence is stored in
``evidence/ethershell2-home-maximized-results.json`` and
``evidence/ethershell2-home-maximized.png``. The repeatable device check is
``ethershell/tools/home_window_test.py``.

Full Home lock
--------------

The user subsequently selected full Home lockdown. The persisted
``homeLocked`` preference is now true on the device. Home occupies all
1440x3120 pixels; the header, dock and launcher interactions are disabled.
X11 keyboard and pointer grabs keep shortcuts and pointer input in Home.
Home rejects WM close requests and the local control socket rejects app
launching, window actions, menus, keyboard and configuration changes while
locked. Diagnosis and returning to Home remain allowed.

``scripts/set-etherpocket-home-lock.py lock`` enables the preference and sets
the user's existing XFCE EtherShell autostart entry to the staged EtherShell
2 launcher. ``unlock`` restores the saved autostart entry and disables the
preference through SSH, then restarts the shell. No on-screen unlock is
provided. Original preferences and the autostart file are backed up beside
the preferences file. Closing the X11 client releases its input grabs.

All 17 live lock checks passed, including exclusive input ownership,
Alt+Tab/Alt+F4/Super+D, disabled clicks, blocked control requests and focus
retention. Results and the full-screen capture are in
``evidence/ethershell2-home-locked-results.json`` and
``evidence/ethershell2-home-locked.png``. Persistence was checked by restarting
the shell; a full device reboot was not performed. This is an X11 session
UI lock and does not restrict SSH or OS-level administration.

Navigation restored
-------------------

The user subsequently requested the bottom menu at all times and cancelled
full lockdown. ``scripts/set-etherpocket-home-lock.py navigate`` now applies
``homeLocked=false`` and ``dockAutoHide=false``, while retaining EtherShell 2
as the XFCE autostart launcher. Keyboard and pointer grabs are released by
the restart. The dock, application launching and overview are available
again. Home retains its opaque, full-work-area geometry. All nine Home
coverage and application-launch checks passed again on the phone.
