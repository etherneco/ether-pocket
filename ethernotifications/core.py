"""Notification lifecycle and policy. No D-Bus, UI, hardware or shell execution."""
import datetime as dt
import html
import json
import os
from pathlib import Path
import re
import sqlite3
import time
from collections import deque


class Invalid(ValueError):
    pass


DEFAULTS = dict(enabled=True, silent=False, dnd='off', manualDnd=False,
                lockPrivacy='sensitive', retentionDays=7, apps={},
                schedule=dict(enabled=False, start=1320, end=420, days=[0, 1, 2, 3, 4]),
                criticalException=False)
APP_DEFAULTS = dict(enabled=True, banner=True, sound='default', vibration=False,
                    priority=-1, lockPrivacy='sensitive', grouping='thread', dndException=False)


def plain(value, limit):
    # Deliberately do not advertise body-markup. Decode the entities emitted by
    # older EtherSMS versions, strip tags and control/bidi override characters.
    return ''.join(c for c in html.unescape(re.sub(r'<[^>]*>', '', str(value)))
                   if c in '\n\t' or (ord(c) >= 32 and c not in '\u202a\u202b\u202c\u202d\u202e\u2066\u2067\u2068\u2069'))[:limit]


def validate_config(config):
    if not isinstance(config, dict) or set(config) - set(DEFAULTS):
        raise Invalid('Unknown notification setting')
    for key, value in config.items():
        if key in ('enabled', 'silent', 'manualDnd', 'criticalException'):
            if type(value) is not bool: raise Invalid('Boolean required')
        elif key == 'dnd':
            if value not in ('off', 'priority', 'alarms', 'silence'): raise Invalid('Invalid DND mode')
        elif key == 'lockPrivacy':
            if value not in ('all', 'sensitive', 'count', 'hidden'): raise Invalid('Invalid privacy mode')
        elif key == 'retentionDays':
            if type(value) is not int or not 1 <= value <= 365: raise Invalid('Retention must be 1–365 days')
        elif key == 'schedule':
            if not isinstance(value, dict) or set(value) != {'enabled', 'start', 'end', 'days'}: raise Invalid('Invalid schedule')
            if type(value['enabled']) is not bool or any(type(value[k]) is not int or not 0 <= value[k] < 1440 for k in ('start', 'end')): raise Invalid('Invalid schedule time')
            if not isinstance(value['days'], list) or any(type(d) is not int or not 0 <= d <= 6 for d in value['days']): raise Invalid('Invalid schedule days')
        elif key == 'apps':
            if not isinstance(value, dict) or len(value) > 256: raise Invalid('Too many application policies')
            for app, settings in value.items():
                if not isinstance(app, str) or len(app) > 160 or not isinstance(settings, dict) or set(settings) - set(APP_DEFAULTS): raise Invalid('Invalid app policy')
                for k, v in settings.items():
                    if k in ('enabled', 'banner', 'vibration', 'dndException') and type(v) is not bool: raise Invalid('Boolean required')
                    if k == 'sound' and v not in ('default', 'soft', 'silent'): raise Invalid('Unknown sound')
                    if k == 'priority' and (type(v) is not int or not -1 <= v <= 3): raise Invalid('Invalid priority')
                    if k == 'lockPrivacy' and v not in ('all', 'sensitive', 'count', 'hidden'): raise Invalid('Invalid app privacy')
                    if k == 'grouping' and v not in ('application', 'thread', 'category', 'none'): raise Invalid('Invalid grouping')


class Engine:
    MAX_ROWS = 2000
    MAX_ACTIVE = 512

    def __init__(self, filename, clock=time.time):
        self.clock = clock
        path = Path(filename)
        path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
        os.chmod(path.parent, 0o700)
        self.db = sqlite3.connect(path)
        os.chmod(path, 0o600)
        self.db.execute('PRAGMA journal_mode=DELETE')
        self.db.execute('PRAGMA secure_delete=ON')
        self.db.execute('CREATE TABLE IF NOT EXISTS records (id INTEGER PRIMARY KEY, stamp REAL NOT NULL, document TEXT NOT NULL)')
        self.db.execute('CREATE TABLE IF NOT EXISTS settings (key TEXT PRIMARY KEY, document TEXT NOT NULL)')
        self.config = json.loads(json.dumps(DEFAULTS))
        saved = self.db.execute("SELECT document FROM settings WHERE key='config'").fetchone()
        if saved:
            patch = json.loads(saved[0]); validate_config(patch); self.config.update(patch)
        self.rows = {}
        self.events = []
        self.rates = {}
        self.locked = True  # fail closed until the verified shell reports state
        self.sleeping = False
        self.call_active = False
        self.low_battery = False
        self.counter = int((self.db.execute("SELECT document FROM settings WHERE key='counter'").fetchone() or ['0'])[0])
        self.prune()
        for ident, document in self.db.execute('SELECT id,document FROM records ORDER BY stamp DESC LIMIT ?', (self.MAX_ROWS,)):
            row = json.loads(document)
            row['owner'] = ''  # unique D-Bus names never survive bus/service restarts
            row['actions'] = []
            self.rows[ident] = row
        self.expire()

    def configure(self, patch):
        validate_config(patch)
        updated = dict(self.config, **patch)
        self.db.execute("INSERT OR REPLACE INTO settings VALUES ('config',?)", (json.dumps(updated),))
        self.db.commit(); self.config = updated
        for row in list(self.rows.values()):
            if row['active'] and (not self.config['enabled'] or not self.app_policy(row['appId'])['enabled']):
                self.close(row['id'], 4)
        self.prune()

    def app_policy(self, app):
        return dict(APP_DEFAULTS, **self.config['apps'].get(app, {}))

    def dnd(self, now=None):
        if self.config['manualDnd']: return self.config['dnd']
        schedule = self.config['schedule']
        if schedule['enabled']:
            now = now or dt.datetime.fromtimestamp(self.clock())
            minute = now.hour * 60 + now.minute
            start, end = schedule['start'], schedule['end']
            if start > end:
                day = now.weekday() if minute >= start else (now.weekday() - 1) % 7
                active = minute >= start or minute < end
            else:
                day = now.weekday(); active = start <= minute < end
            if active and day in schedule['days']: return self.config['dnd'] if self.config['dnd'] != 'off' else 'priority'
        return 'off'

    def delivery(self, row):
        policy = self.app_policy(row['appId'])
        mode = self.dnd()
        exception = policy['dndException'] or (row['trusted'] and row['priority'] == 3 and self.config['criticalException'])
        allowed = mode == 'off' or (mode == 'priority' and (exception or row['priority'] >= 2 and policy['dndException'])) or (mode == 'alarms' and row['trusted'] and row['category'] == 'alarm')
        enabled = self.config['enabled'] and policy['enabled']
        interrupt = enabled and allowed and not self.sleeping and not self.call_active
        # Locked screens get private cards through snapshot(), never banners/audio
        # containing application text. Screen wake is deliberately not attempted.
        return dict(banner=bool(interrupt and policy['banner'] and not self.locked and row['priority'] > 0 and not self.low_battery),
                    sound=policy['sound'] if interrupt and not self.config['silent'] else 'silent',
                    vibration=bool(interrupt and policy['vibration'] and not self.config['silent']),
                    suppressed=not (enabled and allowed))

    def notify(self, owner, app, name, replaces, icon, title, body, actions, hints, timeout, trusted=False):
        if sum(len(str(v)) for v in (name, icon, title, body, actions, hints)) > 32768: raise Invalid('Notification exceeds 32 KiB')
        if len(actions) > 16 or len(actions) % 2: raise Invalid('Actions require at most eight key/label pairs')
        if any(not isinstance(x, str) or len(x) > 128 for x in actions): raise Invalid('Invalid action')
        keys = actions[::2]
        if len(set(keys)) != len(keys) or any(not re.fullmatch(r'[\w.-]{1,64}', k) for k in keys): raise Invalid('Invalid action key')
        if not -1 <= int(timeout) <= 86400000: raise Invalid('Invalid expiration')
        try: urgency = int(hints.get('urgency', 1))
        except (ValueError, TypeError): raise Invalid('Invalid urgency')
        if not 0 <= urgency <= 2: raise Invalid('Invalid urgency')
        now = self.clock()
        # Bound both per-owner and total bursts; replacing does not evade quotas.
        for bucket, limit in ((owner, 20), ('*', 100)):
            queue = self.rates.setdefault(bucket, deque())
            while queue and queue[0] < now - 10: queue.popleft()
            if len(queue) >= limit: raise Invalid('Notification rate limit exceeded')
        for bucket in (owner, '*'): self.rates[bucket].append(now)
        row = self.rows.get(int(replaces)) if replaces else None
        if replaces and (not row or row['owner'] != owner or not row['active']): raise Invalid('Replacement does not belong to sender')
        event = plain(hints.get('x-ether-event-id', ''), 128)
        if event and not replaces:
            row = next((r for r in self.rows.values() if r['appId'] == app and r.get('eventId') == event), None)
            if row: return row['id'], None  # an already processed event never re-alerts
        if not row and sum(r['active'] for r in self.rows.values()) >= self.MAX_ACTIVE: raise Invalid('Active notification limit reached')
        if not row:
            if self.counter >= 0xffffffff: raise Invalid('Notification ID space exhausted')
            self.counter += 1
            self.db.execute("INSERT OR REPLACE INTO settings VALUES ('counter',?)", (str(self.counter),))
        ident = row['id'] if row else self.counter
        priority = (0, 1, 3 if trusted else 2)[urgency]
        if trusted and type(hints.get('x-ether-priority')) is int and 0 <= hints['x-ether-priority'] <= 3:
            priority = hints['x-ether-priority']
        override = self.app_policy(app)['priority']
        if override >= 0: priority = override  # only authenticated Settings sets overrides
        if not trusted: priority = min(priority, 2)
        privacy = str(hints.get('x-ether-privacy', 'sensitive'))
        if privacy not in ('public', 'sensitive', 'secret'): privacy = 'sensitive'
        seconds = 8 if timeout == -1 else timeout / 1000
        row = dict(id=ident, appId=app, appName=plain(name, 80) or app, title=plain(title, 256), body=plain(body, 4096),
                   icon=icon if re.fullmatch(r'[A-Za-z0-9_.-]{1,100}', str(icon)) else 'dialog-information',
                   timestamp=now, priority=priority, category=plain(hints.get('category', ''), 80),
                   group=plain(hints.get('x-ether-group', ''), 128), thread=plain(hints.get('x-ether-thread', ''), 128),
                   actions=[dict(key=k, label=plain(v, 80)) for k, v in zip(actions[::2], actions[1::2])],
                   expires=now + seconds if seconds > 0 else 0, read=False, dismissed=False, active=True,
                   persistent=bool(hints.get('resident', False)), privacy=privacy,
                   transient=bool(hints.get('transient', False)) or privacy == 'secret',
                   owner=owner, trusted=trusted, eventId=event)
        self.rows[ident] = row
        if not self.config['enabled'] or not self.app_policy(app)['enabled']:
            row.update(active=False, read=True, actions=[], expires=0)
            self.events.append(('closed', owner, ident, 4))
        self.save(row)
        self.prune()
        # Replacements of ongoing system warnings update the card without repeating
        # sound/vibration. Other replacements may legitimately represent new events.
        delivery = self.delivery(row)
        if replaces and row['persistent']: delivery.update(banner=False, sound='silent', vibration=False)
        return ident, delivery

    def save(self, row):
        if row['transient']:
            self.db.execute('DELETE FROM records WHERE id=?', (row['id'],))
        else:
            saved = dict(row, owner='', actions=[])
            if row['privacy'] != 'public': saved.update(title='Private notification', body='', thread='', group='', eventId=row['eventId'])
            self.db.execute('INSERT OR REPLACE INTO records VALUES (?,?,?)', (row['id'], row['timestamp'], json.dumps(saved)))
        self.db.commit()

    def close(self, ident, reason=2, owner=None, bulk=False):
        row = self.rows.get(int(ident))
        if not row or not row['active'] or owner is not None and row['owner'] != owner: raise Invalid('Unknown notification or wrong owner')
        if bulk and row['persistent']: return False
        row.update(active=False, dismissed=reason in (2, 3), read=True, actions=[])
        self.save(row)
        self.events.append(('closed', row['owner'], row['id'], reason))
        if row['transient']: self.rows.pop(row['id'], None)
        return True

    def invoke(self, ident, key, text=None):
        if self.locked: raise Invalid('Unlock before invoking an action')
        row = self.rows.get(int(ident))
        if not row or not row['active'] or not row['owner'] or key not in [a['key'] for a in row['actions']]: raise Invalid('Action no longer available')
        if text is not None: raise Invalid('Inline reply is not registered by this application')
        row['read'] = True; self.save(row)
        self.events.append(('action', row['owner'], row['id'], key))
        if not row['persistent']: self.close(ident, 2)

    def mark_read(self, ident):
        row = self.rows.get(int(ident))
        if not row: raise Invalid('Unknown notification')
        row['read'] = True; self.save(row)

    def clear(self):
        for row in list(self.rows.values()):
            if row['active']: self.close(row['id'], bulk=True)

    def delete_history(self):
        for ident, row in list(self.rows.items()):
            if not row['active']:
                self.db.execute('DELETE FROM records WHERE id=?', (ident,)); del self.rows[ident]
        self.db.commit()

    def restore(self, ident):
        row = self.rows.get(int(ident))
        if not row or row['active']: raise Invalid('History item cannot be restored')
        row.update(active=True, read=True, dismissed=False, expires=0, actions=[], owner='')
        if sum(r['active'] for r in self.rows.values()) > self.MAX_ACTIVE:
            row['active'] = False; raise Invalid('Active notification limit reached')
        self.save(row)

    def expire(self):
        for row in list(self.rows.values()):
            if row['active'] and row['expires'] and row['expires'] <= self.clock(): self.close(row['id'], 1)

    def owner_lost(self, owner):
        self.rates.pop(owner, None)
        for row in self.rows.values():
            if row['owner'] == owner: row.update(owner='', actions=[])

    def prune(self):
        cutoff = self.clock() - self.config['retentionDays'] * 86400
        # Bound memory and disk by the same ordered retained set, including old
        # persistent rows. The SQL index avoids parsing all JSON for retention.
        self.db.execute('DELETE FROM records WHERE stamp < ?', (cutoff,))
        self.db.execute('DELETE FROM records WHERE id NOT IN (SELECT id FROM records ORDER BY stamp DESC,id DESC LIMIT ?)', (self.MAX_ROWS,))
        self.db.commit()
        for ident, row in list(self.rows.items()):
            if row['timestamp'] < cutoff:
                if row['active']: self.close(ident, 1)
                self.rows.pop(ident, None)
                self.db.execute('DELETE FROM records WHERE id=?', (ident,))
        while len(self.rows) > self.MAX_ROWS:
            ident = min(self.rows, key=lambda k: (self.rows[k]['timestamp'], k))
            if self.rows[ident]['active']: self.close(ident, 1)
            self.rows.pop(ident, None)
            self.db.execute('DELETE FROM records WHERE id=?', (ident,))
        self.db.commit()

    def snapshot(self):
        cards = []
        unread = sum(r['active'] and not r['read'] and
                     (not self.locked or (r['privacy'] != 'secret' and self.app_policy(r['appId'])['lockPrivacy'] != 'hidden'))
                     for r in self.rows.values())
        for row in sorted(self.rows.values(), key=lambda r: r['timestamp'], reverse=True):
            card = {k: v for k, v in row.items() if k not in ('owner', 'eventId', 'trusted')}
            card['canBanner'] = row['active'] and self.delivery(row)['banner']
            policy = self.app_policy(row['appId'])
            grouping = policy['grouping']
            card['groupKey'] = row['appId'] + ':' + (row['thread'] or row['group'] if grouping == 'thread' else row['category'] if grouping == 'category' else str(row['id']) if grouping == 'none' else '')
            if self.locked:
                privacy = self.config['lockPrivacy']
                app_privacy = policy['lockPrivacy']
                if privacy == 'hidden': continue
                if privacy == 'count' or app_privacy in ('hidden', 'count'): continue
                if row['privacy'] == 'secret': continue
                if row['privacy'] == 'sensitive' and (privacy == 'sensitive' or app_privacy == 'sensitive'):
                    card.update(title='Private notification', body='', thread='', group='', groupKey=row['appId'])
                card['actions'] = []
                if not row['active']: continue
            cards.append(card)
        return dict(ready=True, cards=cards, unread=unread if not self.locked or self.config['lockPrivacy'] != 'hidden' else 0,
                    config=self.config if not self.locked else {}, locked=self.locked, dnd=self.dnd(),
                    sleeping=self.sleeping, callActive=self.call_active, haptics='unverified', wake='not-supported')

    def export(self):
        return [dict(id=r['id'], appId=r['appId'], timestamp=r['timestamp'], priority=r['priority'],
                     read=r['read'], active=r['active']) for r in self.rows.values()]
