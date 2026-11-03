Wi-Fi radio control repair — 2026-10-19
=====================================

NetworkManager rejected EtherShell's radio-off requests with
``Not authorized to perform this operation``. The running shell (UID 1000)
was in the deployment SSH scope, session-c1300, rather than the active local
X11 session c1. NetworkManager's default active-session permission therefore
did not apply, despite the visible desktop being active.

Installed ``config/49-etherpocket-wifi.rules`` as
``/etc/polkit-1/rules.d/49-etherpocket-wifi.rules``. It authorizes only
``org.freedesktop.NetworkManager.enable-disable-wifi`` for the device owner
``mobian``, including processes outside the local logind session. Other users
and other actions retain their existing policy. The standard Wi-Fi installer
now includes this rule. Polkit reloads it automatically; no process restart,
driver reload, firmware change or reboot was needed.

``scripts/fix-phone-wifi-permissions.py`` installs the rule and exercises the
running production EtherShell's existing Core control callback through its
control socket. The real device passed radio off, WLAN disconnection and
rfkill soft block, then radio on and automatic reconnection. The test restored
the initial enabled radio state. NetworkManager, SSH and Bluetooth remained
active. The separate cellular-radio permission remained denied.

Evidence: ``evidence/wifi-radio-fix-2026-10-19.json``. This verifies the running
shell backend and hardware state; it does not claim a physical finger test.
