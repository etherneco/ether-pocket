EtherFiles 0.1.1 — network protocol acceptance
=============================================

Result
------

Authenticated SFTP, SMB and WebDAV integration pipelines passed on both the
Debian amd64 build host and the physical ARM64 EtherPocket. Unknown SSH hosts,
changed SSH keys and untrusted TLS certificates were rejected. Each isolated
client's SSH known_hosts file remained byte-for-byte unchanged.

The tested servers were real disposable OpenSSH, Samba and WsgiDAV/Cheroot
instances, serving real temporary filesystem directories. They were not mock
responses or production accounts. The phone used a separate unprivileged test
account and private D-Bus/configuration/data directories. Its tests ran the
same C++ Services, DirectoryModel and Operations code linked into EtherFiles.
They exercised connection/authentication and actual filesystem transfers;
they did not automate typing credentials into the QML connection dialog.

For each protocol the pipeline verified:

* Rejection of an incorrect password, followed by a successful corrected login.
* Actual directory listing and file metadata.
* Download of a server-side sentinel, checked against its original bytes.
* Creation of a remote directory and upload of a 64 KiB Unicode-named file.
* Download and byte comparison of that uploaded file.
* Conflict Skip preserving the existing bytes.
* Explicit Replace committing the replacement bytes.
* Rename and move into a remote subdirectory, preserving the file size.
* Recursive filename search across the remote directory.
* Explicit deletion of only the disposable test subtree.
* Absence of the fixture password in EtherFiles configuration and job state.

Additional cases verified first-contact SSH identity refusal, a deliberately
mismatching saved SSH key, and refusal of a self-signed/untrusted TLS certificate.
Six network test groups passed on each architecture. The local-file regression
suite also passed again on both architectures: 16 passed, zero failed, zero
skipped, including QtTest setup/cleanup. All six private X11 UI checks passed.

Evidence and delivered fix
--------------------------

* evidence/etherfiles-network-host.json — amd64 network results.
* evidence/etherfiles-network-arm64.json — native ARM64 results and trust-file check.
* evidence/etherfiles-tests-host-network-release.txt — local-file regression.
* evidence/etherfiles-tests-arm64-network-release.txt — phone regression.
* evidence/etherfiles-ui-network-release.json — UI regression results.
* evidence/etherfiles-install-0.1.1.json — installation digest/preserved baseline.
* build/etherfiles_0.1.1_arm64.deb — updated native Debian package.

Version 0.1.1 bounds repeated password prompts rather than indefinitely
resubmitting a rejected credential. It supplies a backend's default SMB domain
when requested. Identity questions explicitly select refusal; a backend success
or already-mounted result cannot override an identity-rejection error. Unknown
remote size/hidden/symlink/time attributes are checked before reading them,
avoiding assumptions based on local filesystem metadata. Explicit refresh now
stops a pending debounce timer to avoid redundant enumeration. The Debian
package explicitly requires openssh-client, needed by the GVfs SFTP backend.

The initial build-host SFTP failures were fixture/environment problems rather
than a substituted success: the host lacked openssh-client, and the first
private runtime path exceeded the Unix-domain socket limit used by OpenSSH
ControlPath. The final tests used standard OpenSSH and short private runtime
directories. Negative host-key cases used non-loopback addresses because the
installed GVfs backend deliberately configures NoHostAuthenticationForLocalhost;
using only loopback would not exercise its remote host-key validation path.
On the phone, those cases reached the fixture through its USB interface address
and a narrowly scoped proxy to the temporary SSH reverse tunnel. No user/system
SSH trust configuration was changed to make a failed check pass.

The DAV backend emitted standard::size warnings from its own process during
remote directory handling. EtherFiles now tolerates absent remote attributes;
the warnings did not prevent byte-verified transfers or metadata/search tests.
No credential manager was installed in the isolated test sessions. Passwords
were kept in memory by EtherFiles and never saved into its ordinary state files.
Private fixture credentials existed only for the test harness and were removed.

Reproduction and cleanup
------------------------

etherfiles/tests/network_servers.py starts the fixture servers in a fresh
root-owned directory under /opt/etherpocket on the build host. It needs OpenSSH
server/client, Samba and a Python environment containing wsgidav and cheroot.
Select a private build-host address with --bind and a new --work directory.
The SFTP server is chrooted and restricted to the newly created efnetserver
account. Samba uses a private passdb rather than changing an existing Unix
account's login password. WebDAV uses a generated random fixture password.
Generated private keys and the private server password databases are deleted
when the fixture exits.

With BUILD_TESTING=ON, CMake builds etherfiles-network-tests. It reads its
credentials from a private fixture JSON file, never from command-line arguments,
and writes public results without passwords. Run it unprivileged in a private
D-Bus session, with isolated XDG directories and a short XDG_RUNTIME_DIR.
Populate only that isolated account's known_hosts from the fixture's generated
public-key file; preserve the intentionally mismatching entry for the rejection
case. Do not disable identity checking to run these tests.

For device validation, forward fixture ports 22422, 22423, 22425, 22443, 22445 and
22480 to phone loopback through the existing pinned SSH connection. Then run
scripts/test-etherfiles-network-device.py with the compiled ARM64 test executable
in build/etherfiles-network-tests-arm64. The helper creates the separate phone
client, copies only fixture credentials/public trust information over SSH,
starts the scoped USB-address proxy for SSH identity cases, runs the tests,
collects public evidence and removes the phone account and its files. Its final
cleanup now waits for the proxy/backend processes to exit before deleting the
account; the first cleanup attempt raced proxy shutdown and was completed
explicitly after the process exited.

All fixture servers, temporary accounts, served directories, password databases,
private keys, client configuration and SSH reverse tunnels used in this run
have been removed. Newly installed build-host SSH/Samba server services were
disabled; they were not started as permanent services. Test dependencies remain
available on the development host. No fixture server was installed on the phone.
The phone's own SSH, NetworkManager, kernel, Thunar and display setup were kept.
Only EtherFiles was upgraded from 0.1.0 to 0.1.1 on the phone.

Acceptance limits
-----------------

These results establish interoperability with the controlled OpenSSH/Samba/
WsgiDAV fixtures, not every production deployment. Domain/Kerberos integration,
SSH key/passphrase/agent combinations, trusted-CA HTTPS WebDAV, sustained
disconnect/reconnect and interrupted large network transfers remain separate
acceptance work. The positive WebDAV transfer used authenticated HTTP over the
controlled SSH-tunneled test path; the TLS case verified rejection of an
untrusted certificate. No trusted-CA HTTPS success is claimed.

Physical AR switching, touch/keyboard acceptance and the remaining advanced
application features in etherfiles/README.rst are unchanged by this update.
The pre-existing EtherShell Experience.qml corruption and live shell rebuild
remain outstanding; this update does not replace or restart EtherShell.

Backend references
------------------

* https://docs.gtk.org/gio/iface.File.html
* https://github.com/GNOME/gvfs/blob/1.57.2/daemon/gvfsbackendsftp.c
* https://github.com/GNOME/gvfs/blob/1.57.2/daemon/gvfsbackenddav.c
* https://www.samba.org/samba/docs/current/man-html/smb.conf.5.html
* https://wsgidav.readthedocs.io/en/stable/user_guide_configure.html
