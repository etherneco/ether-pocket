EtherLocation acquisition follow-up — 2026-10-21
================================================

Task 08 remains incomplete: first real GNSS fix has not been obtained.
The installed module, maps, permissions and camera integration remain available.
No release-complete or operational-GNSS claim is made.

A separate ARM64 diagnostic probe was built from the installed provider source
with additional redacted quality fields. It ran as mobian for 300 seconds,
without replacing the installed helper or changing location settings. Its
temporary executable was removed after the test. Neither coordinates nor
injected positions were recorded. Evidence:
``evidence/etherlocation-quality-test.json``; reproducible procedure:
``scripts/test-etherlocation-quality.py``.

Results
-------

* 300 in-progress reports, one timeout, zero successful fixes.
* Every position report had technology mask 2: CELLULAR, without SATELLITE.
  The enum is defined by libqmi's ``qmi-enums-loc.h`` and its upstream source:
  https://github.com/linux-mobile-broadband/libqmi/blob/main/src/libqmi-glib/qmi-enums-loc.h
* Both uncertainty ellipse axes were 7,070,360.5 metres in every report.
  These are not usable device positions and were correctly rejected.
* Report timestamps were current: approximately 0.0002–0.0231 seconds old.
  The phone reported NTPSynchronized=yes and standalone LOC operation mode.
  These observations do not support a stale-clock explanation.
* 64 satellite reports, at most one reported GPS satellite in this attempt;
  maximum reported signal was 29 dB-Hz. Earlier attempts reported up to 14
  satellites, but none produced a successful position. Visibility varies.
* No satellites-used field was provided. Reported HDOP was zero, which does
  not establish valid geometry or accuracy for a failed position report.
* Stop was acknowledged and the client/device were released. No kernel log
  matches for GNSS, GPS, modem crash or fatal error were found in this audit.

The verified failure is acquisition in the modem, not coordinate serialization
or timestamp rejection by EtherLocation. The underlying reason for insufficient
satellite acquisition remains unresolved; no antenna, firmware or assistance
root cause is established. Changing firmware, radio configuration or injecting
guessed coordinates would not constitute verified completion.

Acceptance still required
------------------------

A successful satellite-derived fix with valid coordinates, accuracy and time,
then cold/warm acquisition timing and actual history/camera/map use with that
fix. Browser-origin integration remains deferred because this repository has
Firefox ESR and no trusted EtherBrowser bridge. External receiver, physical
suspend/resume, battery-only power and physical geofence acceptance remain open.
Routing and turn-by-turn navigation remain deferred as documented separately.

The Debian test host passed all 34 location tests again. Installed package/source
hashes and real-device negative-permission/map acceptance are checked by the
delivery verifier. User-selected location enabled and 1 km approximation remain
unchanged; history and online positioning remain disabled.
