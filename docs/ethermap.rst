EtherMAP
========

Task 12 implementation for Debian 13 ARM64 / Qt6 Quick / X11.
Release acceptance is pending; real GNSS acquisition and remote publication are
not established by unit tests or package builds.

Audit and renderer decision
---------------------------

EtherLocation is the sole device-positioning owner. It already supplies the
Qualcomm LOC/QRTR helper, local gpsd external-receiver adapter, opt-in GeoClue,
sender-derived permissions, accuracy transforms, power and suspend policy.
Its 2026-10-21 acquisition report recorded no usable GNSS fix. No satellite
data, coordinates or operational-GNSS claim is synthesized by EtherMAP.
EtherMobile supplies modem state; no unrestricted Wi-Fi/cell location database
or licensed production network-positioning endpoint is configured here.
GeoClue cannot reliably distinguish its Wi-Fi/cellular sources, so its source
is labelled GeoClue rather than inventing source provenance.
With separate online authorisation, EtherLocation now runs the existing GeoClue
adapter alongside its selected GNSS backend. Fresh network fixes replace stale
or poor (>100 m) GNSS fixes; good fresh GNSS retains priority. There is no new
Wi-Fi scanner or upload endpoint. Network authorisation is managed in the existing
Location page while the device service is disabled.

MapLibre Native Qt and its Qt Location plugin were evaluated against the
existing software-rendered X11 deployment. This release uses the existing
maintained Qt6 Quick/QtSql raster renderer, shared with EtherLocation, rather
than adding an unverified GL renderer to the phone. It supports actual OSM
raster tiles, pan, zoom, rotation, markers, accuracy areas, segmented trails,
route lines and imported licensed raster MBTiles. This is not a MapLibre vector
implementation. Vector MBTiles and offline turn-by-turn navigation are not
advertised. MapLibre vector rendering remains a future hardware acceptance gate.

Architecture and defaults
-------------------------

``ethermap`` is the native Qt window. Its private child ``backend.py`` owns a
persistent EtherLocation D-Bus connection, local SQLite tracks and provider
jobs. It has no listener or GNSS hardware access, installs no service and exits
with the window. Root-owned installed executable/script associations identify
both processes as ethermap. Existing EtherShell permission review remains the
only grant coordinator. No duplicate device-location settings are created.

History, background use, precise requests, external IP lookup, online search,
routing and online tiles default off. Local recording requires both the history
switch and an explicit Record action. Background use requires its own permission
in Settings → Location; suspend creates a gap and acquires no wake inhibitor.
Tracks survive process failure as interrupted local recordings; reopening never
silently resumes recording. Same-UID X11 access is not a sandbox boundary.

Select precise permission and the Maps precise request before recording. Only
fresh (30 seconds), precise, live EtherLocation reports with accuracy at most
100 m qualify. GeoClue is honestly labelled and may qualify only when the
existing permission boundary returns precise live data. IP, manual, cached and
imported points never qualify. Duplicate/out-of-order reports are ignored.
Pauses, signal loss, suspend, implausible jumps and long intervals split GPX
segments and distance calculations. Movement is never inferred from IP changes.

Battery Saver/thermal policy comes from EtherLocation/EtherPower. Stationary
reported speed below 0.5 m/s requests 60-second updates, otherwise ten seconds.
Foreground loss releases ordinary subscriptions; background subscriptions remain
bounded to one hour and revalidate the same permission. No kernel wake promise.
Notifications use the existing freedesktop/EtherNotifications owner and policy;
active authorised background recording requests a persistent resident notice.
No automatic upload, remote monitoring, Google service or EtherFleet is added.

Privacy and IP fallback
-----------------------

The new EtherLocation ``GetIpLocation(s)`` method requires ordinary caller
permission, current foreground/background authorisation, explicit consent and
a configured HTTPS endpoint. The service rechecks permission, focus, lock and
suspend after the asynchronous response. Requests have a ten-second timeout,
64 KiB response bound, no redirects, an hour cache and a persisted 15-minute
request/failure limit. No endpoint or key is shipped. The JSON contract is::

  {"latitude":51.5,"longitude":-0.1,"city":"London","country":"GB"}

Optional ``accuracy`` is in metres and must be supplied reliably by the provider;
unknown accuracy stays null. Provider host and timestamp accompany the result.
There is no blue IP position dot. A region label is always shown; a supplied
uncertainty radius is drawn. VPNs, proxies and carrier exits can be misleading.
Coordinates never enter EtherLocation's GNSS live fix, history or geofences.
After a consented Locate/Follow/Record request, IP fallback is attempted when
device positioning has no acceptable fix; there is also an explicit IP request.
On network failure, an existing IP cache up to seven days old can be returned
with its original timestamp and an explicit stale flag.

``GetIpLocation`` takes JSON ``endpoint``, ``consent:true`` and standard
``options``. It is separate from GetLocation so existing clients cannot mistake
IP for GNSS. Cached IP timestamps remain unchanged and age is shown.
Settings, tracks and searches live under ~/.local/share/ethermap with private
directory/file permissions. The database is unencrypted. Local deletion does
not promise flash-level erasure. GPX export is explicit and stays local.

Map services and offline use
----------------------------

Online tiles are visible-view requests only with a named User-Agent and bounded
128 MiB Qt HTTP disk cache respecting response caching headers. The default
optional layer is OSM Standard with visible OSM attribution. No prefetch or bulk
tile downloader exists. Custom layers require an HTTPS XYZ template and provider
attribution; satellite imagery is not included with OpenStreetMap.

Offline regions reuse EtherLocation's licensed PNG/JPEG MBTiles manager: local
import, required attribution, 2 GiB per region / 8 GiB aggregate, direct HTTPS
dataset transfer, mandatory SHA256, progress, pause/Range resume, verification,
storage size and deletion. Public OSM tile bulk URLs and redirects are rejected.
Installed offline maps render without network. Natural Earth's existing overview
is not an OSM street map and must not be presented as one. Region selection is
by dataset, not a public tile area downloader.
The package includes a small real OSM Westminster street dataset, zooms 13–16,
for immediate offline map viewing when no region is installed. Its dataset centre
is not a device position. ``scripts/prepare-ethermap-osm-region.py`` renders a
bounded OSM XML extract without any public tile requests; the source XML and
provenance are included under /usr/share/doc/ethermap/osm. Build regeneration
requires python3-pil; runtime rendering does not. Other areas require suitable
licensed regional datasets.

Search accepts local coordinates, saved places and optional offline dataset
place indices without network. Explicit online submission uses a configured
Nominatim-compatible URL, eight-result bound, one-second minimum request spacing,
bounded 24-hour local cache and no autocomplete. A configured provider must
permit caching and the intended deployment. The public Nominatim endpoint is
not configured by default. Neither tiles nor geocoding have a service SLA here.

OSRM-compatible routing is optional, explicitly consented, and requires separate
profile-prepared endpoint URLs for walking/cycling/driving. Real returned GeoJSON
geometry, distance, duration and maneuver text are shown. No fake straight-line
route, traffic ETA or offline navigation is supplied. Navigation mode follows
the device with a calculated route visible; it does not provide turn-by-turn
guidance, off-route recalculation or map matching. An unavailable provider is
reported as unavailable.

Build, distribution and acceptance
---------------------------------

``sh scripts/build-ethermap.sh`` builds the ARM64 Debian package using the
existing EtherPocketBuild toolchain. Rebuild EtherLocation too for the new IP
method and app identity (required version 0.1.1). The EtherShell launcher discovers ethermap.desktop;
Settings → Location → Maps links to the application. Rebuild the shell to embed
the updated Location page. ``distributor.json`` records acceptance-pending status
and uses the existing distributor, not a second updater.

Tests: ``python3 -m unittest discover -s ethermap/tests -v`` and the existing
EtherLocation suite. ``scripts/test-ethermap-native.py`` runs the actual native UI,
worker and EtherLocation service on an isolated bus with only an unlocked-lock
fixture. Run under ``unshare --net dbus-run-session`` with private HOME/XDG paths
and a native build configured with ``-DETHERMAP_UI_TESTS=ON``. The production ARM64
package does not include that interaction driver. Unit fixtures are not physical movement acceptance.
Outstanding hardware checks include successful GNSS acquisition, external
receiver movement, consented real IP/VPN responses, configured production
geocoder/router tests, physical lock/suspend/screen-off and battery measurements,
offline street-map rendering and boot/network/SSH regression. Distribution
requires the existing commissioned publisher/signing and AutoUpdate Center
publication path. A local package is not a remotely published release.

References checked 2026-10-21
-----------------------------

* https://maplibre.org/maplibre-native-qt/docs/group__QMapLibreLocation.html
* https://operations.osmfoundation.org/policies/tiles/
* https://operations.osmfoundation.org/policies/nominatim/
* https://project-osrm.org/docs/v5.24.0/api/
