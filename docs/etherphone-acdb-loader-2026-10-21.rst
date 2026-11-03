Original ACDB loader identified and dynamically loaded — 2026-10-21
==================================================================

Result
------

The matching factory loader is already on this handset's Android vendor_b
partition: /lib64/libacdbloader.so (Android path
/vendor/lib64/libacdbloader.so). Using the phone's own system_b Bionic runtime,
it was successfully dynamically loaded under the running Debian kernel in an
isolated temporary chroot. The original libaudcal.so parser and dependencies
were also present in the probe process's /proc/self/maps; exit status was 0
and stderr was empty. This is runtime linking verification, not ACDB parsing,
voice calibration upload or working call-audio verification.

Exact source and identity
-------------------------

* Hardware-specific vendor fingerprint:
  OnePlus/OnePlus7ProNR_EEA/OnePlus7ProNR:10/QKQ1.190716.003/2111271450:user/release-keys
* Vendor Android version: 10, API 29; board msmnile.
* ACDB revision: version:18827Q-acdb-20191228.
* Loader: ELF64 AArch64, 119504 bytes; SHA256
  cca7ce1674e4a8bb647fd44641022c2bf4a6569cda5ee0abcafb71028b82b789.
* Parser: vendor_b:/lib64/libaudcal.so; SHA256
  d87937a172737cd50344626a92dfdabfbdeef7d3282e7df5da8cc8dd6d31abc1.
* Runtime: system_b:/system/apex/com.android.runtime.release.apex, extracting
  its apex_payload.img with debugfs into temporary ordinary files. Required
  components are /bin/linker64 and /lib64/bionic/{libc,libm,libdl}.so inside
  that image. system_b:/system/bin/linker64 is a symlink into this APEX.

The loader exports acdb_loader_init_v2, init_v3, init_v4, send_voice_cal,
send_voice_cal_v2 and reload_vocvoltable entry points. Its strings identify
/vendor/etc/acdbdata and /dev/msm_audio_cal. It depends on Android libc,
libaudcal, libtinyalsa, libion, libdiag indirectly, HIDL/Binder and
vendor.oneplus.hardware.param@1.0.so. A single .so copied into glibc's library
directory is insufficient. No replacement from another phone is needed to
establish this dynamic-load result.

Reproducible checks
-------------------

scripts/audit-etherphone-acdb-loader.py reads the existing vendor_b and
system_b files with debugfs without write mode. It records hashes, ELF
architecture, exported loader/parser symbols, dependency names and the
Bionic APEX symlinks. Dependencies for stock toybox, used only as a test
executable, are included separately via probeUtilityNeeded.

scripts/check-etherphone-acdb-runtime.py copies those verified files into a
TemporaryDirectory, extracts the original APEX runtime, and runs three checks:

1. Original linker64 --help: exit 0.
2. Original toybox true without preload: exit 0.
3. Original toybox cat /proc/self/maps with
   LD_PRELOAD=/vendor/lib64/libacdbloader.so and LD_BIND_NOW=1: exit 0.
   Both libacdbloader.so and libaudcal.so were mapped, together with their
   dependencies. There were no link errors or stderr output.

Each command runs in private mount and network namespaces, a chroot and
unprivileged UID/GID 65534. The downstream kernel does not support the tested
PID namespace operation, so the probe uses proc's normal user access checks
instead. Only /dev/null is bind-mounted in the private namespace; no modem,
audio-calibration, ALSA, Binder or other handset device nodes are exposed.
No init/send calibration function is called. The temporary files and mounts
are removed when the probe exits. No Android service or Android OS is booted,
and no host library paths, services, partitions or audio routes are changed.

The initial sandbox lacked a usable /dev/null, causing Bionic startup failure
before ACDB loading. Supplying the ordinary /dev/null bind mount resolved it.
The optional --trace mode uses a temporarily extracted Debian ARM64 strace
binary; it is not installed as a package on the handset.

Evidence:

* evidence/etherphone-acdb-loader-selection-2026-10-21.json
* evidence/etherphone-acdb-runtime-check-2026-10-21.json

Remaining integration
---------------------

The loader is identified and linkable with its matching runtime. It has not
been installed as a persistent calibration service. Next, a small Bionic
helper must invoke the exact init ABI and the voice-calibration entry point,
using the handset's original ACDB files and verified RX/TX device IDs. The
OnePlus parameter service dependency and regional dataset selection need
inspection before calling init. No region or ACDB device IDs were guessed.
The existing audio_platform_info.xml overrides some device IDs but does not
by itself enumerate every voice route's calibration pair.

Only after the correct voice blocks are uploaded through the existing kernel
audio-calibration API can the dedicated VoiceMMode1 session and a real call
be tested again. Voice audio, echo handling, volume, earpiece and Bluetooth
call audio remain unverified. This loader result does not establish IMS or
VoLTE registration.

Primary references checked during research
------------------------------------------

The project documentation for libhybris describes using Bionic libraries from
glibc systems and the associated runtime dependencies. This probe used a
separate Bionic process instead of libhybris:
https://github.com/libhybris/libhybris

q6voiced starts/stops dedicated voice PCM streams in response to call events;
it is not an ACDB calibration loader:
https://gitlab.com/postmarketOS/q6voiced

Android 10 linker source describes direct invocation of the runtime linker:
https://android.googlesource.com/platform/bionic/+/refs/tags/android-10.0.0_r47/linker/linker_main.cpp

The handset's own partition files and process-map evidence above, rather than
another model's successful port, support the selected loader/runtime result.
