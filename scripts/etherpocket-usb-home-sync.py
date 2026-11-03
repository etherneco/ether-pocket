#!/usr/bin/python3
"""Three-way sync of user files; run as mobian while the FAT disk is local."""
import hashlib
import json
import logging
import os
from pathlib import Path
import shutil
import stat
import tempfile
import time

HOME = Path('/home/mobian')
DISK = Path('/media/mobian/ETHERPOCKET')
STATE = HOME / '.local/share/etherpocket/usb-home/state.json'
IGNORED = {'usb', 'system volume information', '$recycle.bin', 'recycler'}
MAX_FILE = 2**32 - 1


def fingerprint(path):
    before = path.stat()
    with path.open('rb') as stream:
        digest = hashlib.file_digest(stream, 'sha256').hexdigest()
    after = path.stat()
    if (before.st_size, before.st_mtime_ns, before.st_ino) != (after.st_size, after.st_mtime_ns, after.st_ino):
        raise RuntimeError('File changed during scan: ' + str(path))
    return digest


def valid_name(name):
    if name.startswith('.') or name.casefold() in IGNORED:
        return False
    if name.endswith((' ', '.')) or any(c in '<>:"/\\|?*' or ord(c) < 32 for c in name):
        raise RuntimeError('Name incompatible with FAT32: ' + name)
    if name.split('.')[0].upper() in {'CON', 'PRN', 'AUX', 'NUL', *(f'COM{i}' for i in range(1, 10)), *(f'LPT{i}' for i in range(1, 10))}:
        raise RuntimeError('Reserved Windows name: ' + name)
    return True


def inventory(root):
    files, directories = {}, set()
    for parent, dirs, names in os.walk(root, followlinks=False):
        names_seen = set()
        accepted = []
        for name in sorted(dirs + names):
            path = Path(parent) / name
            if not valid_name(name) or path.is_symlink():
                continue
            kind = path.lstat().st_mode
            if not (stat.S_ISDIR(kind) or stat.S_ISREG(kind)):
                continue
            if name.casefold() in names_seen:
                raise RuntimeError('Case collision in: ' + str(parent))
            names_seen.add(name.casefold())
            relative = path.relative_to(root).as_posix()
            if stat.S_ISDIR(kind):
                accepted.append(name)
                directories.add(relative)
            else:
                if path.stat().st_size > MAX_FILE:
                    raise RuntimeError('File exceeds FAT32 limit: ' + str(path))
                files[relative] = fingerprint(path)
        dirs[:] = accepted
    return files, directories


def safe_path(root, relative):
    parts = Path(relative).parts
    if not parts or Path(relative).is_absolute() or any(p in ('.', '..') or not valid_name(p) for p in parts):
        raise RuntimeError('Invalid sync path: ' + relative)
    path = root
    for part in parts:
        path = path / part
        if path.is_symlink():
            raise RuntimeError('Refusing a symlink: ' + str(path))
    return path


def atomic_copy(source, target, expected, home_target=False):
    if source.is_symlink() or target.is_symlink():
        raise RuntimeError('File changed to a symlink')
    target.parent.mkdir(parents=True, exist_ok=True)
    mode = stat.S_IMODE(target.stat().st_mode) if target.exists() else 0o644
    descriptor, temporary = tempfile.mkstemp(prefix='.usb-sync-', dir=target.parent)
    try:
        digest = hashlib.sha256()
        with os.fdopen(descriptor, 'wb') as output, source.open('rb') as stream:
            while block := stream.read(1024 * 1024):
                digest.update(block)
                output.write(block)
            output.flush()
            os.fsync(output.fileno())
        if digest.hexdigest() != expected:
            raise RuntimeError('Source changed while copying: ' + str(source))
        if home_target:
            os.chmod(temporary, mode)
        os.replace(temporary, target)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


def synchronize(home=HOME, disk=DISK, state=STATE):
    previous = json.loads(state.read_text()) if state.exists() else {'files': {}, 'directories': []}
    home_files, home_dirs = inventory(home)
    disk_files, disk_dirs = inventory(disk)
    spellings = {}
    for relative in set(home_files) | home_dirs | set(disk_files) | disk_dirs:
        key = relative.casefold()
        if key in spellings and spellings[key] != relative:
            raise RuntimeError('Cross-device case collision: ' + relative)
        spellings[key] = relative
    baseline = previous['files']
    # Enough room before any overwrites/deletions; reserve space for conflicts.
    required = sum(safe_path(home, p).stat().st_size for p, h in home_files.items() if disk_files.get(p) != h)
    if required + 16 * 1024 * 1024 > shutil.disk_usage(disk).free:
        raise RuntimeError('USB disk is too small for the home files')
    state.parent.mkdir(parents=True, exist_ok=True)
    stamp = time.strftime('%Y%m%d-%H%M%S') + '-' + str(time.time_ns() % 1000000)
    backup_root = state.parent / 'backups' / stamp

    def archive(path, relative):
        if path.exists():
            target = backup_root / relative
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(path, target)

    for relative in sorted(set(baseline) | set(home_files) | set(disk_files)):
        h, u, old = home_files.get(relative), disk_files.get(relative), baseline.get(relative)
        hp, up = safe_path(home, relative), safe_path(disk, relative)
        if h == u:
            continue
        # Check for local writes since the inventory before replacing a file.
        if h is not None and fingerprint(hp) != h:
            raise RuntimeError('Home file changed during sync: ' + relative)
        if h == old:  # USB edit or deletion; preserve old local content in backups.
            archive(hp, relative)
            if u is None:
                hp.unlink()
            else:
                atomic_copy(up, hp, u, home_target=True)
        elif u == old:  # Phone edit or deletion.
            if h is None:
                archive(up, relative)
                up.unlink()
            else:
                atomic_copy(hp, up, h)
        elif h is None:  # Phone deleted a file which the USB host edited.
            atomic_copy(up, hp, u, home_target=True)
        elif u is None:  # USB deleted a file which the phone edited.
            atomic_copy(hp, up, h)
        else:  # Both edited: keep phone original plus a named USB conflict copy.
            conflict = relative + '.usb-conflict-' + stamp
            atomic_copy(up, safe_path(home, conflict), u, home_target=True)
            atomic_copy(up, safe_path(disk, conflict), u)
            atomic_copy(hp, up, h)
            logging.warning('Kept both versions: %s', conflict)

    # Propagate empty-directory changes, never recursively remove user files.
    old_dirs = set(previous['directories'])
    for relative in sorted(old_dirs - home_dirs, key=lambda p: (-p.count('/'), p)):
        try:
            safe_path(disk, relative).rmdir()
        except (FileNotFoundError, OSError):
            pass
    for relative in sorted(old_dirs - disk_dirs, key=lambda p: (-p.count('/'), p)):
        try:
            safe_path(home, relative).rmdir()
        except (FileNotFoundError, OSError):
            pass
    for relative in sorted((home_dirs | disk_dirs) - old_dirs):
        safe_path(home, relative).mkdir(parents=True, exist_ok=True)
        safe_path(disk, relative).mkdir(parents=True, exist_ok=True)
    new_home, new_home_dirs = inventory(home)
    new_disk, new_disk_dirs = inventory(disk)
    if new_home != new_disk:
        raise RuntimeError('Files changed during sync; baseline was not updated')
    pending = state.with_suffix('.new')
    with pending.open('w') as output:
        json.dump({'files': new_home, 'directories': sorted(new_home_dirs & new_disk_dirs)}, output)
        output.flush()
        os.fsync(output.fileno())
    os.replace(pending, state)
    logging.info('Home synchronized: %d files', len(new_home))


if __name__ == '__main__':
    logging.basicConfig(level=logging.INFO, format='%(levelname)s %(message)s')
    if os.geteuid() == 0:
        raise SystemExit('Run as mobian, not root')
    if not os.path.ismount(DISK):
        raise SystemExit('USB disk is not locally mounted')
    synchronize()
