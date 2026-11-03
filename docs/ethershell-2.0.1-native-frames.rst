EtherSurface 2.0.1 — XFWM-owned frames
=====================================

The separate QML header/grip approach has been superseded for normal current-
session use. The user reported visible lag between those windows and the
application during movement. Stable delegate identity improved dragging but
did not remove the architectural dependency on asynchronous ConfigureNotify
and companion geometry requests. That design is not used by the current
launcher anymore.

The current launcher passes ``--native-frames``. Ordinary clients request
native decorations through Motif hints. XFWM owns their full frame, title,
buttons and resize hit targets. The client remains a child of that same frame
through drag and resize. No application is reparented into a Qt container,
and EtherShell no longer moves a second header window to follow the client.
The per-application QML header/grip Instantiator has an empty model in this
mode. Root chrome, dock, overview and application menus remain shell UI.

Replacing or patching the XFWM binary was unnecessary. The existing running
xfwm4 PID 1572 and Xorg PID 1415 were preserved on the phone. Reversible
user-level XFWM themes/settings supply EtherSurface Light/Dark and Phone/
Desktop variants. Phone titlebars are 152 physical pixels tall with 132-pixel
buttons; the native lower-right grip is 144 pixels square. Desktop assets
use a 52-pixel title and 44-pixel buttons. Assets are generated from geometric
drawing code by ``scripts/generate-native-frame-themes.py`` and shipped in
``ethershell/themes``. No copied application chrome or Firefox binary patch
is involved.

Free native windows are left under WM control during interactive movement.
The companion repairs unreachable frames, initial placement and changed
keyboard/display workareas; it does not keep fitting every partial screen-
edge overlap back inside the phone during a drag. Native maximise/restore
states are respected. Geometry repair accounts for the actual native frame
extents so adding a titlebar does not accumulate position offsets.

``tools/native_frames.py`` backs up the affected XFWM settings, installs the
user themes, selects opaque interactive movement/resizing and restores the
original settings when the supervised shell exits. ``current_session.py``
still restores the previous shell UI. XFCE, Xorg configuration, network,
kernel and boot setup are unchanged.

The ordinary WM caption currently displays the application's own title,
ellipsised by XFWM. The shell overview retains profile identity and full
titles. These native captions do not reproduce every element of the earlier
QML identity pill. Theme sizing is global to the X11 WM; switching to the
Desktop theme changes the native frame sizing on that X server. Physical
dual-output AR behaviour remains to be tested.

Validation
----------

The native AddressSanitizer build and ARM64 release passed the build-host
integration checks: real terminal input, Firefox recognition, keyboard
geometry, Light/Dark theme selection, normal exit and the native frame tests.
The eight structural/interaction checks also passed in the real current
phone session:

* A real WM frame is the application's parent.
* Native frame extents include the touch-sized titlebar.
* No per-application following overlay is present.
* Continuous dragging moves the complete frame.
* Header/client offsets stay constant through eight movement samples.
* The parent frame ID is unchanged after dragging.
* The actual WM corner resizes the terminal.
* The parent frame ID remains unchanged after resizing.

Device offsets remained exactly (6, 152) pixels in every sample. These are
XTest pointer-driven checks, not a claim that physical finger feel has been
accepted by the user. Terminal geometry was restored afterwards; normal
application contents were not modified by the frame test.

Evidence: ``evidence/ethershell2-native-device-results.json``,
``ethershell2-native-device-frame.png``, ``ethershell2-native-arm64.json``,
``ethershell2-native-arm64-geometry.json`` and corresponding ASan results.
After two minutes the new shell used about 145 MiB RSS, XFWM remained at
about 112 MiB, system swap was unused, and SSH responded. This is a short
runtime observation, not a long-duration stability guarantee.

Deployment and rollback
-----------------------

The current ARM64 package is ``build/ethershell_2.0.1_arm64.deb``. It is staged
under ``/opt/ethershell2/2.0.1-<package-hash>``; the latest package directory
is ``/opt/ethershell2/2.0.1-ff860ec19c8a``. The installed 0.4 binary remains
the fallback. The normal ``EtherShell 2`` menu entry and
``~/.local/bin/ethershell2-start`` point to the new current-session launcher.
Use ``ethershell2-start stop`` (or the full user-bin path) to restore the old
UI and saved native WM preferences. Do not stop or replace XFWM manually.

The existing default login/session startup is preserved. After a reboot,
launch EtherShell 2 from its normal application entry to enter this mode.

The final skin uses an opaque lower resize strip, avoiding the dark gap that
transparent theme tiles could expose in the native frame. Those assets were
reloaded through the user's existing XFCE settings bus without restarting
XFWM or the applications. The running 2.0.1 code is unchanged by this asset-
only update; a subsequent launch uses the latest package directory. The
final Firefox appearance is ``evidence/ethershell2-native-device-browser.png``.

Protocol/theme contracts were checked against the upstream XFWM 4.20 source
and the official Xfce theme guide:
https://wiki.xfce.org/howto/xfwm4_theme
https://github.com/xfce-mirror/xfwm4/tree/xfwm4-4.20.0/src
