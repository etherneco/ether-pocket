Readable diagnostics UI — 2026-10-19
===================================

Removed JSON serialization from the EtherShell Mobile diagnostics and advanced
modem views, standalone EtherMobile Doctor, Wi-Fi connection details, Bluetooth
diagnosis/pairing details and storage mountpoint descriptions.

``ethermobile/diagnostics.js`` is shared by both applications. It presents
named fields, readable port/protocol and mode lists, radio power labels,
booleans and explicit missing values. Doctor stages include a short explanation
and collapsible details. Unknown or untested connectivity remains unverified;
it is not described as a broken connection. Report values use plain text.
Machine-readable settings and diagnostic collection remain unchanged.

ARM64 checks passed on the phone: real Doctor stages and expanded details at
360x900 and 1000x600, Settings at 1080x2340, both themes, and standalone Doctor
smoke/render. Reviewed the narrow diagnostic and advanced-detail screenshots.
Artifacts: ``evidence/readable-diagnostics``. No QML warning was reported by
the shell suites. Standalone offscreen smoke emitted unrelated existing
session-runtime/GVFS warnings; its UI loaded, collected stages and rendered.

Activation record: ``evidence/readable-diagnostics-deployment.json``.
Active stage: ``/opt/ethershell2/2.1.0-diagnostics-8b9062dd3bdb``.
The prior shell stage and ``ethershell2-start.before-readable-diagnostics``
launcher remain available. The standalone previous binary is saved on the
phone as ``/var/backups/ethermobile-before-readable-diagnostics``.

Only the shell UI was restarted. ethermobile-data remained active; ordinary
user ping to 1.1.1.1 passed 3/3 immediately after activation. This presentation
change does not integrate the separate IPA data adapter into Mobile Data.
