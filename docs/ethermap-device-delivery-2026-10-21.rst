EtherMAP device deployment — 2026-10-21
======================================

Installed and launched on the OnePlus 7 Pro after the user's reboot restored
SSH. This completes deployment of the implemented application, not all Task 12
hardware, provider and release acceptance gates.

Installed components
---------------------

* ethermap 0.1.0 ARM64 and EtherLocation 0.1.1 ARM64.
* EtherShell stage /opt/ethershell2/2.1.0-map-6345de98b24f activated using the
  existing current-session mechanism. Launcher and Location → Maps entry work.
* Licensed OSM Westminster raster region imported alongside existing datasets.
  It is a small offline dataset, not nationwide coverage or a device position.
* Default dataset selection prefers OSM and persists a chosen region or online
  layer. Ordinary status refresh no longer recentres a manually panned map.

Privacy and service continuity
------------------------------

Existing Location settings were preserved: enabled, balanced, 1 km approximation,
Qualcomm LOC backend, history off and network positioning off. No grant was
silently created. EtherMAP recording, background tracking, external IP fallback,
online tiles, external geocoding and routing remain off by default. Launching
the viewer created neither a location-history database nor a track database,
and left GNSS idle. The app and its private worker are both identified as
ethermap by the installed EtherLocation identity policy.

SSH, NetworkManager, ModemManager, EtherHardware, EtherPower, Bluetooth and the
existing session audio/lock/notification services retained their process IDs
during package installation. The shell was then intentionally replaced by the
accepted staged release. Wi-Fi was disconnected before deployment and remained
disconnected; no successful internet-connectivity regression is claimed.
No Android partition, kernel, modem firmware or radio configuration was changed.

Verification
-------------

* On-device suites: 37 EtherLocation tests and 23 EtherMAP tests passed.
* Seven real D-Bus permission/consent denials passed without starting hardware
  or contacting an IP endpoint.
* Installed production ARM64 application rendered maps and settings at narrow,
  portrait and landscape sizes with no QML warnings or worker errors.
* EtherShell Location page passed light/dark rendering, routing and geometry
  acceptance at four sizes before activation.
* Live launcher opened EtherMAP on the physical desktop. The actual foreground
  application screenshot is evidence/ethermap-live/live-map.png.
* The native isolated offline interaction driver also checks that panning survives
  the next status refresh, alongside pan, zoom, rotation, manual separation,
  offline saved-place search and history-off behaviour. No positions were injected
  into the production device service.

Recovery
---------

The original installed EtherLocation package was reconstructed before updating:
/var/backups/ethermap-20261021-183329/etherlocation-before.deb.
The old shell stage remains intact at
/opt/ethershell2/2.1.0-sensors-07e9238c2655. Its launcher backup is
/home/mobian/.local/bin/ethershell2-start.before-2.1.0-map-6345de98b24f.
Activation used automatic rollback on failure; no rollback was needed.

Still pending
--------------

No actual GNSS fix, physical movement recording, external receiver, battery,
screen-off/suspend or reboot-after-installation acceptance is claimed. IP,
geocoding and OSRM endpoints require permitted service configuration and user
consent. MapLibre vector rendering, graphical area dataset selection and offline
routing/navigation remain unimplemented. Signed AutoUpdate Center publication
has not occurred; repository publisher keys and component policy are uncommissioned.

The exact current package/source hashes and evidence are recorded in
evidence/ethermap-delivery.json and evidence/ethermap-package-verification.json.
