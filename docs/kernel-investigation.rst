GM1920 kernel investigation, 2026-10-14
=====================================

The live kernel config was retrieved through read-only ADB from
/proc/config.gz. This succeeds as the Android shell even though board
device-tree properties and DRM status/modes are denied by permissions.
Preserve the compressed config, expanded text and generated audit.

Confirmed live configuration blockers
------------------------------------

CONFIG_VT is disabled. The intended normal local LightDM/Xorg path
requires virtual-terminal support; an Xorg package installation does
not supply missing kernel virtual terminals. CONFIG_DEVTMPFS is also
disabled: the standard native Linux device-node provisioning path needs
to be enabled or explicitly replaced. Android currently provisions /dev
through its own userspace. This is not evidence that Xorg is impossible
with every custom startup arrangement; it blocks the planned standard
native Debian startup path using the current kernel.

CONFIG_SYSVIPC is disabled as well. This limits the SysV shared-memory
facilities used by X11 clients/MIT-SHM; it is a native-stack prerequisite
to address, not proof that every X11 client or the server cannot start.

The running kernel has CONFIG_DRM_MSM=y, CONFIG_DRM_MSM_DSI_STAGING=y,
CONFIG_QCOM_KGSL=y and CONFIG_QCOM_KGSL_IOMMU=y. The GPU currently exposes
KGSL while card0/renderD128 belong to the display device. Generic
CONFIG_DRM_MSM=y is therefore insufficient to certify the mainline MSM
GPU ABI used by Debian Mesa. GLX/EGL and GPU ioctls remain untested.

Candidate board reference
-------------------------

OnePlus public source branch oneplus/SM8150_SDX50M_Q_10.0 points to
commit 31bebb6ffc476f51986bd04502a76ffbd9e2fa7a:
https://github.com/OnePlusOSS/android_kernel_oneplus_sm8150/tree/31bebb6ffc476f51986bd04502a76ffbd9e2fa7a

Its guacamole-sdx50m-overlay-pvt.dts identifies model
SDX50M MTP 18827 21 22 and board ID 0x01010008, revision 1.
The phone's ro.boot.prjname reports 18827. This is a useful vendor
board-source lead; production hardware revision, selected DT overlay,
boot format and exact firmware/source alignment still need validation.
The branch may predate the installed November 2021 kernel build.
Do not infer flash compatibility from project number alone.

The vendor DRM Makefile includes DP USBPD, HPD, AUX and SDE display
objects. This explains why a DP connector directory can exist; it does
not establish a working glasses connection or native userspace support.
Vendor reference files are saved with their original license comments
under evidence/vendor-reference; source paths and commit are recorded
in ORIGIN.txt and vendor-kernel-candidates.json.

An upstream Linux qcom device-tree directory query found SM8150 HDK,
MTP, Surface Duo and Sony boards, but no guacamole/GM1920 file. The
query is saved in evidence/upstream-sm8150-devicetrees.json. This is
evidence about that upstream directory at query time, not a claim that
no downstream mainline port exists anywhere.

Work prepared for the kernel subsystem
-------------------------------------

kernel/x11-native.fragment enables VT/console, devtmpfs, UNIX sockets,
PTYs, evdev, SysV IPC and rootfs/runtime filesystem support. It is an
experimental input for an eventual verified GM1920 build, not a patch
that provides mainline GPU or board support. Audit an effective .config
after merging and running olddefconfig::

    python3 scripts/audit-kernel.py path/to/.config --output kernel-audit.json

The audit fails when the initial native prerequisites are missing. It
does not certify systemd compatibility in full, device-tree correctness,
firmware loading, graphics acceleration or physical display output.

Next kernel work requires a complete pinned source tree and toolchain,
the matched GM1920 board revision and stock recovery artifacts. Compare
the vendor display/GPU ABI with the chosen Mesa build before deciding
whether to adapt the vendor kernel or port the board to a mainline-based
kernel. A vendor KGSL Mesa backend would need explicit build/runtime
validation with native X11/EGL/GBM; installing standard Mesa packages
does not establish that route. A mainline-based port would need verified
GM1920 panel, touch, UFS, power and Type-C/DP support. Neither route has
been claimed working, and no Wayland fallback is introduced.
