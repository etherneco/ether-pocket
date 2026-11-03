"""Copy phone screenshots through SSH to the Windows-owned ETHERPOCKET disk."""
import argparse
import ctypes
from ctypes import wintypes
import hashlib
import json
import logging
from logging.handlers import RotatingFileHandler
import os
from pathlib import Path
import re
import shlex
import subprocess
import tempfile
import time

ROOT = Path(__file__).resolve().parent.parent
SSH_OPTIONS = ['-i', str(ROOT / 'build/etherpocket_ed25519'),
               '-o', 'UserKnownHostsFile=' + str(ROOT / 'build/mobian-known-hosts'),
               '-o', 'StrictHostKeyChecking=yes', '-o', 'BatchMode=yes',
               '-o', 'ConnectTimeout=3', '-o', 'ConnectionAttempts=1',
               '-o', 'ServerAliveInterval=3', '-o', 'ServerAliveCountMax=1']
HOST = 'root@10.77.0.2'
REMOTE = '/home/mobian/Pictures/Screenshots/'
NAME = re.compile(r'Screenshot-\d{8}-\d{6}-\d{3}-[0-9a-f]{8}\.png')
DESTINATION = Path('E:/Pictures/Screenshots')
LIST_SCRIPT = """import json, pathlib
p = pathlib.Path('/home/mobian/Pictures/Screenshots')
print(json.dumps([[f.name, f.stat().st_size] for f in p.glob('Screenshot-*.png') if f.is_file() and not f.is_symlink()]))
"""


def disk_identity():
    """Never write to an unrelated E: drive, or mount the phone's FAT image."""
    label, filesystem = ctypes.create_unicode_buffer(261), ctypes.create_unicode_buffer(261)
    serial = wintypes.DWORD()
    ok = ctypes.windll.kernel32.GetVolumeInformationW(
        'E:\\', label, len(label), ctypes.byref(serial), None, None,
        filesystem, len(filesystem))
    if ok and label.value == 'ETHERPOCKET' and filesystem.value == 'FAT32':
        return serial.value
    return None


def run(arguments):
    return subprocess.run(arguments, check=True, capture_output=True, timeout=25,
                          creationflags=subprocess.CREATE_NO_WINDOW).stdout


def remote(command):
    return run(['ssh', *SSH_OPTIONS, HOST, command])


def synchronize():
    identity = disk_identity()
    if identity is None:
        return
    entries = json.loads(remote('python3 -c ' + shlex.quote(LIST_SCRIPT)))
    for name, size in entries:
        if not NAME.fullmatch(name) or not isinstance(size, int) or size < 8:
            continue
        target = DESTINATION / name
        # Existing names are never overwritten, preserving host edits.
        if target.exists():
            continue
        if disk_identity() != identity:
            return
        expected = remote('sha256sum -- ' + shlex.quote(REMOTE + name)).decode().split()[0]
        DESTINATION.mkdir(parents=True, exist_ok=True)
        descriptor, temporary_name = tempfile.mkstemp(prefix='.screenshot-', dir=DESTINATION)
        os.close(descriptor)
        temporary = Path(temporary_name)
        try:
            run(['scp', *SSH_OPTIONS, HOST + ':' + REMOTE + name, str(temporary)])
            with temporary.open('rb') as stream:
                if stream.read(8) != b'\x89PNG\r\n\x1a\n':
                    raise RuntimeError('Invalid PNG: ' + name)
                stream.seek(0)
                actual = hashlib.file_digest(stream, 'sha256').hexdigest()
            if temporary.stat().st_size != size or actual != expected:
                raise RuntimeError('Incomplete or changed screenshot: ' + name)
            if disk_identity() != identity:
                return
            # On Windows rename fails if the destination exists; no overwrites.
            temporary.rename(target)
            logging.info('Copied %s SHA256=%s', name, actual)
        finally:
            temporary.unlink(missing_ok=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--once', action='store_true')
    args = parser.parse_args()
    log_dir = Path(os.environ['LOCALAPPDATA']) / 'EtherPocket'
    log_dir.mkdir(parents=True, exist_ok=True)
    logging.basicConfig(level=logging.INFO, format='%(asctime)s %(levelname)s %(message)s',
                        handlers=[RotatingFileHandler(log_dir / 'screenshot-sync.log',
                                                      maxBytes=1024 * 1024, backupCount=2)])
    # Hold a per-user lock across restarts/manual launches.
    import msvcrt
    with (log_dir / 'screenshot-sync.lock').open('a+b') as lock:
        lock.seek(0)
        try:
            msvcrt.locking(lock.fileno(), msvcrt.LK_NBLCK, 1)
        except OSError:
            return
        logging.info('Screenshot sync started')
        previous_error = None
        retry_delay = 2
        while True:
            try:
                synchronize()
                previous_error = None
                retry_delay = 2
            except Exception as error:
                message = str(error)
                if message != previous_error:
                    logging.warning('Will retry: %s', message)
                previous_error = message
                if args.once:
                    raise
                # Do not keep creating SSH handshakes while the device is busy
                # or refusing connections (OpenSSH pre-auth connection limits).
                retry_delay = min(300, max(15, retry_delay * 2))
            if args.once:
                return
            time.sleep(retry_delay)


if __name__ == '__main__':
    main()
