EtherLocation delivery and acceptance
=====================================

Implemented and installed on the actual ARM64 handset:

* etherlocation 0.1.0: rootless native LOC/QRTR provider, central private D-Bus
  API, permission coordinator, precise/approximate transforms, optional bounded
  history, exports, local geofences and redacted diagnostics.
* Native Qt6 offline raster MBTiles viewer with software rendering, pan/zoom,
  manual selection, position/accuracy display, saved places, permitted history
  overlay, dataset attribution, region import/delete/storage, and explicitly
  licensed checksum-verified HTTPS downloads with size estimates and resume.
* EtherCamera 0.4.1: optional per-session photo GPS EXIF through the permission
  service. Default photo capture continues to strip location metadata.
* EtherHardware 0.1.1: diagnostic QRTR LOC capability discovery, explicitly
  distinguished from a verified real position fix.
* EtherShell Location Settings, Quick Settings toggle/status/activity and the
  existing AutoUpdate catalogue family. Existing X11 session, modem, network,
  audio, power and lock integrations are reused. No distributor or Fleet service
  is introduced, and no remote release was published.

The module guide is ``docs/etherlocation.rst``. Hardware evidence and exact
status are in ``docs/etherlocation-feasibility-2026-10-20.rst``. Package/source
hashes and acceptance limitations are recorded by
``scripts/finalize-etherlocation.py`` in ``evidence/etherlocation-delivery.json``.

Verified
---------

34 policy/storage/service/lifecycle tests on the Debian build host and handset (the
handset skips the source-tree-only overview dataset test; that real dataset is
instead imported and rendered by native handset acceptance). 39 camera tests,
including EXIF/privacy round trips and default stripping. 18 hardware registry
tests. The integrated shell passed the existing complete Settings UI suite in
narrow, portrait, landscape and external-display sizes, in light and dark modes.
The final diagnostics UI also passed scoped checks at all four sizes. A native
ARM64 regression test verifies that adding EtherLocation preserves existing
cached AutoUpdate releases while offline.
Real live-bus negative tests deny untrusted coordinate, permission-management,
history and tracking requests. The map renders real Natural Earth geography on
the handset with QT_QUICK_BACKEND=software and no tile networking.

The tested EtherShell release is activated from the existing /opt/ethershell2
layout; its previous launcher is backed up for rollback. New service defaults
are location off, history off, network positioning off and background off.
No history database is created, no live location is fabricated, and no idle GNSS
helper remains after acceptance. Package installation compared service/network
state and the unrelated session service PIDs before and after.
The user's later choices to enable the service and select a 1 km approximation
grid were preserved; the service is idle without application demand. History
and online positioning remain off.

Incomplete acceptance
---------------------

This is a partial Task 08 delivery, not a completed GNSS/navigation release.
The modem accepts standalone LOC start and stop. A 180-second native acquisition
test produced no verified fix, followed by a final bounded native retest.
No cause is inferred from the missing fix, and internal GNSS is not operational.
The native tests decoded GPS, GLONASS and Galileo telemetry, with up to 14
reported satellites. The final five-minute test with user-confirmed clear sky
view produced 300 in-progress position reports, no success report, and a timeout.
Partial coordinates were not published or saved. This is not a valid fix.
The earlier crashing Python satellite-binding path was removed.

Outdoor acquisition, cold/warm timing, physical external receivers, online
GeoClue, physical geofence transitions, suspend/resume and battery-only power
measurement remain open. The available USB-powered battery/current readings
are observations, not GNSS consumption measurements. Browser origin integration
requires an actual trusted browser bridge; Firefox's existing permissions are
preserved. Routing and turn-by-turn navigation require suitable offline engines
and datasets. Reboot/boot acceptance and remote distributor publication were
not performed. Android partitions, bootloader and firmware remain untouched.
