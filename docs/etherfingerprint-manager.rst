EtherFingerprint Manager â€” Task 13.1
===================================

The manager lives at Settings > Security & Privacy > Fingerprints, with a search
entry and Back navigation to Security. It reuses EtherFingerprint1.GetState and
does not add another daemon, template database or authentication engine.

The actual GM1920 backend is still diagnostics-only. It cannot enumerate,
enroll, verify, rename, delete or replace protected fingerprints. These flows
are blocked, not simulated. The count is Unknown, rather than zero, and an
unavailable list is distinguished from an empty list. No PIN prompt is shown
for an operation the backend cannot perform. Labels and template records are
not fabricated or stored in QML.

The native manager includes rounded cards, a theme-aware vector fingerprint
symbol, a decorative entrance that respects reduced motion, explicit service,
sensor, driver and secure-backend status, inactive unlock controls, recovery
guidance and expandable diagnostics. Controls have 48/52 pixel minimum touch
targets, keyboard focus styling and accessible names. It inherits EtherShell's
resolved light/dark/automatic theme, font scale, contrast colours and motion
preferences. External displays can show these read-only settings; no biometric
capture or sensor-position controls are exposed on any display.

The symbol is never a sensor-position guide. There is no fake scanning pulse,
enrollment percentage, match animation, haptic event or guessed sensing area.
No illumination or power lease is acquired. Suspend/resume cannot leave a
sensor operation active because no operation is started.

GetState now explicitly reports canList=false, enrolledCount=null,
enrollments=null and an immutable diagnostic security policy. These fields do
not authorize any operation. EtherLock remains responsible for screen locking
and credential authentication. Timeout, primary-auth and privileged-operation
policies cannot be changed by the manager. PAM and recovery remain unchanged.
The Qt client invalidates pending replies when the service owner changes, so a
late old reply cannot restore stale state after a crash/restart.

Hardware-backed acceptance remains blocked
-----------------------------------------

Real empty/enrolled lists, naming, credential rejection, enrollment, cancellation,
timeouts, deletion, replacement, verification and fingerprint unlocking require
a trusted backend that Task 13 could not establish. The enrollment wizard and
mutation interfaces must be implemented against that backend's reviewed
authorization, identifiers, progress, cancellation and assertion protocol;
adding a userspace success path would not satisfy this task.

The future replacement flow must first enroll and verify a new identity, then
obtain explicit confirmation to remove the old identity. It must retain the old
identity after failure and never infer a successful deletion from a UI update.
Labels must be keyed by backend identifiers and never identify a physical finger
without a user label. Management requires recent, session-bound existing
credential approval inside the backend. No such path is enabled in this release.

Packaging and publication
-------------------------

etherfingerprint 0.2.0 includes the manager integration, existing service, CLI,
tests and documentation. The shell package embeds the manager as a Settings
resource. Isolated UI fixtures are source-only and are never authentication
providers. The existing EtherUpdate/AutoUpdate Center distributor descriptor
continues to mark the release blocked-secure-backend, with fullTaskAcceptance
false. Publishing as working biometric authentication is blocked pending real
hardware security acceptance; no separate updater is introduced.

Validation and activation
-------------------------

33 Linux unit tests passed across EtherFingerprint, EtherHardware and EtherLock.
15 isolated Qt cases passed: 320, 360, 480, 1000 and 1920 pixel widths in light
and dark themes, large text, unavailable service/sensor, motion enabled and a 3.6× symbol render scale.
The tests assert disabled biometric controls, unknown enrollment state,
keyboard focus, diagnostic expansion, text geometry and service-loss behavior.

The packaged ARM64 shell passed isolated on-phone checks at narrow, portrait,
landscape and external-display sizes, including both themes, real diagnostic
metadata and expanded diagnostic layouts. No template/match fixtures are used
by these device tests. Results and images are in
``evidence/etherfingerprint-settings-device``.

The tested shell stage is activated on the phone with the previous launcher
preserved for rollback. ``evidence/etherfingerprint-shell-deployment.json``
records the exact stage, previous stage, launcher backup and package identity.
The live manager was visually checked; stopping the diagnostic service changed
the page to Service unavailable, and restarting it restored Secure backend
unavailable without restarting the shell. See
``evidence/etherfingerprint-manager-live.json`` and its associated screenshots.

etherfingerprint 0.2.0 was installed and verified as etherfp with device access
closed. PAM hashes, brightness and monitored service identities remained equal
before/after installation. No biometric sensor, illumination, suspend, reboot,
fingerprint unlock or credential-entry test was performed. The full Task 13.1
Definition of Done remains blocked on the trusted backend; only the truthful
unsupported manager and diagnostics are delivered and activated.
