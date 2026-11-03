EtherLock Task 06 delivery — 20 October 2026
==========================================

Disposition
-----------

Engineering implementation installed without service startup or mandatory
locking. Updated EtherShell is staged beside the active notifications release;
the live launcher is unchanged. Task 06 is NOT release complete.

Delivered
---------

* Debian ARM64 etherlock package, dedicated PAM stack, unprivileged conversation
  helper with authenticate + account checks, Qt6/QML mobile authentication child.
* Established XSecureLock enforcement, explicit post-grab/map acknowledgement,
  private/fault/unknown states and no unlock IPC. No custom input grabs.
* PAM failure delay and temporary lockout, password expiration checks, bounded
  redacted coordinator history, authpriv audit events, administrator evidence gate.
* Session D-Bus application privacy API and logind session lock events.
* Existing Settings integration, custom backend timeout, standard timeout presets,
  existing Media short-press blanking guard and unchanged EtherPower button owner.
* Root-only acceptance tool, staged recovery guide, encryption and X11 trust audit.
* Existing Etherneco distributor family/descriptor; no new distributor or remote
  release publication.

Validation
----------

The ARM64 policy suite passes all nine tests; private real-D-Bus acceptance passes
seven protocol assertions including restart into unknown/private state, persistent
policy and absence of unlock IPC. Evidence: etherlock-protocol-tests.json.

Real PAM tests use a disposable Linux account and random in-memory fixture
credential. Correct/wrong/empty credentials, expired account, five failures,
cross-process lockout and actual 120-second expiry pass. No production password
was supplied to automation. The account is removed after testing.

The isolated X11 suite uses a cookie-authenticated private Xvfb display, without
touching :0. XSecureLock acknowledges coverage/grabs. Wrong credentials and
SIGKILL of the auth child preserve the enforcing parent; later valid credentials
unlock successfully. Visual QA additionally verifies the auth drawable is painted.
An invisible-parent defect found during rendering was corrected by mapping the
supplied authentication parent, without changing enforcement or adding grabs. The follow-up modern visual revision adds rounded touch keys, a full-width blue unlock action, adaptive spacing and a light blue-white gradient (updated to the requested light theme). Its on-screen keypad is tested under the locker grab using local pointer routing; physical touch acceptance remains pending.

Final staged EtherShell passes the existing Settings suite at 360x900,
1000x600 and 1920x1080, in both themes. These are UI/layout tests; they are not
proof of real external monitor protection. See etherlock-shell-stage.json and
etherlock-shell/*/results.json. Existing permission/certificate/Bluetooth
settings remain reachable.

Fresh independent root-key SSH reconnections over USB and Wi-Fi pass. No SSH
policy or session termination occurred. No boot, suspend, partition, firmware or
Android mutation was performed. Live regression evidence records the unchanged
boot/shell and active existing services.

Outstanding requirements
------------------------

* Separate privileged PIN enrollment/verification and configurable minimum length;
  numeric input currently uses the Linux account password. No PIN change UI is
  presented as functional. A short account PIN is not recommended as a substitute
  for a strong system password.
* Progressive failure delays and configurable authentication/lockout timeout;
  current PAM policy uses fixed 2-second failure delay, five attempts and 120-second
  lockout. The prompt clears after 60 seconds.
* Attended unlock with the owner's credential, physical touchscreen/external
  keyboard/power-button/wake acceptance on the real session.
* EtherAIR hotplug and all-output protection acceptance; one physical monitor was
  connected during audit. Multiple independent X11 roots are rejected.
* Suspend/resume: existing EtherPower hardware gate is still blocked. EtherLock
  retains a sleep block while policy is enabled; supported secure suspend and
  resume are not shipped or claimed.
* Notification preview modes in the locker, battery/network status, swipe prompt,
  locked incoming-call controls and emergency dialer. Current opaque lock hides
  every notification. The cellular calling/audio path is not verified, so no
  emergency call was attempted or simulated.
* Fingerprint enrollment/authentication: Goodix platform nodes are present, but
  no proven libfprint/firmware/provider path exists. No biometrics are enabled.
* EtherTrust/remote-operation authorization adapters and remote-session activity
  display. Existing SSH sessions and authorization remain independent.
* Physical recovery, reboot persistence and release activation. Current evidence
  deliberately expires on boot/build changes; mandatory boot locking is absent.
* Review/remove development autologin and passwordless sudo only through a tested
  migration preserving independent recovery. Both prevent a hardened release.
* XSecureLock upstream maintenance decision: upstream is archived; Debian's
  packaged 1.9.0 is used as the engineering enforcement component.

No encryption migration, LUKS enrolment or repartitioning was undertaken. ext4
root is unencrypted; a lock credential cannot prevent offline extraction.

Next acceptance step
--------------------

Use docs/etherlock.rst to retain independent recovery, start the coordinator
manually with the existing session environment, and perform an attended unlock
test before any automatic-lock policy is enabled. Do not mark all acceptance
flags true merely to activate settings. Physical/suspend/call limitations above
remain release gates; the master-task Definition of Done is not yet satisfied.
