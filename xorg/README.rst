Experimental native Xorg diagnostics for GM1920
===============================================

0001-skip-uninitialized-output-atoms.patch fixes the null pointer fault
observed with GDB in the Debian modesetting driver's property setter.
The patched module allowed LightDM and an XFCE X11 session to start.
It does not provide Adreno acceleration.

0002-preserve-advertised-mode-refresh.patch is an opt-in display patch.
The downstream DSI driver rejected a mode with nominal refresh zero.
The initial legacy-KMS 1080 test reached a Qualcomm 900E failure. A later
atomic-KMS test using the exact advertised 1440x3120 native timing worked.
scripts/build-xorg-driver.sh omits it from the default module; it requires
the explicit build environment ETHERPOCKET_PANEL_REFRESH_TEST=1.

0003-atomic-refresh-after-shadow-damage.patch replaces unsupported
DIRTYFB refresh with the existing atomic plane-flip helper when shadow
damage is pending. Without it the panel retained the first desktop image
even while XInput2 received real touch events. With all three patches,
atomic KMS and explicit panel brightness 300, the user confirmed visible
XFCE, working touch, menu opening and window dragging.

The verified opt-in module SHA256 is
e127c81a1b2371acd107115e79e459680ff0eed03a807fd41f67d64f139f71a9.
This module is included in the experimental persistent dual-boot root.
Patch 0003 also skips inactive CRTCs and retains damage tracking when
DIRTYFB is unsupported at initialization. Without these cold-boot guards,
the display could stop refreshing even though touch opened applications.

The standalone diagnostic module is built from Debian's matching source
against its ARM64 Xorg SDK. Its private configuration bridge is documented
in the build script; a production package should use the distribution's
complete build configuration and package integration.

The RAM diagnostic configuration explicitly disables acceleration and
uses ShadowFB. Mesa reported llvmpipe, which is a GPU acceptance blocker.
No Wayland session was used. Phone panel and touch are user-verified;
Nreal output remains unverified. Connecting the actual glasses exposed
a separate downstream-kernel Oops: DSI-only backlight scaling was applied
to a DP connector, terminating its commit worker. Kernel patch 0006
guards the DSI cast and is compiled, awaiting the next hardware boot.
See docs/dualboot-2026-10-15.rst for persistent-installation status.
