EtherCamera 0.3: native photo and video application
=================================================

The user explicitly requested the capture application after the initial
hardware-blocked delivery. This supersedes the earlier instruction to defer
the camera UI. The app does not claim that the OnePlus sensors work.

Installed entry: EtherCamera — Aparat, command ``ethercamera-app``. The
existing separate gallery remains ``ethercamera-media``. Both are native
Qt 6 applications, using the same managed per-user EtherCamera D-Bus service.

Use
---

Open EtherCamera from Applications. An available capture device can be
selected and started with explicit confirmation. A fresh JPEG frame returned
by sealed file descriptor enables the shutter. Choose Zdjęcie and Zrób zdjęcie
for a still. Choose Film and Nagraj film, then explicitly choose recording
with the phone microphone or silent recording. Zatrzymaj i zapisz film
finalizes the MP4. Galeria opens the saved media application. Video is limited
to the existing software limits: 640x480, 15 fps, 60 seconds.

No camera starts on launch. The app disables capture without a supported
source, fresh image, unlocked coordinator and granted policy. Denied policy
is changed in existing Settings, not bypassed by the app. Lock/coordinator or
backend loss clears the displayed frame and session; hiding/backgrounding
also releases it. The backend still owns file privacy, camera device access,
microphone consent, recording finalization and sleep/power limits.

Recording uses the existing EtherPower owner's validated CPU/GPU/battery
temperatures and capacity. It rejects missing, invalid or stale telemetry,
stops at 85 C CPU/GPU, 45 C battery or 5 percent capacity, and releases on
power-owner loss. It does not iterate unrelated/unreadable thermal sysfs
nodes. Three additional pure tests cover these limits and freshness checks.

Handset status
--------------

The connected handset is identified by its vendor image as GM1920,
OnePlus7ProNR, the OnePlus 7 Pro 5G family. It has camera hardware; Debian
currently has no working internal sensor capture endpoint. Vendor request,
sync and codec nodes are not listed as usable cameras. The app therefore
shows the internal camera integration blocker instead of a fabricated
preview or an active shutter. No physical frame was obtained in this release.

Matching Android camera/CamX libraries are present on the Android vendor
partition. Their existence does not make them usable by glibc/Qt. They require
the matching Android runtime, binder/HIDL camera and graphics services,
properties, buffer allocation and a Debian-facing bridge. Existing upstream
documentation describes Halium/libhybris adaptation rather than loading the
camera HAL directly into a Linux desktop application:

* https://docs.droidian.org/porting-guide/
* https://docs.droidian.org/porting-guide/debugging-tips/
* https://github.com/libhybris/libhybris

No kernel/boot change, Android partition write, vendor HAL execution, firmware
flash or pop-up motor operation is performed by this application. External
UVC remains the implemented capture provider; it still requires physical
camera acceptance. The internal hardware report remains authoritative:
``ethercamera-feasibility-2026-10-20.rst``.

Validation
----------

The optional, uninstalled ``ethercamera-ui-test`` runner builds the same QML
and controller and operates actual controls through Qt mouse events. The
Python harness supplies a watermarked OFFLINE / NOT A CAMERA FRAME GStreamer
test pattern only on a private D-Bus session/display and temporary HOME.
Production includes no test source or hardware-bypass setting.

The nine scenarios cover no-hardware handset classification at narrow and
wide layouts, consent/cancel, real JPEG FD preview, still saving and H.264 MP4
finalization checked by ffprobe, lock revocation, disconnect, backend death,
background cleanup, policy denial and preserving source startup errors. These are software acceptance tests,
not physical sensor or microphone tests. Existing backend and gallery tests
are retained. Exact package/hash and device results are recorded in evidence.

Full built-in camera photography still needs device-specific Android camera
runtime integration and a first verified physical sensor frame. This app
alone does not complete that lower-level port.
