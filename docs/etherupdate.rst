EtherUpdate 0.1.0 — implementation and commissioning
==================================================

EtherBackup integration added on 21 October 2026
----------------------------------------------

Installation now requires a successful EtherBackup pre-update recovery point.
The verified snapshot reference is durably persisted before application activation.
Commission /etc/etherbackup/policy.json with a destination and component source
contracts; missing configuration or a failed sample restore blocks installation.
Post-update health success retains the point for the configured safety period;
failure pins it. No automatic older-database restore is performed. See
docs/etherbackup.rst for the independent CLI and current recovery limitations.

Scope and status
----------------

The existing Etherneco AutoUpdate Center remains the sole release authority.
This package provides a privileged system-bus coordinator, private bounded cache,
Ed25519 verification, SQLite transaction journal, application bundle installation
and recovery, guarded Debian installation, local read-only stdio MCP and a native
EtherShell Settings → System → Software Updates page. It does not provide a
second server, artifact repository or account system.

This is a commissioning release. Default policy has no commissioned components
and no trusted signing keys. Discovery can list public projects without a token;
installation is impossible until an administrator provisions independent trust
roots, a real project mapping, device family and meaningful local health checks.
No official release, automatic OS rollback or self-update support is claimed.

Audit on 21 October 2026
------------------------

Source inspected: EtherShell distributor, Settings, Python/D-Bus component
services, EtherPower inhibition policy, EtherNotifications standard Notify API,
existing packaging/deployment conventions, and C:\\projects.local\\autoupdate.
The latter contains Laravel API controllers, authentication and HTTP MCP tools.
There was no screenshot attached to task 09; dashboard appearance was not audited.

Live public API and MCP discovery are recorded in evidence/etherupdate-*.json.
All project pages were enumerated. Public EtherPocket component projects were
not found; private projects cannot be audited without rotated credentials.
No projects were created, so existing entries cannot have been duplicated.

Actual contracts:

* GET /api/projects?page=N — Laravel pagination: data, last_page.
* GET /api/releases — published release pagination, not per-device eligibility.
* GET /api/releases/check?project=slug&channel=Stable — latest, artifact,
  sha256, sha512, download_url, signature, metadata, notes, published_at.
  The client does not trust PHP update_available for Debian version ordering.
* GET /api/manage/projects and /api/manage/releases require credentials.
* POST /api/mcp — HTTP JSON-RPC 2.0, initialize/tools/list/resources/list.
  Discovery is public; management tools authenticate against existing accounts.
  The client uses Authorization Bearer headers only; there is no URL-token fallback.
* Existing channels are Stable, Beta, Nightly, Experimental. Only latest-per-channel
  is queried; no assumption that all earlier compatible releases are enumerated.

The original gpg_url content is the digest text; rsa is an APP_KEY HMAC, not RSA.
Neither is accepted for publisher authenticity. The local server extension adds
optional etherupdate[payload], etherupdate[signature], etherupdate[key_id] fields
to the existing multipart POST /api/manage/projects/{project}/releases. It checks
Ed25519 against project-scoped public keys configured in config/etherupdate.php,
binds digest, size, project, version and channel to the uploaded artifact, and
stores the envelope in platform_metadata. Existing release/check and MCP read
tools then expose it without a new endpoint or database migration. This extension
has to be deployed before production can supply those envelopes. The legacy
publishing UI and MCP upload helper have not been extended to submit this field;
use the authenticated multipart REST upload for commissioning signed releases.

The audited server has no device registration, install reporting, device-health,
rollout pause/percentage or compatibility eligibility endpoints. Those features
are marked unsupported, and no speculative requests or telemetry are sent.
No authentication system or roles were added. Publication still requires a
separate, explicit approval using the existing release workflow.

Device audit: SSH reachable, ARM64, Debian 13.7, kernel 4.14.117-perf, root ext4
on sda21 with about 183 GB free. SSH, EtherPower and EtherHardware were active.
Partition names were read only. Existing recovery backups are not an atomic OS
snapshot. No Btrfs, root A/B recovery, tested boot recovery or device installation
of a new official release is asserted. No Android partition is written.

Trust and configuration
-----------------------

Install etherupdate_0.1.0_arm64.deb through a reviewed initial provisioning path.
Set /etc/etherupdate/device-family to oneplus7pro only after confirming the target.
Provision /etc/etherupdate/trusted-keys.json independently from the update API::

  {"publisher-2026": {"public_key": "BASE64_ED25519_PUBLIC_KEY",
                      "projects": ["existing-project-slug"], "revoked": false}}

The keys, local policy and parent directories must be root-owned and not writable
by other users. Empty trust is intentional. Rotate keys by provisioning the new
public key through an independent authenticated administrator channel, overlap
explicitly, then revoke the old key locally. API data cannot add trust keys.

Provision a rotated token in /etc/etherupdate/autoupdate-token, root:root 0600.
The agent reads the protected file directly; credentials never enter
arguments, filenames, URLs, source, history or diagnostics. Do not reuse the old
build/autoupdate-credential.json token. Revoking it at the server requires the
account owner or a separately authenticated administrator; it was not attempted.

Alternatively use Software Updates → AutoUpdate access token → Save and Test
Connection. The input is masked, disables predictive input, clears after submit,
and never reads a saved token back. A dedicated Polkit administrator authorization
is required. The secret is passed over a Unix file descriptor, not a D-Bus string
argument. The agent verifies access to the real protected project API before
saving; failed validation preserves the previous credential. The managed copy
is written atomically to /var/lib/etherupdate/credentials/autoupdate-token with
0600 permissions under a root-owned 0700 directory. It overrides the provisioned file
on restart. Remove Saved Token writes an empty override and clears in-memory
access; revoking the server API key remains a separate operation. Only configured/
unconfigured status is exposed in diagnostics. No token is stored in EtherShell
preferences or passed through a shell command.

Example local policy for a noncritical, versioned application::

  {"schema":1,"sessionUid":1000,"components":{
    "existing-project-slug": {
      "name":"Test application","package":"test-app",
      "type":"versioned-bundle","critical":false,
      "service":"locally-reviewed-app.service",
      "health":[["/usr/local/libexec/test-app-functional-health"]]
    }
  }}

Service and health commands come only from protected local policy, never release
notes, manifest commands or MCP text. Configure a bounded functional probe (UI/
D-Bus response or equivalent), not just service active. Bundle releases must be
tar archives containing regular files and directories: no links, special devices,
duplicate names, traversal or privileged modes. Extraction is capped at 10,000
entries and 1 GiB uncompressed. Applications must already launch through
/opt/etherupdate-components/PACKAGE/current. This is an opt-in deployment strategy,
not a claim that current EtherShell binaries already use versioned directories.

Signed UTF-8 manifest payload, schema 1::

  {"schema":1,"project":"existing-project-slug","package":"test-app",
   "version":"1.2.0","channel":"Stable","type":"versioned-bundle",
   "sha256":"64 lowercase hex digits","size":12345,
   "compatibility":{"architecture":"arm64","distribution":"debian",
     "distribution_major":13,"device_family":"oneplus7pro",
     "kernel_abi":"4.14.117-perf"},"dependencies":{},"reboot":false}

The Ed25519 signature covers the exact payload bytes. The envelope carries the
base64 payload and detached signature plus key_id. Public-key identity and project
scope are local. Compatibility requires every listed platform field to match.
All supported version strings use Debian's dpkg ordering, including epochs and
tilde prereleases; unsupported version schemes are rejected rather than guessed.
Downgrades/reinstalls are refused. HTTPS downloads permit no redirects. Retry is
bounded, partial files are removed, cancellation is download-only. Pause/resume is
not advertised because no strong-validator Range contract has been commissioned.

Transactions and recovery
-------------------------

Discovery, availability, download, verification, preparation, installation, health
checking and completion are persisted with FULL SQLite durability. Preparation
requires a verified artifact, fresh safety state, dependencies and sufficient disk
space. InstallApproved consumes a short-lived, caller-UID-bound approval and also
requires a separate noncached Polkit admin authorization. Signed metadata and
artifact bytes are checked again immediately before installation. Running calls,
recording, camera activity, unknown safety or battery below 40% defer installation.
logind blocks sleep/shutdown during installation and recovery; EtherPower already
honours that inhibitor. No force suspend is requested.

Versioned application activation replaces the current symlink, preserving the
previous directory. Its recovery point is journaled before activation. Failed
health checks restore the old link, restart the locally configured service and
run local functional health probes again. No previous version means recovery is
manual. Interrupted installation becomes Recovery Required after agent restart;
it never becomes successful automatically. Administrator recovery uses the
recorded previous directory through independent SSH; automatic reboot recovery
is deliberately not claimed.

Debian installation validates package/version/ARM64 control fields and simulates
apt with --no-download/--no-remove. Changes to any other package are rejected.
Dependencies must already be installed; arbitrary online dependency upgrades are
not accepted. Local policy must set manualRecoveryVerified after an independently
tested restoration plan. This strategy has no automatic package or OS rollback.
Kernel/boot/firmware types, critical components and EtherUpdate self-update are
blocked pending their own compatibility, recovery and restart implementation.
Configuration migrations and generic application formats are not yet implemented.

Offline imports use Agent.import_offline and the same envelope, compatibility and
hash checks. The privileged service currently exposes no arbitrary filesystem
path import method; the user-facing file picker remains unimplemented. Development
artifacts have no unsigned bypass. Scheduled install/selected batch operations
are not exposed. Daily discovery is event-loop scheduled with hourly wake checks.
Metadata is refreshed on explicit checks; there is no assumed cache TTL.

Interfaces and tests
--------------------

The system bus owns com.etherneco.EtherUpdate1 at /com/etherneco/EtherUpdate1.
GetState is read-only. CheckUpdates, SetChannel, Download and CancelDownload use
manage authorization. PrepareInstall/InstallApproved require install authorization.
All methods run on one worker except cached state and cancellation. UI progress
signals run only during an active download. Native Software Updates is part of
EtherShell Settings, not a new application, and never runs as root.

EtherShell forwards update Event signals to the existing session Notify API;
EtherNotifications owns DND and normal notification delivery. This bridge requires
EtherShell to be running. Errors and recovery appear in Settings history.

etherupdate mcp provides six read-only stdio tools using the caller's OS-authenticated
system D-Bus connection. It has no TCP listener, credential or install capability.
Privileged coordination uses the separate Polkit-controlled D-Bus methods. No
natural-language content can supply root commands or bypass installation approval.
Central MCP discovery includes actual schemas/resources but never invokes a
publication or destructive tool. Local release-publication scope is absent.

Run python3 -m unittest discover -s etherupdate/tests -v on Linux; Windows runs
portable verification tests and skips Debian/Unix installation cases. Tests use
temporary keys and isolated application directories. They exercise actual bundle
activation, deliberately failed health, previous-version restoration, signatures,
unsafe archives, compatibility, interruption and approval boundaries. Passing
isolated tests does not establish physical boot/network/audio/lock acceptance of
any new OS release. scripts/build-etherupdate.sh creates the ARM64 Debian package.

Remaining delivery gates
------------------------

Rotated management credentials; verified independent publisher public key;
server extension deployment; reuse/register private component projects; signed
official test release; per-component functional probes; device package install;
production native UI activation and physical checks; tested Debian restoration;
self-update recovery; offline file picker; selected/scheduled installations;
explicit final publication approval. No release was published by this task.

Validation evidence
-------------------

The 34 updater tests pass on the Debian build host and native ARM64 phone,
including service authorization and credential storage tests. Isolated application
installation and deliberately failing-release recovery passed on both hosts.
Phone SSH, NetworkManager, EtherPower, EtherHardware and ModemManager retained
the same active state and process IDs. The AutoUpdate Center regression suite
passes: 62 tests, 360 assertions, including six signed-envelope/upload tests.
Its test encryption key was generated only for the test process and not saved.
Both the EtherUpdate ARM64 package and integrated EtherShell ARM64 package build.
The Software Updates page passes isolated native ARM64 render, route and geometry
checks in light/dark themes at 360x900, 1080x2340, 1000x600 and 1920x1080, with no
QML warnings. These screenshots use a clearly labelled visual fixture; they do
not depict a published EtherShell release. See evidence/etherupdate-ui.
The live protected project endpoint rejects an invalid credential as an
authentication failure, recorded in evidence/etherupdate-auth-failure.json.

Token Settings follow-up
------------------------

The agent is now installed and running on the phone, with the tested EtherShell
token-entry page activated. The old shell and a launcher backup remain available
for recovery. No credential was prepopulated. A synthetic invalid token sent
through the real Unix-FD D-Bus method was rejected without creating a saved token.
The device's kernel 4.14 rejects systemd credential setup (243/CREDENTIALS), so the
unit uses the protected root-owned storage described above instead. Phone service
processes remained unchanged. See evidence/etherupdate-token-deployment.json.
Official release installation, trust commissioning and publication remain pending.
