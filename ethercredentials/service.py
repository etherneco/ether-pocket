"""Root-only socket service. Never exposes secrets or authentication on D-Bus."""
import json
import os
import pathlib
import pwd
import resource
import socket
import stat
import struct
import subprocess
import syslog
from core import Credentials, Denied

SOCKET = '/run/ethercredentials/control'


def primary(uid, secret):
    account = pwd.getpwuid(uid)
    # Existing fixed PAM stack runs as the real target UID, not as root.
    process = subprocess.Popen(['/usr/lib/etherlock/etherlock-pam'],
        stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
        user=uid, group=account.pw_gid, extra_groups=[], cwd='/',
        env={'PATH': '/usr/bin:/bin', 'LANG': 'C.UTF-8'})
    try:
        output, _ = process.communicate((json.dumps({'response': secret}) + '\n').encode(), timeout=15)
        events = [json.loads(line) for line in output.splitlines()]
        return process.returncode == 0 and any(e.get('event') == 'result' and e.get('success') is True for e in events)
    except (ValueError, subprocess.TimeoutExpired):
        process.kill(); process.communicate()
        return False


def main():
    if os.getuid() != 0:
        raise SystemExit('System service requires root')
    os.umask(0o077)
    resource.setrlimit(resource.RLIMIT_CORE, (0, 0))
    directory = pathlib.Path('/var/lib/ethercredentials')
    directory.mkdir(mode=0o700, exist_ok=True)
    info = directory.lstat()
    if not stat.S_ISDIR(info.st_mode) or info.st_uid != 0 or info.st_mode & 0o077:
        raise SystemExit('Unsafe credential directory')
    store = Credentials(directory / 'credentials.sqlite3', primary)
    listener = socket.socket(socket.AF_UNIX)
    listener.bind(SOCKET)
    os.chmod(SOCKET, 0o666)  # Authentication uses kernel UID and primary proof.
    listener.listen(8)
    while True:
        connection, _ = listener.accept()
        with connection:
            connection.settimeout(15)
            uid = -1
            try:
                _, uid, _ = struct.unpack('3i', connection.getsockopt(socket.SOL_SOCKET, socket.SO_PEERCRED, 12))
                account = pwd.getpwuid(uid)
                if uid < 1000 or account.pw_shell in ('/usr/sbin/nologin', '/bin/false'):
                    raise Denied('Unavailable account')
                data = bytearray()
                while b'\n' not in data:
                    chunk = connection.recv(4096)
                    if not chunk or len(data) + len(chunk) > 131072:
                        raise Denied('Invalid request')
                    data.extend(chunk)
                request = json.loads(data)
                result = dict(ok=True, result=store.request(uid, request))
            except (Denied, ValueError, KeyError, OSError):
                result = dict(ok=False, error='Request rejected; check credentials and retry delay')
                syslog.syslog(syslog.LOG_AUTHPRIV | syslog.LOG_WARNING, 'ethercredentials request-rejected uid=%d' % uid)
            try:
                connection.sendall((json.dumps(result) + '\n').encode())
            except OSError:
                pass


if __name__ == '__main__':
    main()
