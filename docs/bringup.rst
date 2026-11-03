EtherPocket X11 bring-up gates
=============================

Hardware, boot and recovery
---------------------------

The connected device is GM1920 / OnePlus7ProNR, not an assumed GM191x
guacamole board. Preserve its model, bootloader version, current slot,
partition map, installed firmware and hashes alongside each build.
Android property flash.locked=0 is evidence only, not permission to
flash and not a substitute for bootloader interrogation.

Before a native boot, obtain and validate the exact variant's recovery
procedure and matching stock boot, dtbo, vbmeta and firmware artifacts.
Read-only ADB discovery cannot back up protected block devices as the
unprivileged Android shell. Record this as a recovery blocker rather than
claiming a backup. Do not unlock, erase, repartition, set an active slot,
write boot/dtbo/vbmeta, modify AVB or flash without explicit approval.
No destructive commands are included in these tools.

First identify a kernel source and device tree that support the GM1920
board, including panel, touchscreen, regulators, UFS, PMIC and USB PHY.
Compare actual board IDs/DT compatibles against the proposed port.
Do not substitute the related 7 Pro or 7T Pro device tree without that
comparison. Even a temporary RAM boot needs a verified image, matching
boot format, validated recovery route and a reviewed test procedure.

Kernel/GPU/display investigation
--------------------------------

The current vendor Android kernel exposes a display DRM node and KGSL
GPU interface. A renderD128 node under mdss_mdp does not prove that it
offers the GPU submission interface expected by Mesa Freedreno. Native
Linux testing must distinguish a display-only vendor DRM device from a
working mainline MSM/Adreno renderer.

Verify the selected kernel configuration and device tree for:

* DRM/MSM, the SM8150 display controller, panel/bridge, clocks and IOMMU.
* Adreno A6xx GPU, required firmware and GMU power management. Confirm
  successful probe and firmware load in kernel logs, not only Kconfig.
* Touchscreen, USB device networking/debugging, regulators and charging.
* USB-C role switching, orientation switch, DP mux/PHY, Alt Mode
  negotiation and the display controller's DP routing. Inspect the
  actual selected kernel; options vary by kernel and port.

On native Linux, capture ``modetest -M msm -c`` if the libdrm test tools
are available, DRM connector status/EDID, kernel logs and GPU driver
binding. Avoid taking DRM master while a live Xorg server owns the seat.
If no KMS connector exists, investigate panel/DP probe, DTS endpoints,
power and PHY before changing the desktop. If Mesa cannot submit GPU
work, investigate firmware, MSM ioctls and render node identity.

Freedreno implements GL/GLES for Adreno 2xx-6xx:
https://docs.mesa3d.org/drivers/freedreno.html
This generic support does not certify the current phone kernel.
Xorg modesetting uses KMS and glamor requires compatible GL/GLES:
https://manpages.debian.org/testing/xserver-xorg-core/modesetting.4.en.html

Use modesetting after confirming that combination. The example Xorg
configuration is deliberately not installed by default. Xorg logs must
show which driver was actually selected, whether glamor initialized and
whether DRI3 is available. Software rendering is a temporary debug
limitation, never evidence of GPU acceptance. Do not enable Wayland to
bypass a failed gate.

Root filesystem and reproducible builds
--------------------------------------

Mobian remains preferred. Obtain a verified Mobian ARM64 root filesystem
and adapt its session packages with ``scripts/install-x11.sh``. The
current Mobian device list does not establish GM1920 support:
https://wiki.debian.org/Mobian/Devices
Record image origin, signature verification and SHA256 before use.

If packaging prevents the X11 session, document the exact dependency
conflict and proposed Debian ARM64 plus compatible Mobian package
deviation before building it. Do not silently change distro. No such
deviation has yet been made.

A reproducible release needs a build manifest containing immutable
kernel/source commits and patches, toolchain version, kernel config,
device-tree hash, boot-image parameters, initramfs sources, rootfs hash,
firmware versions/licenses and snapshot-pinned APT repository URLs plus
package versions. The installer uses the target's configured repositories
and records versions, APT policy and sources for diagnosis. It is NOT
itself a reproducible rootfs builder. Reproduction requires restoring
the manifest's exact repository snapshots and package versions.

No root filesystem was downloaded or assembled: a verified GM1920
kernel/DT, matching recovery artifacts and build inputs remain missing.
WSL discovery found only docker-desktop, no native Debian ARM64 build
environment. Cross-compilation or a build container may prepare artifacts;
the phone must boot the resulting native system directly.

USB debugging should remain available through a validated native Linux
USB gadget network plus authenticated SSH, or a documented debug UART.
Configure it in the initramfs so failures before graphical login can be
collected. Do not confuse Android ADB diagnostics with native boot proof.

X11 desktop and mobile integration
----------------------------------

On native Linux preview, then run the installer. It installs the required
Xorg, XInit, XAuth, XInput, libinput, XFCE, Openbox, LightDM and Mesa tools.
Debian supplies the xrandr executable in x11-xserver-utils:
https://manpages.debian.org/unstable/x11-xserver-utils/index.html
LightDM selects the XFCE X11 session, disables competing display-manager
units for future boots and enables graphical.target. It does not restart
the live desktop. Review ``lightdm --show-config`` and any existing
configuration that could override the selected session. Openbox remains
an optional X11 login session. No autologin or permissive xhost is enabled.

Run mobile setup as the desktop user to select Xft DPI (default 180),
48px icons and four EWMH workspaces. This is an initial scaling choice,
not a tested phone setting. Place EtherPocket launcher and Onboard on
the XFCE panel using panel preferences; test their touch targets on the
physical device. Onboard is an X11 keyboard; start it with ``onboard``.
xfce4-power-manager provides the desktop power interface. The power
command reads battery and thermal values without changing policy; raw
thermal temperatures are usually millidegrees C, battery temperature
units are driver-dependent.

Discover touch devices with ``xinput list`` and ``xinput list-props ID``.
Use rotate with the physical panel output and the exact touch device.
It combines rotation, optional normalized calibration and panel mapping
within the entire XRandR framebuffer, keeping touches off the external
display. Test every corner in portrait and both landscapes. Persist the
same touch ID/name, rotation and calibration as arguments in the user's
watcher autostart entry; IDs can change, so prefer a verified unique name.
User overrides live in ~/.config/autostart/etherair-x11.desktop. No
generic calibration matrix is asserted correct for this touchscreen.

The watcher polls XRandR connection/mode changes every three seconds,
and reapplies on long execution gaps after resume. Failures are logged
to session stderr and retried; it does not force suspend on an untested
kernel. Suspend/resume must be tested separately for panel, GPU, touch,
USB and glasses, with authenticated debug access available. Polling is
an initial implementation; an XRandR event loop can replace it later.

Nreal Air
---------

DP output names are discovered. Auto-selection requires one recognizable
phone panel and at most one non-virtual external display; specify names
when ambiguous. A connector is not identified as Nreal solely by its
name. Review EDID identity and advertised modes. The controller selects
1920x1080 only when advertised, otherwise the preferred mode. Extended
desktop places the external display right of the panel. Mirror mode
scales the full phone framebuffer to the external display; aspect ratios
may differ. Transform support and performance require hardware testing.
The tools do not invent EDID modes or promise unsupported timings.

XRandR cannot add missing Type-C/DP kernel support. Required validation:
plug/unplug, connector/EDID detection, actual visible XFCE desktop through
the glasses, extend, mirror and resume. Log modes and failures each time.
During testing USB-C may be occupied by the glasses; keep a working
alternate debug route. Nreal compatibility remains unverified until the
glasses display the real native X11 desktop.

EtherAIR extension contract
--------------------------

The controller is an initial native X11 integration layer, not the full
EtherAIR renderer. The diagnostics capture extension availability and
EWMH properties; workspace commands use wmctrl and display commands use
XRandR. Future application code should use:

* XRandR for output events, modes, placement and transforms.
* XInput2 for touch/device events; negotiate its runtime version.
* XComposite plus XDamage for redirected windows and update regions.
* XFixes for cursor images and regions.
* XTest only for explicitly authorized synthetic input; none is injected
  by the tools supplied here.
* EWMH X11 properties for desktop/workspace and window positioning.
* Native X11 EGL/OpenGL surfaces and Mesa Freedreno for rendering.

Check extension versions at runtime and handle missing capabilities.
XFCE's window manager already owns composition when enabled. A future
EtherAIR compositor must coordinate that ownership and avoid claiming
the compositor selection while another compositor holds it. Future AR
window positioning needs an explicit coordinate/workspace model and
glasses tracking evidence. No Wayland protocols implement core UI here.

Acceptance evidence
-------------------

All device acceptance criteria are pending, rather than silently passed:

1. Native Linux boot: authenticated shell, os-release, uname, mount info
   and hardware identity, proving direct device boot.
2. Xorg: physical Xorg process and log, local seat and visible screen.
3. Session: ``echo "$XDG_SESSION_TYPE"`` and loginctl both report x11;
   a manually exported variable is insufficient.
4. Desktop: photograph/manual observation of physical XFCE or Openbox.
5. Touch: successful corner, gesture and rotated input tests.
6. GPU: ``glxinfo -B``, ``eglinfo``, render node/driver and Xorg glamor/DRI3
   logs, or a precise kernel/firmware/ioctl blocker. llvmpipe is reported.
7. Nreal: ``xrandr --query``, EDID and observed desktop in the glasses,
   including hotplug, mirror and extend, or exact native DP blocker.
8. EtherAIR: display/workspace interaction plus runtime extension probes;
   full compositor/rendering acceptance awaits actual EtherAIR sources.

Run ``etherair-x11 diagnose --output evidence-x11.json`` in the physical
session and preserve the output. It includes xinput, XRandR, GLX/EGL,
extensions, session/process evidence, logs and power data. Review it
locally before sharing because kernel logs can contain device identifiers.
