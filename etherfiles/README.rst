EtherFiles 0.1.1
================

Native Qt 6/QML/C++ Linux file manager for EtherPocket and EtherAir, developed
against Debian 13, X11 and ARM64. This is an initial working implementation;
it does not yet satisfy every release acceptance criterion in the full brief.
No sample filesystem entries are shipped or displayed. No root GUI, Wayland,
Android service, partition change, kernel replacement or Thunar change is used.

Discovery and implementation plan
---------------------------------

The existing EtherShell has C++/QML, an XDG desktop-file launcher, EtherSurface
window policies, a separate X11 keyboard, QScreen/XRandR display discovery and
an ARM64 multiarch CMake toolchain. It used Thunar for its Files action and had
no reusable file operation engine. Shared colours now live in
ethershell/qml/EtherPalette.qml, used by both apps. EtherFiles is a normal Qt
window, so the existing keyboard and window manager can handle it without a
new keyboard daemon. EtherShell's source launcher now prefers EtherFiles when
installed and retains Thunar as its fallback; rebuilding the shell is separate.

The phone audit on 2026-10-17 found Debian's running 4.14.117-perf kernel, an
active SSH and NetworkManager service, and libarchive. GVfs, GVfs backends,
UDisks2 and Qt PDF were not installed at that audit. GIO/GVfs was selected
over KIO to reuse Debian desktop authentication, file services and Trash.
PDF preview uses bounded Poppler helper processes rather than Qt PDF.

Implementation order: reusable filesystem model and safe workers; touch and
desktop QML against those workers; previews/network/storage/archive services;
unprivileged safety tests; ARM64 package and isolated device render; then
physical touchscreen, AR display and authenticated remote-server acceptance.

Build and packaging
-------------------

On Debian install build-essential, cmake, ninja-build, pkg-config,
qt6-base-dev, qt6-declarative-dev, libglib2.0-dev and libarchive-dev::

  cmake -S etherfiles -B build/etherfiles -G Ninja -DCMAKE_INSTALL_PREFIX=/usr
  cmake --build build/etherfiles --parallel 2
  QT_QPA_PLATFORM=offscreen ctest --test-dir build/etherfiles --output-on-failure
  cd build/etherfiles
  cpack -G DEB

Run tests as an unprivileged user in a D-Bus session; for an SSH/headless
terminal, prefix the test command with dbus-run-session --. On the existing Debian multiarch build host,
install ARM64 Qt/GIO development libraries and libarchive13t64:arm64, then run::

  sh scripts/build-etherfiles-cross.sh

The toolchain is ethershell/cmake/debian-arm64.cmake. For libarchive the public
header is architecture independent; linking selects the target library. No
host library may be substituted for the target library. CPack computes shared
library dependencies and includes QML runtime modules, GVfs and UDisks2.
Poppler, FFmpeg, xfce4-terminal and a credential agent are recommended.

Install a built ARM64 package with ``sudo apt install ./etherfiles_0.1.1_arm64.deb``
on Debian ARM64. Run ``etherfiles`` or ``etherfiles /path`` as the desktop user.
The desktop entry advertises inode/directory support but does not change the
system default. To opt in use ``xdg-mime default etherfiles.desktop inode/directory``.
To revert use ``xdg-mime default thunar.desktop inode/directory``.
``sudo apt remove etherfiles`` removes the package, leaving user files and
configuration intact. No installer scripts change EtherShell, Thunar or boot.

Architecture and safety
-----------------------

DirectoryModel is a real GIO URI-based list model. Local paths, trash:///,
recent:/// and mounted GVfs URIs share one interface. Enumeration/search run
on a pool of at most two workers, use a 30-second cancellation deadline,
cap results at 100,000, and publish only the latest request. QML GridView
virtualizes delegates. A local QFileSystemWatcher is debounced; Refresh is
always available if inotify limits are reached. All metadata is from GIO and
lstat: owner/group, UID/GID, mode, size, MIME, times, link target and filesystem.

Operations uses one bounded worker and at most 32 queued/running jobs.
Copy/move/create/rename/Trash/restore/delete/permissions use filesystem APIs,
never shell command strings. File copies go through a unique sibling temporary
entry, then commit by GIO move. A collision pauses for Replace, Skip, Keep both
or Cancel, with an optional remaining-conflicts policy. Replace refuses whole
directories. Moves remove each source only after its destination commits.
Recursive operations do not follow symlinks. Local destination containment is
checked after resolving parent symlinks. Permissions use O_NOFOLLOW and fchmod
and never recurse or invoke sudo. There is no fallback from Trash to deletion.

Cancellation retains completed entries, reports partial results and removes
the active file's temporary entry. It does not roll back a multi-file operation.
Progress includes current bytes, speed and remaining time for the current file.
Restart recovery uses a private, atomically saved operation journal. Interrupted
jobs are shown explicitly and never replayed automatically. Atomicity/durability
is subject to filesystem and remote-backend semantics; this is not a transactional
filesystem or a guarantee against power failure.

Services handles X11 file clipboard conventions (URI list, GNOME copy/cut and KDE
cut selection), XDG opening, terminal, bookmarks, hashes, previews, archives,
GVfs mounts and UDisks2. Background developer/archive/network work uses one worker; previews use a
separate two-worker pool, cancel obsolete requests and clear queued previews. Text is
plain, limited to 128 KiB, and rejects NUL-containing data. Images are limited
to 32 MiB/64 megapixels, decoded at thumbnail size, with a 32 MiB memory cache.
PDF/video helpers have memory/CPU limits, timeouts and cancellation; generated
previews have a 64 MiB disk cache. Video is never played during browsing.

libarchive reads ZIP/TAR/TAR.GZ/TAR.XZ/7z when supported by the installed library.
Extraction stages in a private directory and commits to a new *-extracted
directory. It rejects absolute/traversing paths, symlinks, hard links, special
files and duplicate files, and enforces 100,000 entries, 1 GiB expanded data,
1000x ratio after a 64 MiB allowance, and a 60-second deadline. ZIP creation
also stages and refuses collisions, symlinks and a destination inside an input
folder. Archive names and file names never become executable shell strings.

User guide and gestures
-----------------------

The app chooses Pocket below 900 logical pixels, based on its own available
window space. A newly connected external display does not force a window
onto another screen. More offers explicit Pocket/Desktop/Automatic modes.
The same model/panes remain alive across changes, preserving selection and
operations. The existing shell/display manager handles actual screen placement.

Pocket: tap opens; long press selects; subsequent taps toggle selection.
The three-dot item action opens its context menu. Swipe scrolls. Pull down
beyond the top to refresh. Bottom New/Select/Sort/View/More becomes contextual
Copy/Move/Trash/Details/Actions. A selected filename is shown in full below
the grid. Category chips search real Home descendants when explicitly chosen.
Documents currently selects PDF; other document formats remain accessible
through the Documents place and normal search.

Desktop: click selects, Ctrl+click adds, double click opens. Sidebar, tabs,
preview panel, grid/list/compact and split view are available. Click a pane
to make it active; its border indicates the target. Copy/Move to other pane
uses that pane's current destination. Tab folders/history/sort/view/hidden,
window dimensions, theme, preview/split and separate default Pocket/Desktop
view choices persist. Sidebar width is currently fixed.

Shortcuts: Alt+Left/Right/Up navigate; Ctrl+T/W create/close tab; Ctrl+Shift+T
restores a closed tab; Ctrl+Tab cycles; Ctrl+A selects all; Ctrl+C/X/V manages
files; Ctrl+H toggles hidden; F2 renames; F5 refreshes; Delete asks for Trash.
Enter in the location field opens a local path or an already mounted URI.
Search matches filename/extension or MIME text; subfolder scanning is opt-in.
The Filter dialog adds extension, MIME, byte-size range, modified-date range,
hidden entries and folder/home scopes. Choose a device in Places to search it.
Sort is Name/Size/Type/Modified, with folders first and reversible order.

Network, storage and developer mode
-----------------------------------

Connect to server accepts sftp://host:port/path, smb://host/share,
dav://host/path or davs://host/path. Username and password are separate fields;
password is cleared after submission and is not saved in configuration.
GIO/GVfs delegates SSH keys and identity/certificate checks to installed system
backends. Unknown/changed host identity questions are refused with the system
message; verify independently and connect using a system client first. Do not
disable host-key or certificate verification. Existing system credentials may
be used by GVfs, but EtherFiles requests no password persistence. A mount is
cancelled/timed out after 60 seconds. Retry by connecting again. Saved
bookmarks store credential-free URIs. No offline write cache is implemented.

Mounted filesystems show real free/total space. UDisks2 discovery lists
removable/USB filesystems while filtering HintSystem/HintIgnore and internal
drives. Mount/unmount/eject use asynchronous D-Bus requests and ordinary
polkit authorization. Unmount before eject. No partition editing or formatting
workflow exists. A filesystem's appearance alone never automatically mounts it.

Enable Developer mode from More for SHA-256/SHA-512 and octal non-recursive
permissions. Properties shows available metadata. Copy paths, terminal here,
plain text/config/code preview and default external editor opening are available.
Open with lists real registered applications for a filename MIME association.
New can create a symbolic link with an explicit relative or absolute target.
Long results can be tapped to open a selectable result dialog.

Recovery
--------

Close EtherFiles normally or terminate only its process if necessary; pending
operations are cancelled on normal shutdown. Thunar remains usable. Relaunch
to inspect interrupted jobs. Compare original/destination files before retrying.
Unique .etherfiles-* entries may remain after a crash; inspect and remove only
known staging entries after confirming no operation is using them. Do not
blindly delete hidden files or automatically replay a transfer.

Configuration is QSettings under ~/.config/Etherneco/EtherFiles.conf. The job
journal is operations.json under QStandardPaths AppLocalDataLocation, usually
~/.local/share/Etherneco/EtherFiles. Previews are under the analogous cache
location. Rename the configuration file to reset layout; this touches no user
documents. Unmount network storage using the system desktop client if a GVfs
backend fails. Preserve the standard XFCE/Thunar recovery environment.

Known limitations and remaining release work
--------------------------------------------

This 0.1 implementation is not the completed 17-phase release. Physical AR
connect/disconnect, native finger gestures/keyboard interaction, mounted USB,
and production-server-specific authentication/failure recovery need acceptance
on their real devices/servers. Controlled network-fixture acceptance is recorded
in the 0.1.1 update below. The test report in ../docs/etherfiles-2026-10-17.rst
distinguishes host/device evidence and unverified features.

Remaining functionality: interactive new-host verification, connection profiles
and credential-manager UI, desktop sharing portal, file drag/drop, recursive
permission workflow, syntax highlighting, selected-entry archive extraction,
archive modification/password prompts, undo beyond Trash restore, pause/resume,
automatic retry policy, resizable/persisted sidebar, persistent closed-tab undo,
notification-server integration and full recent-file registration. List view
currently shows name/size rather than a sortable metadata table. Thumbnails
for PDF/video are generated on selection rather than during scrolling. Loading
large directories is asynchronous but publishes a completed bounded list rather
than streaming batches. Archives containing links are deliberately refused.

No claim is made that all long-running operations survive sudden power loss,
that an unfamiliar remote backend implements local atomicity, or that the
whole EtherPocket regression suite has passed from an isolated app build.

Network validation update (0.1.1)
---------------------------------

Authenticated SFTP (OpenSSH), SMB (Samba) and WebDAV (WsgiDAV) integration
checks passed on amd64 and the physical ARM64 phone against disposable real
servers. Verified listing/metadata, 64 KiB Unicode upload and byte-checked
download, conflict skip/replace, rename/move, recursive search, explicit test
cleanup and absence of fixture passwords in application state. Wrong passwords,
unknown SSH hosts, changed SSH host keys and an untrusted TLS certificate were
rejected; the client's known_hosts file was unchanged. See
../docs/etherfiles-network-2026-10-17.rst for scope and reproduction notes.

Version 0.1.1 bounds repeated credential prompts, preserves a backend's default
SMB domain, explicitly selects refusal on identity questions, and prevents a
backend's success result from overriding an identity rejection. Missing remote
metadata is handled without assuming every backend exposes local attributes.
The package now explicitly depends on openssh-client for GVfs SFTP support.
