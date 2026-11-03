EtherShell 2.0 — architecture audit
==================================

Inspected before implementation on 17 October 2026.

The device runs native Xorg :0, xfwm4 (PID 153184 at audit), XFCE and
EtherShell 0.4.0 in safe mode. The previous unexplained session failure
remains recorded in the Pocket Mode report. DSI-1 is 1440x3120; DP-1 is
disconnected. No Xorg, boot, firmware, Wi-Fi or display-driver changes
are part of this implementation. Composite, DAMAGE, XFIXES, SHAPE,
XInputExtension and RANDR are exposed. xfwm4 compositing is enabled.
GPU acceleration has not been established; Qt Quick remains software rendered.

Existing reusable components: C++ EWMH Pocket controller; XTest keyboard
with English/Polish/modifiers/terminal keys; XDG/GIO launch discovery;
NetworkManager, Bluetooth, PulseAudio and display helpers; media keys,
screenshots/gallery; persistent JSON preferences; public AutoUpdate client;
phone touchpad; existing EtherAir XRandR watcher; XFCE fallback.

The 0.4 dock is 130 logical pixels tall with text/glyph controls. The
existing Firefox windows still have xfwm4 grey title bars. GTK is Adwaita;
Qt uses the GTK platform-theme bridge when installed. Profile geometry
is currently polled every 650 ms and reserves dock/keyboard struts.

Decision: retain the existing WM and its compositor. EtherSurface uses
Motif decoration hints, reversible XShape bounding regions, EWMH geometry
and separate non-focusing native header windows. Applications remain real
X11 clients under the WM; there is no Qt reparenting or screen-sized input
overlay. Composite snapshots are optional, bounded overview previews,
with icon/title cards when unavailable. Damage is evaluated for preview
invalidation, not a new compositor. XFixes is available for input/shape
support, while only the necessary header/dock windows receive shell input.
XI2 remains the applications' touch path; XRandR stays with EtherAir.

Development is isolated in an authenticated Xephyr X server, a separate
D-Bus session and separate settings/profile directories. The host :0 WM,
EtherShell process, user Firefox profile and autostart remain unchanged.
One xfwm4 instance owns the nested display. A separately selectable
experimental login session is provided; it never changes the default.

Before modifications, source rollback was saved to
``build/ethershell-before-2.0.tar``; device binary and profiles were copied
to ``/var/backups/ethershell/before-2.0/``. The original 0.4 safe-mode marker
is retained. Recovery tools must restore decoration hints and shapes even
after an abnormal experimental-shell exit.

Protocol references:
https://specifications.freedesktop.org/wm/latest-single/
Local X11 extension headers and manual pages for XShape, XComposite,
XDamage and XFixes are used for the implementation contracts.
