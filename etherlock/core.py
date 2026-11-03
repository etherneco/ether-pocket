"""Policy and evidence gates. Credentials never enter this service."""
import hashlib
import json
import os
import pathlib
import stat
import time

DEFAULTS = dict(enabled=False, timeout=60, lockOnScreenOff=True, privacy='hidden')
CHECKS = ('authentication', 'repeatedUnlock', 'recovery', 'screenOff', 'resume', 'externalDisplay')
FILES = ('/usr/bin/xsecurelock', '/usr/lib/etherlock/auth_etherlock',
         '/usr/lib/etherlock/etherlock-pam', '/etc/pam.d/etherlock',
         '/usr/share/etherlock/service.py', '/usr/share/etherlock/core.py')


def policy(current, patch, validated=False):
    if not isinstance(patch, dict) or set(patch) - set(DEFAULTS):
        raise ValueError('Unknown policy field')
    result = dict(current, **patch)
    for key in ('enabled', 'lockOnScreenOff'):
        if type(result[key]) is not bool: raise ValueError('Boolean required')
    if type(result['timeout']) is not int or not 0 <= result['timeout'] <= 86400:
        raise ValueError('Timeout must be 0–86400 seconds; 0 locks immediately')
    if result['privacy'] not in ('all', 'sensitive', 'count', 'hidden'):
        raise ValueError('Invalid privacy mode')
    if result['enabled'] and not validated:
        raise ValueError('Automatic locking requires administrator acceptance for this build and boot')
    return result


def fingerprints(paths=FILES):
    return {p: hashlib.sha256(pathlib.Path(p).read_bytes()).hexdigest() for p in paths}


def validation(path='/etc/etherlock/validation.json'):
    try:
        p = pathlib.Path(path)
        info = p.lstat()
        if not stat.S_ISREG(info.st_mode) or info.st_uid != 0 or info.st_mode & 0o022:
            return {}
        data = json.loads(p.read_text())
        if data['hashes'] != fingerprints(): return {}
        if data['bootId'] != pathlib.Path('/proc/sys/kernel/random/boot_id').read_text().strip(): return {}
        return data
    except (OSError, ValueError, KeyError): return {}


def accepted(data):
    return all(data.get(k) is True for k in CHECKS)


def locker_environment(env):
    # Never inherit arbitrary auth modules, key-command hooks or debug bypasses.
    result = {k: v for k, v in env.items() if k in
              ('DISPLAY', 'XAUTHORITY', 'HOME', 'USER', 'LOGNAME', 'LANG',
               'XDG_RUNTIME_DIR', 'DBUS_SESSION_BUS_ADDRESS')}
    result.update(PATH='/usr/bin:/bin', XSECURELOCK_AUTH='/usr/lib/etherlock/auth_etherlock',
                  XSECURELOCK_BLANK_TIMEOUT='-1', XSECURELOCK_SHOW_DATETIME='1')
    return result


class LockState:
    def __init__(self, interrupted=False):
        self.phase = 'unknown' if interrupted else 'unlocked'
        self.enforced = False
        self.private = interrupted

    def request(self):
        if self.phase != 'unlocked': raise ValueError('Lock is already pending, active or needs recovery')
        self.phase = 'locking'; self.private = True

    def ready(self):
        if self.phase != 'locking': raise ValueError('Unexpected locker acknowledgement')
        self.phase = 'locked'; self.enforced = True

    def exited(self, code):
        if self.enforced and code == 0:
            self.phase = 'unlocked'; self.private = False; self.enforced = False
            return True
        self.phase = 'fault'; self.enforced = False; self.private = True
        return False


class Events:
    ALLOWED = {'locked', 'unlocked', 'lock-failed', 'policy-changed', 'recovery-required'}

    def __init__(self, directory):
        import sqlite3
        path = pathlib.Path(directory); path.mkdir(mode=0o700, parents=True, exist_ok=True)
        self.db = sqlite3.connect(path / 'events.sqlite3')
        os.chmod(path / 'events.sqlite3', 0o600)
        self.db.execute('CREATE TABLE IF NOT EXISTS events (id INTEGER PRIMARY KEY, stamp REAL, kind TEXT)')

    def add(self, kind):
        if kind not in self.ALLOWED: raise ValueError('Invalid event')
        self.db.execute('INSERT INTO events(stamp,kind) VALUES (?,?)', (time.time(), kind))
        self.db.execute('DELETE FROM events WHERE id NOT IN (SELECT id FROM events ORDER BY id DESC LIMIT 1000)')
        self.db.commit()

    def export(self):
        return [dict(timestamp=stamp, event=kind) for stamp, kind in self.db.execute('SELECT stamp,kind FROM events ORDER BY id DESC')]
