EtherLocation
=============

Task 08/11 implementation, Debian ARM64 / Qt6 / X11.
Location, network positioning, history and background tracking are disabled by
default. No coordinates or satellites are synthesized by production code.
EtherFleet is neither integrated nor required.

Architecture and privacy
------------------------

``etherlocation.service`` is a least-privilege user service, activated on demand
by session D-Bus. It supervises a rootless native libqmi/QRTR helper for Qualcomm
LOC, or an explicitly selected existing loopback gpsd receiver. It does not
install or enable competing daemons. GeoClue is an optional, explicitly online
authorised provider: existing GeoClue configuration determines its data sources
and may upload observations. No online provider is selected automatically.

The helper owns registration, start, reports, stop and client release on one
QMI connection. Start acceptance is not a position fix. Invalid, future, stale,
missing-accuracy and incomplete reports are rejected. Stop is asynchronous and
acknowledged. Partial fixes remain Searching and their coordinates are never
published. Idle means the service is enabled but has no positioning demand;
it does not imply an acquired or previously lost fix. The daemon has no polling
timer while idle. Direct GNSS testing
is limited to 180 seconds in Settings; subscriptions expire after at most one
hour, with at least 5 seconds between updates. Battery Saver and thermal limits
raise the next provider session interval to at least 60 seconds. Suspend drops
live positions and stops the provider without acquiring a wake inhibitor.

Only the installed root-owned EtherShell executable (including the existing
root-owned /opt/ethershell2 release staging layout) can approve permissions or
manage sensitive history. Identity derives from the unique bus sender PID and
executable, with a specific root-owned script association for EtherCamera.
Arbitrary app IDs or caller-supplied foreground claims are not accepted.
The active X11 window PID provides foreground evidence; EtherLock is checked
fail-closed. Grants are held in memory and lost when the service restarts.
Background use requires its own explicit grant and remains bounded; normal
foreground subscriptions are released when the app loses focus, disconnects,
locks, or is revoked. Explicit background sessions survive lock when authorised,
but are paused across suspend. Diagnostic tests stop on lock.

This is a managed API boundary, not OS isolation: unrestricted same-UID X11
processes can inspect other processes, modify their own files or directly open
QRTR/receivers. Strong untrusted-app isolation requires a sandbox and portal,
separate service identity and device/socket access restrictions. Do not describe
this session model as tamper-proof application confinement.

Approximation happens before API serialization, including last-known results.
Coordinates become the centres of a configurable 1–100 km grid and accuracy
includes a conservative cell diagonal. Altitude, heading and speed are removed.
Status signals contain no coordinates. Location updates are private method
replies, never broadcast signals. Cached fixes carry kind=last-known and age.
Manual selection is labelled user-supplied and is excluded from live selection,
history and geofence evaluation. Provider selection chooses a fresh source; it
does not average unrelated positions.

API v1
------

Session name/interface: ``com.etherneco.EtherLocation1``.
Object: ``/com/etherneco/EtherLocation1``. JSON documents have schemaVersion=1
in status; API version is exposed by GetCapabilities. Rejections use
``com.etherneco.EtherLocation1.Rejected``. Hold the D-Bus connection throughout
the permission request and positioning session.

* GetCapabilities(), GetState(), GetProviderStatus(): metadata only.
* SubscribeToStatus(): initial status; subsequently observe Changed(s).
* RequestPermission(s options): returns a request token. Review in Settings.
* GetPermissionState(s origin): policy for the caller's derived identity.
* GetLocation(s options), GetLastKnownLocation(s options): private filtered fix.
* StartUpdates(s options): bounded owner-bound subscription token.
* ReadUpdate(s token): private update, rate-limited to requested interval.
* StopUpdates(s token): releases caller demand and one-shot consent.

Options: precision=approximate|precise, interval=5..300 seconds,
timeout=5..3600 seconds, maxAge=1..3600 seconds, background=false by default,
origin empty by default. The service caps requests at two per owner and sixteen
total subscriptions. Ask-every-time grants expire with the requested timeout.
Clients requesting a new fix must StartUpdates and wait for a valid report;
GetLocation never fabricates a successful reply or silently starts hardware.

Shell-only management methods: Configure, GetManagement, GetPermissionRequests,
ResolvePermission, RevokePermission, ManageZone, SetManualLocation,
DeleteHistory, ExportHistory, TestGnss and ExportDiagnostics. Management returns
sensitive history only while unlocked. Diagnostic exports exclude coordinates
unless includeCoordinates is explicitly true. Error messages and app names are
omitted from the exported diagnostic allowlist.

``etherlocation state`` and ``etherlocation capabilities`` are read-only CLI
queries. ``etherlocation maps`` opens the native map viewer. ``client.py``
contains a connection-owning Python API adapter for applications.

Offline maps
------------

The maintained Qt6 Quick/QtSql stack renders raster MBTiles through a bounded
32 MiB image cache; no Qt Location plugin, GPU acceleration or web map engine
is required. Set QT_QUICK_BACKEND=software for software rendering. Import
licensed PNG/JPEG raster MBTiles in Maps → Regions; vector PBF is rejected.
Attribution is required and displayed as plain text. The default region limit
is 2 GiB and aggregate installed map quota is 8 GiB. Local storage is private
under ~/.local/share/etherlocation/maps. Region deletion does not remove the
original imported file.

Downloads require an explicit offline-rights confirmation, a direct HTTPS URL
and expected SHA256. No default tile endpoint exists; public OSM tile bulk
downloads and redirects are rejected. Content-Length, space and checksum are
checked. A paused partial download resumes with HTTP Range when supported;
otherwise it restarts. Resume identity includes URL and checksum. Resumed
Content-Range is checked; final hash protects against a changed remote object.
Progress reports bytes received and expected total. A network/server Range test
is still required for any production dataset source.

Pan by dragging, zoom with +/−, and double-tap to select a user-supplied point.
Permission and Locate are separate explicit controls. A current position has
source attribution and an accuracy circle; loss of live status labels the
remaining selected map position last-known. Offline place search requires the
optional dataset table etherlocation_places(name,latitude,longitude). The Regions
panel also saves user-selected places and loads a permission-filtered local
history point overlay while unlocked. Route calculation
and turn-by-turn navigation are not implemented.

``scripts/prepare-etherlocation-world-map.py`` builds a real coastline overview
from Natural Earth public-domain 1:110m land data, zooms 0–3. It queries no tile
service. Provenance and SHA256 are recorded in evidence. This is a world
overview, not a street-level map or navigation dataset.

History, geofences and applications
-----------------------------------

History is optional, off by default, capped at 10,000 entries and 1–90 days.
Collection requires fresh live fixes and an unlocked device. Enabling history
does not create positioning demand. SQLite storage is 0600 in a 0700 directory;
the database is not encrypted, so full-disk encryption is required for at-rest
confidentiality against privileged or offline access. GPX/GeoJSON exports are
explicit user actions. Selection and all-history deletion use secure_delete
and vacuum; flash-level erasure is not claimed.

Local geofences require fresh fixes with accuracy no worse than 100 m or half
the zone radius. Accuracy-expanded bounds, 10%/20 m hysteresis and two distinct
fixes spanning at least ten seconds suppress false transitions. Initial state
is silent. Gaps reset candidate/dwell timing. Zones do not independently enable
background GNSS. Notifications go through the existing freedesktop notification
owner/EtherNotifications and its DND policy; precise coordinates are excluded.

EtherCamera adds RequestPhotoLocation and EnablePhotoLocation, checked against
the caller-owned camera session and installed native camera executable. It cannot
proxy its grant to arbitrary capture clients; other applications need their own
location permission. Consent is off for every new camera session;
a separately granted EtherLocation permission and a fresh permitted fix are
required. Photos retain no source GPS metadata by default. Optional GPS EXIF
encodes hemisphere, rational degrees, UTC and horizontal positioning error;
approximate permissions remain approximate, without altitude reconstruction.
Missing permission/fix saves the photo without location. Location demand stops
with camera release, lock or exit. Video location metadata is not collected.

The repository contains Firefox ESR, not an EtherBrowser source module.
Firefox's website-origin permission controls are preserved. No all-origin
bridge or remote geolocation endpoint is installed. An origin-aware API schema
exists but origin requests are rejected until a trusted sandboxed browser
bridge is installed. GeoClue-provider support is not a reverse GeoClue server
and does not claim Firefox can consume EtherLocation. That bridge is deferred.

Build and verification
-----------------------

Use the existing EtherPocketBuild Debian environment:
``sh scripts/build-etherlocation.sh``. libqmi-glib-dev:arm64 and
libqrtr-glib-dev:arm64 are build dependencies. Packaging uses existing CPack
Debian ARM64 conventions and existing EtherShell distribution metadata.
No new application distributor is created. Settings → Location and Quick
Settings are integrated into the existing EtherShell source.

Tests live in etherlocation/tests and ethercamera/tests/test_location_metadata.py.
Controlled fixture data remains in tests only; production has no injection API.
Real-device first-fix, cold/warm timing, physical external receiver, online
GeoClue, suspend/resume, outdoor geofence transitions and battery-only power
measurements must be recorded independently. A successful build is not those
acceptance tests. See the feasibility report and delivery manifest.

Primary references
-------------------

* https://mobile-broadband.pages.freedesktop.org/docs/libqmi/api-reference/
* https://www.freedesktop.org/software/geoclue/docs/gdbus-org.freedesktop.GeoClue2.Client.html
* https://doc.qt.io/qt-6/qtquick-visualcanvas-scenegraph-renderer.html
* https://operations.osmfoundation.org/policies/tiles/
* https://www.naturalearthdata.com/about/terms-of-use/
