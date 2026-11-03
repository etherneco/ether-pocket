#!/usr/bin/env python3
"""Isolated OpenSSH, Samba and WebDAV integration fixtures on the build host.

Requires root to create a disposable SFTP-only Unix account and Samba process.
All content, Samba databases and generated keys live in a fresh root-owned
directory below /opt/etherpocket. Test credentials never enter source/evidence.
Clients and the EtherFiles application run as separate unprivileged users.
"""
import argparse
from contextlib import ExitStack
import json
import os
from pathlib import Path
import pwd
import secrets
import signal
import subprocess
import threading
import time

from cheroot import wsgi
from cheroot.ssl.builtin import BuiltinSSLAdapter
from wsgidav.wsgidav_app import WsgiDAVApp


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--work', required=True)
    parser.add_argument('--bind', default='127.0.0.1')
    parser.add_argument('--unix-user', default='ethershelltest')
    args = parser.parse_args()
    work = Path(args.work).resolve()
    if not work.is_relative_to('/opt/etherpocket'):
        raise SystemExit('Use a new root-owned directory under /opt/etherpocket for chroot safety.')
    work.mkdir(mode=0o711)
    owner = pwd.getpwnam(args.unix_user)
    password = secrets.token_urlsafe(30)
    sentinel = 'EtherFiles authenticated network fixture\n'
    stop = threading.Event()
    signal.signal(signal.SIGTERM, lambda *_: stop.set())
    signal.signal(signal.SIGINT, lambda *_: stop.set())
    with ExitStack() as cleanup:
        for name in ('smb', 'dav'):
            root = work/name
            root.mkdir(mode=0o700)
            (root/'server.txt').write_text(sentinel)
            os.chown(root, owner.pw_uid, owner.pw_gid)
            os.chown(root/'server.txt', owner.pw_uid, owner.pw_gid)
        key = work/'ssh_host_key'
        subprocess.run(['ssh-keygen', '-q', '-t', 'ed25519', '-N', '', '-f', str(key)], check=True)
        cleanup.callback(key.unlink, missing_ok=True)
        public = (work/'ssh_host_key.pub').read_text().split()
        wrong_key=work/'wrong_ssh_key'
        subprocess.run(['ssh-keygen','-q','-t','ed25519','-N','','-f',str(wrong_key)],check=True)
        wrong_public=(work/'wrong_ssh_key.pub').read_text().split()
        wrong_key.unlink()
        (work/'known_hosts').write_text(''.join(f'[{host}]:22422 {public[0]} {public[1]}\n[{host}]:22425 {wrong_public[0]} {wrong_public[1]}\n' for host in {'127.0.0.1', args.bind}))
        user = 'efnetserver'
        try:
            pwd.getpwnam(user)
        except KeyError:
            pass
        else:
            raise RuntimeError('The disposable server user already exists; do not reuse it.')
        subprocess.run(['useradd', '--system', '--no-create-home', '--home-dir', '/data', '--shell', '/bin/sh', user], check=True)
        cleanup.callback(subprocess.run, ['userdel', user], check=False, capture_output=True)
        subprocess.run(['chpasswd'], input=f'{user}:{password}\n', text=True, check=True, capture_output=True)
        server_user = pwd.getpwnam(user)
        jail = work/'sftp'
        jail.mkdir(mode=0o755)
        data = jail/'data'
        data.mkdir(mode=0o700)
        (data/'server.txt').write_text(sentinel)
        os.chown(data, server_user.pw_uid, server_user.pw_gid)
        os.chown(data/'server.txt', server_user.pw_uid, server_user.pw_gid)
        Path('/run/sshd').mkdir(mode=0o755, exist_ok=True)
        ssh_config = work/'sshd_config'
        addresses = list(dict.fromkeys(['127.0.0.1', args.bind]))
        ssh_config.write_text(f'''Port 22422
Port 22423
Port 22425
'''+''.join(f'ListenAddress {address}\n' for address in addresses)+f'''HostKey {key}
PidFile {work}/sshd.pid
AllowUsers {user}
PermitRootLogin no
UsePAM no
PasswordAuthentication yes
KbdInteractiveAuthentication no
PubkeyAuthentication no
PermitTTY no
AllowTcpForwarding no
X11Forwarding no
PermitTunnel no
ChrootDirectory {jail}
ForceCommand internal-sftp -d /data
Subsystem sftp internal-sftp
LoginGraceTime 10
LogLevel INFO
''')
        def process(command, log_name):
            log = cleanup.enter_context((work/log_name).open('wb'))
            child = subprocess.Popen(command, stdin=subprocess.PIPE, stdout=log, stderr=subprocess.STDOUT, start_new_session=True)
            def terminate():
                child.terminate()
                try:
                    child.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    child.kill()
                    child.wait()
            cleanup.callback(terminate)
            return child
        ssh = process(['/usr/sbin/sshd', '-D', '-e', '-f', str(ssh_config)], 'sshd.log')
        # Only this newly-created account can own these chrooted SFTP children.
        cleanup.callback(subprocess.run, ['pkill', '-TERM', '-u', str(server_user.pw_uid)], check=False, capture_output=True)

        cert, tls_key = work/'server.crt', work/'server.key'
        subprocess.run(['openssl', 'req', '-x509', '-newkey', 'rsa:2048', '-nodes', '-days', '1', '-subj', '/CN=localhost', '-addext', 'subjectAltName=DNS:localhost,IP:127.0.0.1', '-keyout', str(tls_key), '-out', str(cert)], check=True, capture_output=True)
        tls_key.chmod(0o600)
        cleanup.callback(tls_key.unlink, missing_ok=True)
        dav_app = WsgiDAVApp({
            'provider_mapping': {'/': str(work/'dav')},
            'simple_dc': {'user_mapping': {'*': {args.unix_user: {'password': password}}}},
            'http_authenticator': {'domain_controller': None, 'accept_basic': True, 'accept_digest': True, 'default_to_digest': True},
            'verbose': 0, 'logging': {'enable': False}, 'property_manager': True, 'lock_storage': True,
        })
        for address in addresses:
            for port in (22480, 22443):
                server = wsgi.Server((address, port), dav_app)
                server.shutdown_timeout = 2
                if port == 22443:
                    server.ssl_adapter = BuiltinSSLAdapter(str(cert), str(tls_key))
                server.prepare()
                threading.Thread(target=server.serve, daemon=True).start()
                cleanup.callback(server.stop)

        for name in ('private', 'state', 'cache', 'lock', 'run'):
            (work/name).mkdir(mode=0o700 if name == 'private' else 0o755)
        config = work/'smb.conf'
        config.write_text(f'''[global]
server role = standalone server
workgroup = WORKGROUP
security = user
map to guest = Never
server min protocol = SMB2_02
smb ports = 22445
interfaces = 127.0.0.1 {args.bind}
bind interfaces only = yes
disable netbios = yes
load printers = no
printing = bsd
printcap name = /dev/null
passdb backend = tdbsam:{work}/private/passdb.tdb
private dir = {work}/private
state directory = {work}/state
cache directory = {work}/cache
lock directory = {work}/lock
pid directory = {work}/run
ncalrpc dir = {work}/run/ncalrpc
log file = {work}/smbd.log
[fixture]
path = {work}/smb
valid users = {args.unix_user}
read only = no
browseable = yes
''')
        subprocess.run(['smbpasswd', '-s', '-a', '-c', str(config), args.unix_user], input=password+'\n'+password+'\n', text=True, check=True, capture_output=True)
        cleanup.callback((work/'private/passdb.tdb').unlink, missing_ok=True)
        smb = process(['smbd', '--foreground', '--no-process-group', '--configfile', str(config)], 'smb-process.log')
        fixture = work/'fixture.json'
        fixture.write_text(json.dumps({'sentinel': sentinel, 'targets': [
            {'name': 'sftp', 'uri': f'sftp://{args.bind}:22422/data/', 'user': user, 'password': password},
            {'name': 'smb', 'uri': 'smb://127.0.0.1:22445/fixture/', 'user': args.unix_user, 'password': password},
            {'name': 'webdav', 'uri': 'dav://127.0.0.1:22480/', 'user': args.unix_user, 'password': password},
        ], 'reject': [
            {'name': 'untrusted_ssh_host_rejected', 'uri': f'sftp://{args.bind}:22423/data/', 'user': user, 'password': password},
            {'name': 'changed_ssh_host_key_rejected', 'uri': f'sftp://{args.bind}:22425/data/', 'user': user, 'password': password},
            {'name': 'untrusted_tls_certificate_rejected', 'uri': 'davs://127.0.0.1:22443/', 'user': args.unix_user, 'password': password},
        ]}, indent=2))
        fixture.chmod(0o600)
        cleanup.callback(fixture.unlink, missing_ok=True)
        time.sleep(.4)
        if ssh.poll() is not None or smb.poll() is not None:
            raise RuntimeError('A fixture server failed; inspect its private log.')
        (work/'ready').write_text('ready\n')
        print(f'Disposable OpenSSH/Samba/WebDAV fixtures ready: {work}', flush=True)
        while not stop.wait(.5):
            pass


if __name__ == '__main__':
    main()
