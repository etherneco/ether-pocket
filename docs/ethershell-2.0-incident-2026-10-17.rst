EtherShell development incident — 17 October 2026
=================================================

The user reported that the phone stopped responding and performed a hard
restart. After that restart, read-only SSH checks succeeded. Xorg :0, xfwm4
and installed EtherShell 0.4.0 were running; the original host safe-mode
marker remained present. No Xephyr, development supervisor or native compiler
was running. The 2.0 package had not been installed on the device.

The previous boot's ssh.service journal records repeated ``Maxstartups``
refusals with connection count 100. This establishes exhaustion of the SSH
pre-authentication connection limit, rather than a bad authentication key.
The earlier suggestion of a per-source penalty was provisional and is now
superseded by this evidence. Why those connections accumulated is unresolved.

The Windows screenshot synchronizer had been retrying every two seconds.
It was stopped after verifying its process command line, before the reboot,
and remains stopped. Its source now backs off after errors at 15, 30, 60,
120, 240 and at most 300 seconds. Successful operation retains the existing
two-second interval. It must not be resumed in its old retry loop.

A filtered previous-boot kernel journal query found no matching OOM-kill,
hung-task or kernel-panic report; startup messages containing the words
watchdog/panic were not treated as runtime failures. This negative search
does not establish the cause of the freeze. Kernel logs near the reboot
include the long power-button press, consistent with the user's report.

The first post-reboot memory check showed 889 MiB used and 6512 MiB available,
with no swap used. The SSH process tree contained the listener and the
current diagnostic session. These are point-in-time observations, not a
long-duration stability result. upower.service was failed; it has not been
restarted or otherwise changed as part of these checks.

No SSH settings, network interfaces, boot configuration, kernel or firmware
were changed during recovery. New UI deployment and device compilation were
withheld after the freeze. Compilation stays on the Debian WSL build host.
The user's intended final integration is the current X11 session with free
application windows and EtherSurface decorations; nested software isolation
is not the intended user workflow.
