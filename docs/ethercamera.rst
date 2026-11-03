EtherCamera 0.3.0
=================

Status: independent software baseline; internal hardware blocked. See
ethercamera-feasibility-2026-10-20.rst. The native EtherCamera application was
added at the user's explicit request. Its shutter requires an actual fresh
frame; internal sensors remain unavailable. Settings includes diagnostics,
persisted defaults and managed camera permission policy. The native media
library is independent of capture. See ethercamera-app-2026-10-20.rst.

Architecture
------------

``core.py`` contains pure policy, owner sessions, private media and scanner;
``devices.py`` discovers V4L2 candidates without streaming; ``provider.py``
owns a bounded GStreamer UVC pipeline; ``documents.py`` performs offline
OpenCV/Pillow processing. ``audio.py`` leases an explicitly authorized microphone through EtherAudio.
``capture_client.py`` provides the caller review/confirm/retake workflow.
``service.py`` exposes versioned session D-Bus
control independent of Qt. ``cameraclient.*`` and ``CameraPage.qml`` integrate
with the existing EtherShell Settings -> Applications -> Camera route. A
managed activity indicator and Quick Settings shortcut are in EtherShell.

Install the ARM64 Debian package through the existing local package/update
workflow. No new distributor exists; distributor.json deliberately reports
hardware-blocked. Required packages provide ZXing-C++ and OpenCV. Optional
recommended packages provide software H.264 encoding/parsing; missing video
plugins return an explicit error.
No daemon starts a sensor at installation or login. The camera service starts
the existing EtherLock coordinator; its automatic-lock policy is unchanged.
``ethercamera-media`` opens the Qt6 media browser without starting a camera.
``ethercamera-app`` opens the native photo/video application; starting a
supported camera and using the microphone each require explicit consent.

Commands (run as the graphical session user)
-------------------------------------------

::

   systemctl --user daemon-reload
   systemctl --user enable --now ethercamera
   ethercamera state
   ethercamera refresh
   ethercamera report > camera-diagnostics.json
   ethercamera media
   ethercamera-media
   ethercamera configure '{"format":"PNG","videoFps":10}'
   ethercamera manual EAN-13 5901234123457
   ethercamera photo /dev/video8 --consent --purpose 'Inventory item photo'
   ethercamera scan /dev/video8 --consent --purpose 'Inventory barcode'
   ethercamera video /dev/video8 --consent --seconds 5

Replace the example node with a discovered uvcvideo capture device. Commands
refuse Qualcomm codecs, the request manager and unsupported internal sensors.
Scan output is data only; the caller must ask before opening a URL, importing
a contact or joining Wi-Fi. Video is silent by default. Add
``--microphone-consent`` only after a separate explicit microphone choice;
StartRecordingWithAudio obtains a 60-second EtherAudio lease and muxes AAC with
H.264. Offline fixture mux/decode tests pass; physical camera/microphone sync
and quality remain unverified.

D-Bus version 1
--------------

Session bus name/interface com.etherneco.EtherCamera1, object path
/com/etherneco/EtherCamera1. Methods use JSON for bounded structured metadata.

* GetState() -> s: cached devices, activity, limitations, usage, job states.
* Refresh() -> s: enumerate formats/controls while idle; no sensor stream.
* RequestSession(s device, s purpose, b consent, s optionsJSON) -> s token.
  Options: width, height, fps, format (JPEG/PNG). Single owner, five-minute
  lease; no persistent grants. Device must advertise capture-only UVC.
* StartPreview(s token): acquire logind sleep inhibitor, start real V4L2 source.
* GetFrame(s token) -> h: sealed memfd containing latest fresh JPEG, capped
  at 30 requests/s and 16 MiB. Caller closes returned FD. No raw frame arrays
  in D-Bus. The camera preview consumer is gated on a physical capture path.
* CapturePhoto(s token) -> s metadata: only after a fresh physical frame;
  JPEG/PNG saved in camera-owned Pictures/EtherCamera with UUID reference.
* SetControl(s token, s control, i value): only allowlisted standard UVC
  integer controls actually enumerated by v4l2-ctl. Driver validates range.
  zoom_absolute is labelled according to driver, never claimed optical.
* StartRecording(s token), StopRecording(s token) -> s metadata: restart
  pipeline with x264/mp4 branch; EOS finalizes file. Optional encoder/parser
  required. Video defaults are independent of photo resolution. Limits:
  640x480, 15fps, silent by default, 60s. No hardware acceleration claim.
* StartRecordingWithAudio(s token, b microphoneConsent): separate explicit
  microphone consent, EtherAudio source selection/policy, raw S16LE 16kHz
  mono FD, timestamped GStreamer parser and AAC/MP4 mux; all exit paths release
  the microphone lease and FD.
* Scan(s token, b continuous) -> s job. ZXing decodes real fresh frame;
  continuous mode suppresses repeats for two seconds. Call repeatedly to scan.
* GetJob(s job) -> s: private to submitting unique bus owner, requires unlock.
* ProcessDocument(s mediaReference, s optionsJSON) -> s job: optional corners,
  grayscale, rotation; automatic quadrilateral detection, perspective warp,
  crop and contrast enhancement. Original is retained. No OCR.
* ExportDocument(as references) -> s job: PDF from 1..20 managed images.
* Configure(s JSON) -> s: atomically persisted photo defaults (width, height,
  fps, format), independent video defaults (videoWidth, videoHeight, videoFps,
  videoAudio preference) and cameraPolicy (deny/ask-each-time). The audio
  default never grants microphone access. Deny immediately closes a lease;
  tightening to deny is allowed while locked. Invalid stored policy fails closed.
* ManualCode(s format, s text) -> s: typed manual result, EAN/UPC check digits,
  Code39/128 validation and explicit manual/not-sensor provenance.
* ListMedia(s search) -> s: bounded metadata search, date-sort and album field.
* ListMediaPage(s filterJSON, u offset) -> s: asynchronous pages of 50, with
  search/kind/album filters and nextOffset; scans only camera-owned metadata.
* GetThumbnail(s reference) -> h: asynchronous cached image/video JPEG memfd;
  locked results are rejected again after the worker completes.
* SetAlbum(s reference, s album) -> s: atomic metadata update.
* MediaInfo(s reference) -> s: metadata and managed local file URI after unlock.
* ExportMedia(s reference) -> s: explicit private Documents/EtherCameraExports
  copy; never overwrites existing files.
* OpenMedia(s reference) -> h: read-only file descriptor for viewer/export/
  sharing or inventory attachment, with no duplicate image database.
* DeleteMedia(s reference): remove only managed file and its sidecar.
* Release(s token): stop/finalize recording, release buffers, source and lease.
* DiagnosticReport() -> s: allowlisted devices/status, no image, recording,
  purpose, owner, scan payload, worker result or arbitrary last-error text.

Changed(s JSON) reports lifecycle changes. Never treat device discovery,
PLAYING state or an allocated file as physical capture proof. The verified
map changes preview only after an appsink sample and still only after decoded
dimensions agree and the photograph is saved. Video verification remains
false pending independent playback/audio acceptance.

Inventory/browser integration and boundaries
--------------------------------------------

EtherInventory requests a session on its own persistent D-Bus connection,
shows explicit confirmation, captures, asks the user to accept, then stores
the returned media reference against its own item/repair. Multiple references
are supported without inventory business logic in EtherCamera. Release on
cancel/accept. A disconnected unique bus name releases the camera. A newly
spawned dbus-send process cannot take over an existing token. Reference
assignment is an API contract. The reusable CaptureClient keeps a private
D-Bus connection alive, returns provisional metadata for review and requires
explicit confirm_photo before caller association; cancel/retake removes only
its own unconfirmed captures when permission allows. No inventory integration
is claimed deployed
because no EtherInventory source is present in this workspace.

EtherBrowser/websites must use their own getUserMedia permission and selection
mechanism against compatible Linux UVC infrastructure. No browser portal or
virtual V4L2 bridge is provided, and direct browser capture is outside this
managed API's activity indicator. EtherRemote and EtherMCP receive no automatic
capture permissions. No scan result triggers an external action.

Privacy, power and resource lifecycle
------------------------------------

Same-UID D-Bus ownership and explicit per-session consent follow the existing
EtherAudio model. This is a cooperative per-user boundary, not application
identity isolation: same-user processes can declare consent or access media;
unrestricted/video-group device nodes can bypass the managed API. No device
ACLs, group memberships or other services are changed. EtherLock must be ready
and report unlocked. Lock signals, lock-service loss, caller loss, SIGTERM,
capture errors and PrepareForSleep release capture. Resume rediscovers devices
but never starts capture without a new session.

All media files use private mode, camera-owned UUID names, no arbitrary path
parameters and no symlink references. JPEG re-encoding discards location/EXIF;
sidecars contain UTC time, dimensions, camera ID and explicitly unknown
orientation/exposure when unavailable. Location capture is not implemented.
Diagnostics never include photographs or recordings. Worker scan text remains
memory-only and owner-bound. Camera usage history persists at most 100 allowlisted events without purposes,
media references, file paths or scan payloads. Preferences and history are private.

There is no inactive polling. EtherHardware camera topology events trigger
coalesced discovery. Only an active lease runs a 500ms safety timer.
Capture uses logind inhibition alongside EtherPower's existing ownership;
no suspend/reboot/power-policy changes. Video stops at low space (<128MiB),
reported thermal zone >=85C, battery <=5%, telemetry failure or duration limit.
These are conservative safety limits, not calibrated performance guarantees.
GStreamer errors/timeouts stop the device and deliver an existing desktop
notification through EtherNotifications' freedesktop compatibility endpoint.

Validation and explicit remaining scope
---------------------------------------

``python3 -m unittest discover -s ethercamera/tests -v`` verifies real handset
node rejection, owner/consent/lock policy, media lifecycle/traversal/metadata,
and generated OFFLINE decoder/document/A-V fixtures. The private D-Bus Qt
media suite also tests gallery, full image, video decode, policy persistence
and lock revocation without any physical sensor or microphone input.
Fixture success never counts as a physical sensor frame.

Hardware preview/photo/video/scanning, real orientation, controls, latency,
CPU/RAM/battery, disconnect and suspend acceptance remain untested without a
capture device. The capture UI and Qt FD preview now have private-bus software
acceptance. Remaining: touch focus, real vendor
camera bridge, actual live inventory UI (sources absent) and browser internal
camera adaptation. The media library implements local-date grouping, search,
albums, asynchronous thumbnails, full-screen photo/video viewing, explicit
clipboard file sharing, export/delete, document correction and multi-page PDF.
No photography interface or camera test source is presented as working hardware.

The EtherLock coordinator has been started with automatic locking disabled,
without modifying its policy or enabling enforcement. All camera/media access
still requires ready/unlocked state. Live-lock authentication, suspend/wake
and external-display security acceptance from task 06 remain unclaimed.
The exact new EtherShell package is isolated-test gated before live activation.
See ethercamera-followup-2026-10-20.rst and the delivery manifest for final state.
