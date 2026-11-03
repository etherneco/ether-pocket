USB device execution on 2026-10-14
=================================

User authorized execution on the connected phone and confirmed the
bootloader screen reported "device state - unlocked". Work proceeded on
serial 548cb338, model GM1920, project 18827. No flash, erase, format,
active-slot change or AVB modification command was issued.

Completed on the physical device
--------------------------------

* Entered Fastboot from Android through ADB. Windows initially had no
  driver for USB VID_18D1/PID_D00D (problem code 28).
* Installed the matching Google driver from Microsoft Update Catalog,
  verified its Microsoft WHCP catalog signature, and confirmed the
  interface became healthy. Driver Store published name: oem87.inf.
* Fastboot independently confirmed unlocked=yes, current-slot=b,
  max-download-size=805306368 and a successful, bootable slot b.
* Fastboot fetch is unsupported on this bootloader.
* Temporarily RAM-booted TeamWin 3.4.0-0. The image SHA256 matched the
  official checksum. TeamWin's legacy device initialization explicitly
  maps project 18827 to GM1920. Recovery actually identified GM1920 and
  provided root ADB. This recovery is preparation, not native Mobian.
* Read boot_a/b, dtbo_a/b and vbmeta_a/b without writing those partitions.
  All six backups were checked for their expected sizes and their host
  SHA256 matched the SHA256 calculated directly on the phone. See
  recovery/stock-backup/manifest.json. These are boot recovery backups,
  not a backup of personal data or all firmware partitions.
* Read the live FDT and hardware evidence. The board is
  SDX50M MTP 18827 15, rf_version=1, selected stock dtbo index=35.
  Touchscreen input appears as touchpanel, event5 in recovery.

Artifacts built on the host
---------------------------

A dedicated WSL distro EtherPocketBuild was imported into build/wsl
using a digest-verified official Debian AMD64 layer. It is exclusively
a cross-build environment. The phone target is ARM64 and does not run
in WSL, a container, Android, Termux or proot.

The kernel candidate combines pinned OnePlus sources:

* Kernel: 31bebb6ffc476f51986bd04502a76ffbd9e2fa7a, SDX50M Android 10.
* Vendor code: 5fba057468048661d4cbc8cc50303575a42a37da, SM8150 Android 10.

The source contains a DVT overlay with the exact 18827 15 board model.
RAM test images instead use the original DTB from the backed-up boot_b
and the stock header-v2 layout. They do not replace dtbo or vbmeta.

Experimental changes are recorded in kernel/patches and the native
configuration fragment. They enable initial Linux VT/device/IPC support,
restore an omitted Kconfig declaration, repair two vendor prototypes,
a debug-buffer bound and a logging format, and place RTIC data inside
the real allocated/zeroed BSS. SELinux and RTIC were not disabled.

The public source omits panic_flush.c. RAM-only candidates omit its
panic hook and use standard emergency_sync for the affected SysRq hook.
They do not mount Android filesystems. This omission must be resolved
before considering a persistent production kernel. Stock binary modules
are not used; MODVERSIONS is disabled to avoid legacy absolute CRC
relocations with the newer linker. GCC 12 and binutils versions are
recorded in build-host-packages.tsv. Legacy format/prototype warnings
remain visible but are not promoted to errors. Linker RWX-segment
warnings remain a limitation of this experimental old kernel build.

The first candidate compiled and was packed with an 8 MB native Debian
ARM64 initramfs containing BusyBox, authenticated Dropbear SSH and USB
RNDIS/DHCP debug networking. It has no Android framework and mounts no
internal phone storage. A trap can switch PID 1 to a separately verified
Mobian rootfs mounted in RAM.

The full ARM64 rootfs was built from pinned Mobian recipes commit
c39f05e9e54df98e4f5e249c44f9689e3aaecae3, choosing the custom xfce recipe.
It contains mobian-base, Xorg, LightDM and XFCE. Archive XZ integrity and
package records were checked. Source LF normalization is necessary after
Windows Git checkout. During the successful recipe execution, the outer
wrapper was edited, causing a trailing command error after "Recipe done";
the archive itself was then independently verified. The current wrapper
has passed Bash syntax checks. Do not call the overall first wrapper run
successful based solely on the completed recipe.

The RAM-only rootfs enables temporary XFCE autologin, adds the task's SSH
public key for debugging and masks root repartition/growth services. The
generic native installer retains its separate, non-autologin behavior.
Local test credentials and private keys are in the ignored build folder;
they are not included in public source files or logs.

First native RAM test and current blocker
-----------------------------------------

Fastboot accepted native-mini-boot.img, 22814720 bytes, SHA256
4c6209760c232255eadc4c1f5022db28c9ef11b4f2ec4bbef898ec48ffc7db12.
"Sending" and "Booting" both returned OKAY. This proves handoff by the
bootloader only, not successful kernel/userspace execution.

After handoff, no phone USB interface was observed and TCP port 22 at
the intended point-to-point address was unreachable. The phone's screen
cannot be observed by these tools; the user was asked to report its state.
Native Linux boot, Xorg, XFCE, touch and GPU acceptance remain unverified.
The full Mobian rootfs has not yet been transferred to the phone's RAM.

The running candidate's firmware userspace fallback was enabled. Missing
firmware could stall early probes; this is a hypothesis without a kernel
log, not a confirmed cause. A second candidate disables the legacy
userspace firmware fallback as recommended for native udev, while keeping
direct kernel firmware loading. It compiled and was packaged as
native-mini-boot-no-fw-fallback.img, SHA256
e2f904564e61979d399a1d37a204d187e80e647eca3ccc28367e7766b3edebd3.
After a physical reboot by the user, Android and ADB returned successfully.
An ADB reboot to the bootloader restored Fastboot after approximately
20 seconds. The installed bootloader driver was present with no PnP error.
Temporary TWRP boot also succeeded again. Recovery exposed a 262068-byte
console-ramoops record, copied verbatim to
evidence/previous-boot-console-ramoops.bin. The contents are badly corrupted
and include stock-kernel fragments; they do not establish the native
candidate's failure cause. /proc/last_kmsg was absent.

The second candidate was then sent using fastboot boot. Both Sending and
Booting returned OKAY, recorded in
evidence/native-mini-no-fw-fallback-attempt.txt. No native USB interface
appeared, and the user again reported the Fastboot screen. Fastboot USB
communication was unavailable after that handoff. Firmware fallback has
not been established as the cause.

The stock boot kernel is a raw ARM64 Image, whereas the first two native
candidates used Image.gz. A third candidate matches the raw kernel format:
native-mini-boot-raw.img, 45527040 bytes, SHA256
e7894e36848e8affd82a4d95a3979077a2fe0443c15e84b9ca8f54a3c5ba7b62.
It retains the second candidate's configuration and stock DTB. Its ARM64
Image magic was checked during packaging. After the user restored Android,
ADB and Fastboot were detected again. The raw candidate was sent with
fastboot boot; Sending and Booting returned OKAY, recorded in
evidence/native-mini-raw-attempt.txt. No native USB interface appeared and
the user reported the Fastboot screen again. That screen alone does not
distinguish a kernel hang with unchanged display from a bootloader return.

Stock and native raw Image headers have matching text_offset 0x80000,
flags 0xa and ARM64 magic. Image memory sizes are respectively 0x2731000
and 0x2734000. These checks do not show a gross memory-size discrepancy.
The mini-rootfs init and USB scripts have LF line endings. Neither kernel
compression nor firmware fallback is established as the failure cause.
Native X11 deployment remains blocked on early kernel/USB bring-up without
a usable native kernel log. Further image trials require evidence of the
failure stage; do not claim a desktop or GPU acceptance result.

Controlled reference-kernel diagnostic
--------------------------------------

The user again restored Android, and ADB reported sys.boot_completed=1.
A controlled image reused the exact kernel blob (including its appended
DTB) from the SHA256-verified TWRP image that had booted successfully. It
used recovery's header-v0 layout, kernel/ramdisk addresses and command line,
including skip_override, adding the native RAM opt-in and rdinit=/init.
Only the recovery userspace was replaced by the native mini initramfs;
no Android framework was included or phone partition mounted by that init.
The packaging script is scripts/pack-reference-kernel-test.py.

native-reference-kernel-test.img is 22401024 bytes, SHA256
cde05aca5f6a5e8f5f4170417cc386f029d50ae155d1bf35f67776c49b9793dc.
Fastboot Sending and Booting returned OKAY; the log is
evidence/native-reference-kernel-attempt.txt. The host did not observe a
native USB interface, and the user reported the unchanged Fastboot screen.
This does not prove a kernel crash or a bootloader return. The failure
cannot currently be attributed solely to the rebuilt kernel, since the
known recovery kernel also failed to expose this native RAM debug setup.
Boot parameter handling, initramfs execution and USB gadget initialization
remain unverified stages. A usable early log is needed to distinguish them.
No native X11, GPU, touchscreen, or Nreal acceptance result is established.

Resolved native RAM debug blocker
---------------------------------

Subsequent investigation reproduced the USB setup failure directly in
working temporary recovery. In the downstream Qualcomm kernel,
USB_ETHERNET_CONFIGFS_ITEM_ATTR_DEV_ADDR returns ENODEV while opts->bound
is false. The native USB script wrote dev_addr before binding the gadget;
set -e therefore terminated it before any native USB enumeration. This
was reproduced on the phone and confirmed in
drivers/usb/gadget/function/u_ether_configfs.h. The helper now uses the
kernel-generated MAC addresses and reads ifname only after binding.

The known recovery kernel also lacks CONFIG_DEVTMPFS. The mini init now
falls back to tmpfs /dev, creates essential device nodes and runs mdev -s.
Native ARM64 BusyBox and Dropbear were independently executed successfully
inside a RAM-only chroot in recovery before rebuilding the initramfs.
These are diagnostic checks, not the final native boot acceptance.

An unbound RNDIS probe reproduced the failure before the correction.
A corrected temporary bind created usb0 and enumerated on Windows; the
test automatically restored recovery's working ADB gadget. Evidence is
in recovery-native-userspace-check.txt, recovery-usb-gadget-probe.txt and
recovery-rndis-bind-check.txt.

The fixed initramfs was repacked using the unchanged verified recovery
kernel and preserved metadata. native-reference-fixed.img SHA256 is
a6bcac010f74b696b430864f8ce28fb153991e15a6308cb0359be54922362b66.
Fastboot boot accepted it. Windows then detected a healthy Remote NDIS
Compatible Device and DHCP configured 10.77.0.1/24. An SSH connection to
10.77.0.2 succeeded with the task key and pinned host key. uname reported
ARM64 kernel 4.14.117-perf+; PID 1 was /usr/bin/busybox running the native
init script. Mounts were rootfs and virtual/RAM filesystems only, without
phone storage mounted. This confirms native Linux RAM bootstrap execution.
Logs: native-reference-fixed-attempt.txt, native-reference-fixed-ssh.txt,
native-reference-fixed-dmesg.txt and native-reference-fixed-hardware.txt.

This resolves the previously invisible native debug interface for the
reference kernel. It does not yet validate the custom rebuilt kernel.
The reference kernel has no VT or /dev/tty0, so it is a diagnostic stepping
stone rather than an Xorg acceptance result. Mobian, X11, Freedreno and
Nreal testing remain to be completed with a suitable native kernel.

Next steps depend on the physical screen state and USB recovery. Restore
communication through the known temporary recovery, collect pstore or
last-kernel logs where available, then perform the next RAM test. Do not
substitute a flash operation for an unavailable USB debug interface.
Do not claim native X11 or Nreal compatibility from the Fastboot receipt.
Persistent dual-boot follow-up, 2026-10-15
========================================

The later native custom-kernel/Mobian disk-root and physical X11 bring-up
supersede the initial RAM-only status recorded below. The user confirmed
visible XFCE and touch-driven desktop updates. Android data was reset
with explicit authorization and partitioned to 32 GiB; Mobian occupies
208,467,374,080 bytes on sda21. Native boot_a, DTBO A and vbmeta A are
installed; Android boot_b and signed vbmeta_b remain original. The final
type-aware selector completed Mobian -> Android -> Mobian, preserving a
test file. See docs/dualboot-2026-10-15.rst for details and limitations.

