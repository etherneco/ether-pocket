Readable structured data in EtherPocket
=======================================

Delivered on 10 November 2026. User-facing JSON dumps were replaced in
notifications, hardware and Bluetooth diagnostics, power details, sensor
readings, map download progress and diagnostics, backup retention and recovery
instructions, and update dependencies. JSON remains the transport, storage and
explicit export format.

``qml/StructuredData.js`` supplies field labels, hierarchical presentation,
boolean and missing-value handling, and memory units. ``qml/DataView.qml``
renders diagnostic fields as wrapping cards using the Settings theme.
The custom power profile uses governor and frequency selectors; the existing
service still validates every submitted setting.

Notification presentation also handles persisted legacy power notices without
rewriting the database. Battery alerts show a readable title and remaining
percentage. Thermal alerts show only available measurements. Formatting runs
after lock-screen redaction.

Validation
----------

* Fifteen notification policy and presentation tests passed.
* Qt Quick formatter and phone-width layout tests passed with Qt 6.8.2.
* The custom profile rendered with synthetic CPU settings in a native QML
  harness without QML warnings. No hardware profile was applied during testing.
* ARM64 builds passed for EtherShell, EtherMAP and EtherBluetooth.
* Installed binaries and notification code were checked by SHA-256 on the
  phone. The notification service reconnected, both legacy battery notices
  displayed without JSON, and SSH, NetworkManager, ModemManager, EtherPower,
  EtherHardware and Bluetooth remained active.

``scripts/deploy-readable-data-ui.py`` installs a separate shell stage and
keeps a rollback launcher plus backups of the other replaced files.
``scripts/verify-readable-data-ui.py`` checks the running build and captures
the notification center. Local receipts and the screenshot are in
``evidence/readable-data-ui-*.json`` and ``evidence/readable-notifications.png``.
