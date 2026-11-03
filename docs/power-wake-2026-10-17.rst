Power key display wake repair
============================

Panel remains black with DPMS On: software-blank workaround
---------------------------------------------------------

The next recurrence at 16:32 UTC affected the active staged 2.0.1 build
``7b446a1157ed`` (binary SHA256
``d99a4e2fdb6d05bda57b594f5086bfbdebd42e1717486903bfa387b3e66fd320``).
Xorg reported On, the shell responded, and a root screenshot contained
the complete desktop, but the user confirmed the physical screen remained
black after DPMS On and saver reset. This is distinct from simply failing
to deliver a power key. Brightness was reapplied, DPMS cycled and the DSI
output disabled/re-enabled with XRandR. The user confirmed image and touch
returned after recovery; these combined actions do not isolate which one
recovered the panel.

An opt-in ``ETHERSHELL_SOFT_BLANK=1`` policy now avoids powering the panel
down. It disables DPMS and registers a black external XScreenSaver window;
power release activates/resets that saver. Idle blanking uses the same
policy. A separate native override-redirect black window covers the actual
desktop while the saver is active. On this Xorg/XFWM build the server-owned
saver window was reparented below the shell, so saver state alone did not
prove visible blanking; the user correctly reported that power did nothing.
Using only DPMSDisable was insufficient: Xorg's built-in saver
calls xf86SaveScreen and still disabled this panel during the first test.
The external saver bypasses that path, as verified against local Xorg
``dix/window.c`` and ``Xext/saver.c`` source and the device kernel log.
Normal shell exit removes the saver window and restores DPMS if it was
enabled at startup. Keeping the display hardware powered can consume more
energy while blanked. This is a workaround, not a verified kernel repair.

Installed build:
``/opt/ethershell2/2.0.1-7b446a1157ed-soft-efd6782b/usr/bin/ethershell``.
The existing user launcher sets the opt-in variable, including at login.
Original launcher: ``~/.local/bin/ethershell2-start.before-soft-blank``.
The original staged binary is retained. Only the shell was restarted;
XFCE and applications stayed running. The workaround binary reused the
exact active build's compiled UI resource objects and rebuilt all C++
objects against the updated header. Build/deployment helpers are
``scripts/build-ethershell-soft-blank.sh`` and ``scripts/deploy-soft-blank.py``.

``ethershell/tools/soft_blank_test.py`` passed seven assertions on the
device: DPMS disabled, five blank/wake cycles with external-saver state
and black pixel checks at the top, middle and bottom of the root image,
long press blank and wake, idle blank and power wake, and DPMS remaining
disabled. No panel enable/disable kernel messages appeared during the
16:45:30--16:45:49 UTC test interval. Original idle settings were restored;
display was left on. The user then manually confirmed the newly installed
policy: "Wygasza się i wraca, dotyk działa". This confirms one physical
blank/wake check; long-term recurrence and battery impact remain unmeasured.
Evidence: ``evidence/power-soft-blank-2026-10-17.json`` and
``evidence/power-soft-blank-runtime-2026-10-17.txt``.

Further recurrence: current EtherShell 2 session
-----------------------------------------------

At 14:31 UTC the user reported another failed wake. The active binary was
the staged EtherShell 2 build under
``/opt/ethershell2/2.0.1-90f5cc32fe41/usr/bin/ethershell``, PID 7883;
its live log is ``~/.local/state/ethershell/current-session.log``. The old
power-wake-queue.log is historical and must not be used as its current log.
SSH remained available and Xorg reported DPMS Off. Recovery requested
DPMS On and reset the screen saver without restarting applications.

The kernel recorded panel disable at 14:30:18 followed by recurring touch
I2C read failures while blanked. The recovery at 14:31:46 enabled the panel
and restored backlight 300. This does not establish visible output or a
touch-driver root cause. The existing evdev test passed all eight checks
plus four repeated off/wake cycles against the active staged binary.
Display was left On; the user subsequently confirmed visible panel and touch
operation: "Tak, ekran i dotyk działają".
No speculative code change was deployed. The recurrence remains unresolved.
Evidence: ``evidence/power-wake-recurrence-2026-10-17.txt`` and matching JSON.

Second follow-up: Xlib queue dispatch
------------------------------------

The user reported a further recurrence shortly after the manual success.
At inspection DPMS was On and EtherShell was responsive. A screenshot
showed the open applications. Forcing DPMS On, resetting the screen saver,
and reapplying brightness restored operation; the user confirmed both
screen and touch working. The exact contribution of each recovery command
was not isolated, so DPMS On alone is not evidence of visible recovery.

Code inspection found a defect in the newly added polling path:
DPMSInfo and XScreenSaverQueryInfo can read X events into Xlib's internal
queue while waiting for replies. QSocketNotifier only observes the socket;
when those reads empty the socket, buffered keys can remain undispatched
until another event arrives. The polling callback now explicitly drains
the Xlib queue after updating display state. In the first test run the
new diagnostic logged five buffered event batches dispatched by this path.
This confirms that socket notification alone misses queued events, though
the full prior visible failure was not reproduced in isolation.

The native build is installed and backed up as
/usr/bin/ethershell.before-x11-queue-fix. Current diagnostics are at
/home/mobian/ethershell-power-wake-queue.log. All eight input/DPMS checks
passed after installation. Ten further off/wake cycles also passed through
the kernel input device; the repeated-cycle test is recorded in
evidence/power-wake-queue-repeated-2026-10-17.json. The earlier manual
confirmation does not establish that subsequent recurrences are solved.

Follow-up: hardware input ordering
---------------------------------

The user reported another failed physical wake the next morning. The
original repair was still present in the running executable. Logind
recorded the presses and the kernel showed panel enable/backlight 300
followed by another disable. SSH remained available; forcing DPMS On
restored the panel without rebooting.

The first validation missed a race: XScreenSaver notifications do not
reliably track DPMS-only blanking. Physical input may unblank DPMS before
the shell handles XI2, so querying at key press is already too late.
The first implementation could still classify a wake as an off request.

The follow-up samples display state every 100 ms and retains the recent
off-to-on transition for 500 ms. Explicit power actions update that cache
immediately. This supplies the pre-input state even when the X server
wakes before delivering the key. Power decisions are now logged in
/home/mobian/ethershell-power-wake-v2-fixed.log on the device.

The test now supports ``--evdev /dev/input/event0`` (root required) to
inject through the existing qpnp_pon kernel device. It also explicitly
simulates wake before key delivery. Before the follow-up, DPMS Off wake
and the ordering regression failed. After installing the follow-up, all
eight assertions passed. Evidence: power-wake-v2-before-2026-10-17.json
and power-wake-v2-after-2026-10-17.json in evidence/.

Installed executable matches the native build. The pre-follow-up binary
is retained as /usr/bin/ethershell.before-power-wake-v2. After installation
the user manually tested the physical button and confirmed: "Tak, ekran
działa". This supplies visible physical-button confirmation in addition
to the injected kernel-event checks.

Initial repair and validation
-----------------------------

Installed on the GM1920 on 2026-10-17 (Europe/London).

The phone remained reachable by pinned USB SSH while its screen was off.
Xorg reported DPMS Off, and logind recorded repeated short power presses.
There was no systemd-suspend invocation in the inspected current boot log.
EtherShell and XFCE held power-key inhibitors; XFCE's power action was 0.

Root cause: Media::button unconditionally launched ``xset dpms force off``
on every unchorded power-key release. Xorg could wake for the press, but
the release immediately blanked the screen again.

Media now subscribes to XScreenSaver state notifications and checks both
DPMS and screen-saver state. At power press it remembers whether the key
woke the screen, including a just-delivered automatic unblank notification.
Release explicitly keeps a wake press on; an awake-screen press turns it
off. Screenshot chords remain consumed until both buttons are released.
DPMS calls use the existing X11 connection instead of detached processes.

Built natively with ``python scripts/deploy-ethershell.py --build`` and
installed as /usr/bin/ethershell. Previous executable retained on phone
as /usr/bin/ethershell.before-power-wake. Restarted only EtherShell;
the XFCE session and applications remained running. Autostart uses the
installed path, so the correction survives login and reboot.

Validation
----------

``ethershell/tools/power_wake.py`` ran as mobian on the real X11 server.
All seven assertions passed: power off from awake, wake retained after
release, wake from standby/suspend/off DPMS levels, actual accelerated
idle-timer blanking, and wake after that idle blank. Timer settings were
restored to 600/0/900 seconds; display was left on. Inputs were injected
through XTest, not manually pressed during this test. Physical power
presses were independently present in the earlier logind log.

Kernel logs during these cycles show dsi_panel_enable completing and
dsi_panel_update_backlight restoring 300. The panel's actual_brightness
sysfs value remained 0 even with DPMS On; it is not used as proof of
visible output. Human confirmation of the visible panel remains useful.

The existing ``ethershell --media-test`` also passed all 17 assertions,
covering both screenshot chord orders, volume, gallery and capture.
Normal EtherShell was restarted afterward. Evidence is saved in
``evidence/power-wake-2026-10-17.json`` and
``evidence/power-wake-media-2026-10-17.json``.
