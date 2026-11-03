EtherFiles 0.1.0 implementation and validation — 2026-10-17
=========================================================

Delivery
--------

EtherFiles is a standalone native Qt 6/QML/C++ file manager, built for ARM64
and installed as etherfiles 0.1.0 on EtherPocket. It browses real GIO filesystem
entries and performs real file operations as the desktop user. This is an
initial implementation, not completion of all 17 phases in the supplied brief.
Build/install/user/network/developer/recovery documentation and the remaining
functional limitations are in etherfiles/README.rst.

Delivered: adaptive Pocket/EtherAir layouts; real directory navigation and
metadata; grid/list/compact; selection and contextual actions; creation,
rename, safe copy/move, symlinks, Trash/restore, confirmed permanent deletion,
non-recursive permissions; file clipboard interoperability; conflict decisions,
progress/cancellation/errors and an interrupted-job journal; tabs/history,
split panes and basic layout persistence; recursive search and filters;
image/text/PDF/video preview integration; hashes and terminal/default-app/app
chooser integration; bookmarks; GIO/GVfs network connection code; UDisks2
removable-storage discovery and explicit mount/unmount/eject requests; bounded
libarchive browsing/extraction and ZIP creation; shared light/dark colours;
desktop entry and a native Debian ARM64 package.

Package: build/etherfiles_0.1.0_arm64.deb. Rebuild with
scripts/build-etherfiles-cross.sh on EtherPocketBuild. Deployment is reproducible
with scripts/deploy-etherfiles.py, which uses the existing pinned SSH host key,
checks the transferred package hash, refuses removals/protected-environment
package changes, and compares the running kernel/Thunar/SSH/NetworkManager
baseline before and after installation. The GUI refuses execution as root.

Tests and evidence
------------------

The same C++ tests passed on both Debian amd64 and the physical ARM64 phone:
16 passed, zero failed, zero skipped, including QtTest setup/cleanup. Actual
test cases cover home Trash/restore; Unicode/hidden/broken-link listings;
create/rename/copy/move/delete; replace/skip/keep-both conflict decisions;
symlink preservation/non-traversal/creation; invalid names and source containment;
conflict cancellation; archive traversal and link rejection; ZIP creation and
extraction; known SHA-256; non-executing text/binary previews; permission denial;
symlink-alias containment and size/extension filters; 2,200-file directories and
obsolete searches; image dimensions and first-page PDF rendering/metadata.
All mutations used disposable fixtures. These tests do not imply every remote
filesystem, failure mode or touchscreen interaction has been accepted.

Evidence:

* evidence/etherfiles-tests-host.txt — amd64 QtTest output.
* evidence/etherfiles-tests-arm64.txt — native phone QtTest output.
* evidence/etherfiles-tests-arm64-initial.txt — original failed /tmp Trash test.
* evidence/etherfiles-ui-results.json — six passing UI checks on private Xvfb.
* evidence/etherfiles-ui-qml.log — final UI run (no QML diagnostics).
* evidence/etherfiles-desktop.png — real project directory, desktop layout.
* evidence/etherfiles-dark-split.png — dark split layout and real directories.
* evidence/etherfiles-device-pocket.png — ARM64 offscreen home render.
* evidence/etherfiles-device-x11.png — native on-device X11 Pocket window render.
* evidence/etherfiles-device-default.png — native default launch/density render.
* evidence/etherfiles-install-result.json — package digest and preserved baseline.

The UI harness, etherfiles/tests/ui_test.py, runs unprivileged with a private
X server, private configuration and temporary real files. It verifies keyboard
rename/dialog submission, folder creation, clipboard copy/paste, cut/move,
tab create/close/restore, and adaptive resize. These six checks passed. They
do not substitute for actual finger gestures, external clipboard applications,
AR output or an on-device UI interaction run.

The first ARM64 suite correctly exposed that /tmp is a separate system tmpfs
on this phone. GIO refused Trash with “Trashing on system internal mounts is
not supported”; EtherFiles reported an error and did not delete the source.
Trash acceptance was changed to a disposable directory on the actual home
filesystem, with isolated GIO test data on that same filesystem; it passed,
including restoration of original bytes. The production engine was not changed
to bypass the refusal. The failure remains recorded for transparency.

Private test D-Bus sessions emitted GVfs FUSE mount warnings because the normal
user's /run/user/1000/gvfs mount already existed. URI-based GIO Trash/restore
and all final tests passed. FUSE paths are not required by the EtherFiles
engine, which uses GFile URIs directly.

System preservation
-------------------

The application installation added 55 userspace packages, about 39.3 MB, for
the declared GVfs/UDisks2/Poppler dependencies. It removed no packages and
upgraded no existing packages on the first installation. A later installation
updated only EtherFiles to the final artifact of the same 0.1.0 development
version. Standard Debian package triggers ran; no partition/boot image flashing,
kernel replacement, reboot or manual network/display service restart occurred.

Before/after: running kernel 4.14.117-perf; Thunar
4.20.2-1+deb13u1, binary SHA-256
62ae0d0a05446bf7cf0cc0ca0f249f3663547f643d534fe6c417146ae31d4cb0;
SSH active; NetworkManager active. Wi-Fi remained usable for package downloads
and SSH remained accessible. This is not a fresh Android dual-boot regression
test. Android, the custom bootloader, partition tables and Xorg configuration
were not opened for modification by this work. Thunar/default MIME associations
and the running EtherShell executable were not changed.

EtherShell integration and release gates
---------------------------------------

The source Files action now prefers etherfiles when installed and falls back
to Thunar. A separate EtherFiles window profile and shared EtherPalette tokens
were added without removing the Thunar profile. The installed desktop entry
offers a standalone launcher. Rebuilding/deploying the running shell integration
is still outstanding: the pre-existing ethershell/qml/Experience.qml contains
qmllint JSON rather than QML. That unrelated source corruption was discovered
during the audit and was left intact; no uncertain shell rebuild was installed.

On-device XRandR reported DSI-1 primary at 1440x3120 and DP-1 disconnected;
Xfwm4 was the current window manager. Default native Qt launch used Xft.dpi 264
and selected Pocket layout automatically after window sizing. Native X11
rendering passed as mobian. Physical AR connect/disconnect, physical touch
gesture/keyboard tests, removable-media authorization/eject, and real authenticated
SFTP/SMB/WebDAV endpoint acceptance remain outstanding. Server addresses/test
usernames were requested; no remote access success is claimed without them.

Further functional work is explicitly listed in etherfiles/README.rst, including
sharing, drag/drop, advanced archive editing/passwords, interactive host-key
confirmation, syntax highlighting, expanded persistence and notification support.
The package is useful for local file management, but is not represented as the
completed release described by the full Definition of Done.
