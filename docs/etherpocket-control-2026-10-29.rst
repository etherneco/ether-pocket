EtherPocket Control for Windows, 2026-10-29
=========================================

Delivered application
---------------------

``build/windows/EtherPocketControl/EtherPocketControl.exe`` is a Windows x64
application with desktop and Start menu shortcuts. It includes its Python/Tk/Pillow runtime;
the user does not need to install Python. Keep the entire application directory.
Sources and build instructions are in ``etherpocket-control``.

Live X11 capture, fit-to-window scaling, mouse buttons/motion/dragging, wheel,
keyboard shortcuts and Unicode text, view-only mode, PNG screenshots, adjustable
1–15 FPS, explicit disconnect and reconnect are implemented. Default capture is
8 FPS and 720 pixels wide. Display dimensions and pointer coordinates use the
real X11 desktop size. The UI is Polish. Video recording, audio, clipboard sync,
Android capture and display hotplug/resolution changes during a session are not
implemented. Reconnect after changing the phone display geometry.

Connection and lifecycle
------------------------

The existing USB SSH address, private key and verified host key file are reused.
The private key is referenced by path, never embedded in the EXE or copied into
the distribution. SSH enforces BatchMode, IdentitiesOnly and strict host key
checking. The configuration dialog permits a verified network address as well.
Changing networks does not bypass host key checks.

Each connection verifies the exact handset disk identity and installs/updates
the small agent under /usr/local/lib/etherpocket-control. SSH then runs it as
mobian on display :0. FFmpeg produces MJPEG over stdout while bounded JSON input
events arrive over stdin. Mouse and key state use XTest; Unicode typing uses
xdotool without a shell. There is no listening TCP server or boot service.
The agent releases its own held keys/buttons at disconnect and terminates its
capture subprocess, including a bounded kill if output cannot drain.

This engineering tool uses the workstation's existing root SSH access to prepare
the helper; it is not a new restricted-access account provisioning system.
Screen captures are saved locally only when requested. No credentials are logged.

Verification
------------

Four transport tests passed, covering chunked JPEG framing, truncation,
letterboxed coordinate mapping and SSH host validation. Hardware acceptance
used a temporary xev window for typing and X server queries for pointer/button
state, checking text, Polish characters, modifiers, button release, frames and
clean stop. The original foreground window was restored afterwards.

The GUI received live frames, disconnected cleanly and reconnected. The frozen
Windows EXE also received eight live frames in its automated smoke test. See
evidence/etherpocket-control-device.json, evidence/etherpocket-control-gui.json
and evidence/etherpocket-control-exe-final.json. These checks establish basic
desktop control, not high-frame-rate video or long-duration reliability.

Build with ``powershell -NoProfile -File etherpocket-control/build.ps1``.
The build creates the application directory and desktop and Start menu shortcuts. Configuration
defaults refer to the current workstation's existing keys; another workstation
must supply its own authorized SSH key and verified known_hosts file.
