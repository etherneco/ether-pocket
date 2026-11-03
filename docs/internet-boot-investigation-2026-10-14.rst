Internet research and boot-image investigation
=============================================

Device scope
------------

The attached phone is GM1920 / OnePlus7ProNR / project 18827, the 5G
variant. The postmarketOS guacamole deviceinfo selects
qcom/sm8150-oneplus-guacamole and documents a port for the regular 7 Pro.
That file does not establish GM1920 compatibility. No verified ready-made
native Mobian/X11 image for GM1920 was found in this research.

Primary sources checked:

* https://wiki.postmarketos.org/wiki/OnePlus_7_Pro_(oneplus-guacamole)
* https://gitlab.com/postmarketOS/pmaports/-/raw/master/device/testing/device-oneplus-guacamole/deviceinfo
* https://twrp.me/oneplus/oneplus7pro.html
* https://github.com/topjohnwu/Magisk/releases/tag/v30.7
* https://topjohnwu.github.io/Magisk/tools.html

Downloaded tools and reference data
------------------------------------

Official Magisk-v30.7.apk was downloaded solely to extract the standalone
x86_64 magiskboot tool for the WSL build host. The APK was not installed on
the phone; Magisk rooting was not performed. Its SHA256 matched GitHub's
release asset digest:
e0d32d2123532860f97123d927b1bb86c4e08e6fd8a48bfc6b5bee0afae9ebd5.
The download and extracted tool are in sources/boot-diagnostics.
The postmarketOS guacamole deviceinfo was also downloaded there as a
reference, not as a declaration of support for this 5G phone.

Concrete packaging discrepancy
-------------------------------

magiskboot successfully parsed the working official TWRP image and the
two native image layouts. Its reports are evidence/magiskboot-*.txt.
The known-working TWRP carries OS-version metadata 16.1.0 and patch-level
metadata 2099-12. These are boot-header values, not the actual installed
Android version. Our initial reference-kernel packaging omitted both.
This is a confirmed difference in packaging, not a confirmed failure cause.

scripts/repack-preserved-reference.py uses magiskboot to preserve the
original recovery image's metadata and padding, replace its RAM userspace
with the native Linux mini-initramfs, and add native command-line flags.
It checks the original kernel blob is unchanged byte for byte and that
the OS metadata and kernel/ramdisk addresses are preserved. It does not
disable AVB or write phone partitions.

The resulting native-reference-preserved.img is 32464896 bytes, SHA256
dc909cf712affa5c4f920078ad2fe17472de42654e2f93b3419370d121e6928b.
Fastboot Sending and Booting returned OKAY, recorded in
evidence/native-reference-preserved-attempt.txt. No native USB interface
was observed after handoff. Preserving the header has therefore not
established a successful native boot or resolved the blocker.

Remaining uncertainty
----------------------

The physical Fastboot screen can remain displayed during a kernel hang;
it does not independently establish that execution returned to the
bootloader. No usable native kernel log has been obtained. Bootloader
handoff, the appended skip_initramfs parameter, PID 1 execution, and USB
gadget initialization must be distinguished using additional evidence.
The downloaded tool works on the build host; it is not a working native
desktop image for GM1920. Native X11/Freedreno/Nreal acceptance is pending.

Update after live diagnostic work
---------------------------------

The RAM debug blocker was subsequently reproduced and fixed: the Qualcomm
RNDIS configfs driver rejects setting dev_addr before gadget binding, but
our set -e helper did exactly that. The recovery kernel also lacks devtmpfs,
requiring a tmpfs/mdev fallback for /dev. After both changes, the native
mini-initramfs booted using the verified recovery kernel. Windows RNDIS,
DHCP and authenticated SSH worked, and PID 1 was native BusyBox with only
RAM and virtual mounts. The complete evidence and remaining Xorg/kernel
limitations are recorded in docs/device-execution-2026-10-14.rst.
