EtherCamera 0.2 continuation — 20 October 2026
===========================================

This continuation implements missing independent software rather than treating
the first audit report as completion. Internal physical capture is still
blocked, and no production sensor frame is claimed. The initial 0.1 delivery
report remains a historical baseline; this document describes the 0.2 changes.

Implemented in 0.2
------------------

* Native Qt6/QML EtherCamera Media application: camera-owned images, videos
  and documents; local-date grouping, search/type/album filters, paged results,
  asynchronous cached thumbnails, full-screen image viewing and video playback
  with pause/seek, album editing, explicit export, delete confirmation, file-URI
  clipboard sharing, document correction/rotation and multi-page PDF selection.
  Controls are sized for touch. There is no fake camera preview or capture UI.
  The software Qt scenegraph did not paint QML VideoOutput despite receiving
  decoded frames. Playback now uses QVideoSink -> QImage -> image provider,
  with software decoding by default. Acceptance checks both decoded-frame
  count and visible test-pattern pixels; a running media clock is insufficient.
* Media APIs ListMediaPage, GetThumbnail, SetAlbum, MediaInfo and ExportMedia.
  Workers perform indexing/thumbnail/copy work outside the service event loop.
  A second unlock/owner check rejects a worker result if permission changed
  while it was processing. Only the camera-owned directory is indexed.
* Persisted photo/video defaults with independent resolutions/frame rates,
  JPEG/PNG selection, microphone preference and deny/ask-each-time policy.
  Atomic private storage; invalid stored policy denies capture. Revocation
  closes an active lease. No preference constitutes microphone permission.
* Persisted bounded usage history containing only allowlisted event types and
  timestamps, never purposes, references, file paths or decoded QR payloads.
* StartRecordingWithAudio: separate per-recording consent, the existing
  EtherAudio StartCapture/StopCapture owner, FD transport, timestamped raw
  S16LE 16-kHz mono parsing, AAC/H.264 muxing and lease/FD cleanup before EOS.
  Silent StartRecording remains compatible. Software limits remain 640x480,
  15 fps and 60 seconds pending physical thermal/performance acceptance.
* ManualCode with EAN/UPC check digits, Code39/128 validation and explicit
  manual/not-sensor provenance. Wi-Fi escapes and vCard/MECARD fields are
  parsed as data. No network join, contact import or URL launch is automatic.
* CaptureClient SDK: persistent owner connection, provisional media review,
  explicit confirmation, retake/cancel cleanup, multiple photos, barcode jobs
  and separate microphone choice. Business record associations stay in the
  calling inventory application. Source for EtherInventory is not present;
  an application-side deployment is not claimed.
* EtherHardware camera topology events trigger discovery without idle polling.
  A node disappearing during hotplug no longer crashes enumeration. Activity
  distinguishes an active hardware pipeline from a merely reserved session.
  Native discrete formats/rates and focus/exposure controls are structured in
  the API; the complete V4L2 text remains available for other format types.
  UVC decodebin handles supported raw/compressed input, and output sizes are
  explicitly identified as potentially software scaled.
* Existing Camera Settings now edit real persisted defaults/permissions.
  No separate Settings program or distributor was introduced.
* Source EXIF/GPS removal is tested for both JPEG and PNG output. A denied
  camera policy stops capture immediately even if storage failure prevents
  persisting the policy; the current process continues to deny requests.

Real privacy coordinator integration
-------------------------------------

The prior staging-only restriction was reviewed against the actual EtherLock
implementation. Its coordinator can report privacy/session state while
automatic locking remains disabled. The existing policy file was absent,
DEFAULTS.enabled is false, and no active-lock marker existed. The coordinator
was started and checked: ready=true, phase=unlocked, enabled=false, locked=false,
enforced=false. Its policy file and the running shell PID were unchanged.
Evidence: ethercamera-lock-coordinator.json.

The camera unit now Wants/After etherlock.service, without enabling automatic
locking or bypassing its administrator evidence gates. Existing lock, caller
exit, coordinator loss and suspend signals still stop managed capture. The
media viewer clears its contents and stops playback on privacy revocation.
Same-UID applications/direct device-node access remain outside this cooperative
API boundary. Authentication, physical lock/wake and secure suspend acceptance
from task 06 are still not claimed by this camera work.

The final backend suite contains 31 tests. All must pass without skips on
the build host and ARM64 phone; the final manifest binds results to packages.

Actual Android loader feasibility progress
------------------------------------------

Read-only debugfs inspection establishes that /system/bin/linker64 in system_b
is a symlink to /apex/com.android.runtime/bin/linker64. Android 10 ships that
runtime in com.android.runtime.release.apex, not as a plain system binary.
The runtime APEX and payload were copied to a disposable Debian /var/tmp
directory without mounting or writing Android partitions. Only linker64
--help was executed in a transient systemd sandbox: UID/GID 65534, no
capabilities, NoNewPrivileges, PrivateDevices, DevicePolicy=closed, private
network, read-only root, 128MiB and five-second limits. It exited successfully.
All temporary copies were removed. No camera HAL/provider, Android init,
firmware or motor was executed. Evidence: ethercamera-android-loader-probe.json.

This proves loader execution, not camera capture. The complete matching
Android camera runtime, properties/services, CamX, graphics buffer allocation,
safe motor-service integration and a Linux-facing bridge still need adaptation.
The Android provider is not a direct GStreamer V4L2 source. Existing open-source
approaches were checked against their upstream documentation:

* https://github.com/libhybris/libhybris — requires a stripped Android runtime
  and adaptation services, rather than treating bionic HALs as glibc plugins.
* https://docs.sailfishos.org/Reference/Core_Areas_and_APIs/Multimedia/ —
  gst-droid exposes hardware camera/media through droidmedia and libhybris.
* https://github.com/sailfishos/droidmedia — Android-side multimedia adaptation
  whose API/version/build must match the device's Android BSP.

No prebuilt compatible libhybris/droidmedia/gst-droid packages or matching
device adaptation are installed in Debian. No unreviewed Android init or
unrestricted container is started against the live phone.

Acceptance and remaining hardware gate
---------------------------------------

The Python suite now includes persisted settings/history, media paging,
thumbnails/export, SDK review lifecycle, manual code provenance, microphone
consent/FD cleanup and real GStreamer H.264/AAC muxing of explicitly OFFLINE
test video plus a generated tone. ffprobe verifies both tracks, duration and
start-time alignment. This is not a microphone/sensor synchronization test.

The real backend and native media application are exercised on private D-Bus
and authenticated Xvfb displays with private HOME. Only the test locker is
substituted, on that disposable bus. The production service/UI run unchanged.
Acceptance includes thumbnails, album filtering, export, preferences surviving
backend restart, manual-code provenance, denied microphone consent, gallery
at narrow/wide sizes, full image, video decode and clearing on lock revocation.
The test images are visibly watermarked OFFLINE / NOT A CAMERA FRAME; the
generated video is a test pattern. Private fixture files are removed afterward.

See ethercamera-media-amd64/acceptance.json, ethercamera-media-arm64/
acceptance.json, ethercamera-tests-amd64.txt and the final installed-package
test log. Camera Settings is separately covered by all four existing EtherShell
light/dark Settings suites; activation requires the exact tested package hash.

Still required for the original full Definition of Done: a first verified
physical frame via a safe internal bridge or an attached compatible UVC camera;
then the camera preview/capture UI, real photo orientation/focus/controls,
camera plus microphone recording acceptance, real scanning, hotplug and
suspend/recovery tests, and actual mobile CPU/memory/battery/thermal measures.
Browser internal-camera adaptation and application-side inventory UI cannot
be declared deployed from an SDK or a discovered device node. Existing Linux
browser UVC permissions/selection are not bypassed or silently granted.

Task 07 remains incomplete at that hardware gate. The independently testable
media, preferences, permission, audio-mux and reusable caller components have
been implemented rather than simulated. Final package hashes, live/staged
shell disposition and test counts are recorded in ethercamera-delivery.json.
