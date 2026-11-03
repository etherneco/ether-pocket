"""Privileged credential policy/store; caller identity is supplied only by transport."""
import json
import re
import sqlite3
import time
from argon2 import PasswordHasher, Type
from argon2.exceptions import VerificationError, InvalidHash


class Denied(Exception):
    pass


class Credentials:
    def __init__(self, path, primary, clock=time.time):
        self.primary = primary
        self.clock = clock
        self.kdf = PasswordHasher(time_cost=3, memory_cost=65536, parallelism=1,
                                  hash_len=32, salt_len=16, type=Type.ID)
        self.db = sqlite3.connect(path)
        self.db.execute('PRAGMA synchronous=FULL')
        self.db.execute('CREATE TABLE IF NOT EXISTS users (uid INTEGER PRIMARY KEY, pin TEXT, password TEXT, preferred TEXT NOT NULL DEFAULT "system", failures INTEGER NOT NULL DEFAULT 0, retry REAL NOT NULL DEFAULT 0)')
        self.db.execute('CREATE TABLE IF NOT EXISTS events (stamp REAL, uid INTEGER, event TEXT)')
        self.db.commit()

    def event(self, uid, kind):
        self.db.execute('INSERT INTO events VALUES (?,?,?)', (self.clock(), uid, kind))
        self.db.execute('DELETE FROM events WHERE rowid NOT IN (SELECT rowid FROM events ORDER BY rowid DESC LIMIT 1000)')

    def row(self, uid):
        self.db.execute('INSERT OR IGNORE INTO users(uid) VALUES (?)', (uid,))
        self.db.commit()
        row = self.db.execute('SELECT pin,password,preferred,failures,retry FROM users WHERE uid=?', (uid,)).fetchone()
        return dict(zip(('pin', 'password', 'preferred', 'failures', 'retry'), row))

    def reserve(self, uid):
        row = self.row(uid)
        if row['retry'] > self.clock():
            raise Denied('Authentication temporarily unavailable; retry later')
        failures = min(row['failures'] + 1, 20)
        delay = min(300, 2 ** min(failures, 9))
        self.db.execute('UPDATE users SET failures=?,retry=? WHERE uid=?', (failures, self.clock() + delay, uid))
        self.db.commit()  # Crash/cancellation counts as an attempt.
        return row

    def verify_hash(self, encoded, secret):
        if not encoded:
            return False
        try:
            return self.kdf.verify(encoded, secret)
        except (VerificationError, InvalidHash):
            return False

    def authenticated(self, uid, ok):
        if not ok:
            self.event(uid, 'authentication-failed')
            self.db.commit()
            raise Denied('Authentication failed')
        self.db.execute('UPDATE users SET failures=0,retry=0 WHERE uid=?', (uid,))
        self.db.commit()

    @staticmethod
    def secret(value):
        if not isinstance(value, str) or not value or '\0' in value or len(value.encode('utf-8')) > 16384:
            raise Denied('Invalid credential input')
        return value

    def request(self, uid, request):
        if type(uid) is not int or uid < 1 or not isinstance(request, dict):
            raise Denied('Invalid request')
        op = request.get('operation')
        row = self.row(uid)
        if op == 'status':
            return dict(pin=bool(row['pin']), password=bool(row['password']), preferred=row['preferred'],
                        retryAfter=max(0, int(row['retry'] - self.clock()) + (row['retry'] > self.clock())),
                        fingerprint=False, recovery='Debian account password', backend='Argon2id + EtherLock PAM',
                        minimumPinLength=6, maximumPinLength=32)
        if op not in ('verify', 'set', 'remove', 'prefer'):
            raise Denied('Unsupported operation')
        kind = request.get('kind')
        if kind not in ('system', 'pin', 'password'):
            raise Denied('Invalid method')
        proof = self.secret(request.get('proof'))
        row = self.reserve(uid)
        # All management requires stronger, independent system recovery proof.
        ok = self.primary(uid, proof) if op != 'verify' or kind == 'system' else self.verify_hash(row[kind], proof)
        self.authenticated(uid, ok)
        if op == 'verify':
            self.event(uid, 'authentication-success'); self.db.commit()
            return dict(authenticated=True)
        if op == 'set':
            if kind == 'system':
                raise Denied('Use the system PAM password-change conversation')
            secret = self.secret(request.get('new'))
            if secret != request.get('confirmation'):
                raise Denied('Confirmation differs')
            if kind == 'pin' and not re.fullmatch(r'[0-9]{6,32}', secret):
                raise Denied('PIN requires 6 to 32 ASCII digits')
            if kind == 'password' and len(secret) < 12:
                raise Denied('Use at least 12 characters')
            encoded = self.kdf.hash(secret)
            if not self.verify_hash(encoded, secret):
                raise Denied('Credential verification failed')
            with self.db:
                self.db.execute('UPDATE users SET ' + kind + '=? WHERE uid=?', (encoded, uid))
                self.event(uid, kind + '-changed')
        elif op == 'remove':
            if kind == 'system':
                raise Denied('System recovery cannot be removed')
            # Independently authenticated Debian password is always retained.
            with self.db:
                self.db.execute('UPDATE users SET ' + kind + '=NULL, preferred=CASE WHEN preferred=? THEN "system" ELSE preferred END WHERE uid=?', (kind, uid))
                self.event(uid, kind + '-removed')
        else:
            if kind != 'system' and not row[kind]:
                raise Denied('Enroll this credential first')
            with self.db:
                self.db.execute('UPDATE users SET preferred=? WHERE uid=?', (kind, uid))
                self.event(uid, 'method-changed')
        return self.request(uid, dict(operation='status'))

