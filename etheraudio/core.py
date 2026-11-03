"""EtherAudio policy over the existing Pulse protocol (PipeWire or PulseAudio).

No ALSA mixer, firmware, DSP, USB-role or global service mutations belong here.
"""
import copy
import json
import math
import os
from pathlib import Path
import subprocess
import time
import uuid

CATEGORIES = ('media', 'call', 'ringtone', 'notification', 'alarm')
PRIORITIES = {'media': 10, 'notification': 20, 'navigation': 30, 'alarm': 40, 'ringtone': 50, 'call': 60, 'emergency': 70}
DEFAULTS = dict(schemaVersion=1, automatic=True, preferredOutput='', preferredInput='',
                categories={k: 70 for k in CATEGORIES}, microphonePolicy='ask-each-time', externalDisplayPolicy='preserve')


class AudioError(Exception):
    pass


def percentage(value):
    if type(value) is not int or not 0 <= value <= 100:
        raise AudioError('Volume must be an integer from 0 to 100')
    return value


def is_monitor(row):
    return row.get('name', '').endswith('.monitor') or row.get('monitor_of_sink') not in (None, '', 4294967295, '4294967295')


def volume(row):
    channels = list(row.get('volume', {}).values())
    return round(max((int(c.get('value', 0)) / 65536 * 100 for c in channels), default=0))


def category(row):
    role = row.get('properties', {}).get('media.role', '')
    return {'phone': 'call', 'communication': 'call', 'ringtone': 'ringtone', 'event': 'notification',
            'notification': 'notification', 'alarm': 'alarm'}.get(role, 'media')


class Pulse:
    def run(self, *args):
        try:
            p = subprocess.run(['pactl', *map(str, args)], capture_output=True, text=True, timeout=5,
                               env=dict(os.environ, LC_ALL='C.UTF-8'))
        except (OSError, subprocess.TimeoutExpired) as e:
            raise AudioError('Existing audio server unavailable or timed out') from e
        if p.returncode:
            raise AudioError('Audio backend rejected operation: '+p.stderr.strip()[:300])
        return p.stdout.strip()

    def snapshot(self):
        data = {kind: json.loads(self.run('--format=json', 'list', kind))
                for kind in ('sinks', 'sources', 'sink-inputs', 'source-outputs', 'cards')}
        for kind in ('sink', 'source'):
            data['default-'+kind] = self.run('get-default-'+kind)
        return data


class Audio:
    def __init__(self, directory, backend=None):
        self.directory = Path(directory)
        self.directory.mkdir(parents=True, exist_ok=True, mode=0o700)
        self.backend = backend or Pulse()
        self.config = copy.deepcopy(DEFAULTS)
        path = self.directory/'config.json'
        if path.exists():
            self.config = json.loads(path.read_text())
            self.validate(self.config)
        self.state = {'ready': False}
        self.focus = {}
        self.ducked = {}
        self.seen_streams = set()
        self.initialized = False
        self.last_devices = None
        self.manual_output = None
        self.manual_input = None
        self.suspended = False
        self.results = []
        if (self.directory/'diagnostics.json').exists():
            self.results = json.loads((self.directory/'diagnostics.json').read_text())[-100:]

    @staticmethod
    def validate(config):
        if not isinstance(config, dict) or set(config) != set(DEFAULTS) or type(config['schemaVersion']) is not int or config['schemaVersion'] != 1:
            raise AudioError('Unknown audio configuration schema or keys')
        if type(config['automatic']) is not bool or config['microphonePolicy'] not in ('ask-each-time', 'deny') or config['externalDisplayPolicy'] != 'preserve':
            raise AudioError('Unsupported audio policy')
        for key in ('preferredOutput', 'preferredInput'):
            if not isinstance(config[key], str) or len(config[key]) > 512:
                raise AudioError('Invalid preferred endpoint')
        if not isinstance(config['categories'], dict) or set(config['categories']) != set(CATEGORIES):
            raise AudioError('Unknown logical volume category')
        for value in config['categories'].values():
            percentage(value)

    def atomic(self, name, data):
        path = self.directory/name
        temporary = path.with_suffix('.new')
        with temporary.open('w', encoding='utf-8') as f:
            json.dump(data, f, indent=2)
            f.flush()
            os.fsync(f.fileno())
        temporary.replace(path)
        if os.name == 'posix':
            fd = os.open(self.directory, os.O_RDONLY | getattr(os, 'O_DIRECTORY', 0))
            try: os.fsync(fd)
            finally: os.close(fd)

    def configure(self, changes):
        if not isinstance(changes, dict) or set(changes)-set(DEFAULTS) or 'schemaVersion' in changes:
            raise AudioError('Unknown configuration fields')
        next_config = dict(self.config, **changes)
        self.validate(next_config)
        self.atomic('config.json', next_config)
        self.config = copy.deepcopy(next_config)
        if changes.get('preferredOutput') == '': self.manual_output = None
        if changes.get('preferredInput') == '': self.manual_input = None
        self.last_devices = None

    def rows(self, kind):
        return self.state.get({'sink': 'sinks', 'source': 'sources', 'sink-input': 'sink-inputs', 'source-output': 'source-outputs'}[kind], [])

    def find(self, kind, ident):
        for row in self.rows(kind):
            if str(row.get('index')) == str(ident) or row.get('name') == str(ident):
                return row
        raise AudioError('Endpoint/stream disappeared; refresh and try again')

    def call_active(self):
        return any(category(s) == 'call' and not s.get('corked', False) for s in self.state.get('sink-inputs', [])) or any(f['kind'] in ('call', 'emergency') for f in self.focus.values())

    def select(self, kind, ident, manual=True):
        if kind not in ('sink', 'source'):
            raise AudioError('Invalid endpoint type')
        row = self.find(kind, ident)
        if kind == 'source' and is_monitor(row):
            raise AudioError('Speaker monitor is not a microphone')
        if self.call_active():
            raise AudioError('Active call protects routing; end the call before changing endpoints')
        old = self.state.get('default-'+kind)
        moved = []
        streams = self.state.get('sink-inputs' if kind == 'sink' else 'source-outputs', [])
        # Never move another application's live recording to a different microphone.
        if kind == 'source' and streams:
            raise AudioError('Stop active recordings before changing microphone')
        try:
            self.backend.run('set-default-'+kind, row['name'])
            for stream in streams:
                self.backend.run('move-sink-input', stream['index'], row['name'])
                moved.append((stream['index'], stream.get('sink')))
            actual = self.backend.snapshot()
            if actual['default-'+kind] != row['name']:
                raise AudioError('Default route readback mismatch')
            if kind == 'sink' and any(s.get('sink') != row['index'] for s in actual['sink-inputs'] if any(s['index'] == i for i, _ in moved)):
                raise AudioError('Stream route readback mismatch')
            if manual:
                self.configure({'preferredOutput' if kind == 'sink' else 'preferredInput': row['name']})
        except (AudioError, OSError) as error:
            failures = []
            for index, destination in reversed(moved):
                try: self.backend.run('move-sink-input', index, destination)
                except AudioError: failures.append(str(index))
            if old:
                try:
                    self.backend.run('set-default-'+kind, old)
                    if self.backend.run('get-default-'+kind) != old: failures.append('default route')
                except AudioError: failures.append('default route')
            try:
                restored = self.backend.snapshot()
                for index, destination in moved:
                    if any(s['index'] == index and s.get('sink') != destination for s in restored['sink-inputs']):
                        failures.append('stream '+str(index)+' readback')
            except AudioError: failures.append('rollback readback')
            raise AudioError(str(error)+'; rollback '+('failed: '+', '.join(failures) if failures else 'completed')) from error
        self.state.update(actual)
        if manual:
            setattr(self, 'manual_output' if kind == 'sink' else 'manual_input', row['name'])

    def set_volume(self, kind, ident, percent):
        percentage(percent)
        if kind not in ('sink', 'source', 'sink-input', 'source-output'):
            raise AudioError('Invalid volume target')
        row = self.find(kind, ident)
        # A user's edit supersedes focus restoration for this stream.
        self.ducked.pop(str(row['index']), None) if kind == 'sink-input' else None
        self.backend.run('set-'+kind+'-volume', row['index'], str(percent)+'%')
        self.state.update(self.backend.snapshot())
        if abs(volume(self.find(kind, row['index']))-percent) > 1:
            raise AudioError('Volume readback mismatch')

    def mute(self, kind, ident, wanted):
        if type(wanted) is not bool or kind not in ('sink', 'source', 'sink-input', 'source-output'):
            raise AudioError('Invalid mute request')
        row = self.find(kind, ident)
        self.backend.run('set-'+kind+'-mute', row['index'], '1' if wanted else '0')
        self.state.update(self.backend.snapshot())
        if self.find(kind, row['index']).get('mute') is not wanted:
            raise AudioError('Mute readback mismatch')

    def move(self, stream, sink):
        row = self.find('sink-input', stream)
        target = self.find('sink', sink)
        if self.call_active():
            raise AudioError('Active call protects stream routing')
        self.backend.run('move-sink-input', row['index'], target['name'])
        self.state.update(self.backend.snapshot())
        if self.find('sink-input', stream).get('sink') != target['index']:
            raise AudioError('Stream routing readback mismatch')

    def set_category(self, name, percent):
        if name not in CATEGORIES: raise AudioError('Unknown volume category')
        percentage(percent)
        previous = []
        try:
            for row in self.state.get('sink-inputs', []):
                if category(row) == name:
                    previous.append((row['index'], volume(row)))
                    self.set_volume('sink-input', row['index'], percent)
            values = dict(self.config['categories'], **{name: percent})
            self.configure({'categories': values})
        except (AudioError, OSError):
            for index, before in previous:
                self.set_volume('sink-input', index, min(100, before))
            raise

    def set_card_profile(self, name, profile):
        card = next((c for c in self.state.get('cards', []) if c['name'] == name), None)
        if card is None or card.get('properties', {}).get('device.bus') not in ('bluetooth','usb'):
            raise AudioError('Only exposed Bluetooth/USB card profiles may be selected here')
        advertised = card.get('profiles', {})
        if profile not in advertised or str(advertised[profile].get('available')).lower() in ('no','false'):
            raise AudioError('Profile is not advertised as available')
        if self.call_active() or self.state.get('source-outputs'):
            raise AudioError('Active call or recording protects the card profile')
        previous = card.get('active_profile')
        try:
            self.backend.run('set-card-profile', name, profile)
            actual = self.backend.snapshot()
            current = next((c.get('active_profile') for c in actual['cards'] if c['name'] == name), None)
            if current != profile: raise AudioError('Card profile readback mismatch')
            self.state.update(actual)
        except AudioError as error:
            restored = False
            if previous:
                try:
                    self.backend.run('set-card-profile', name, previous)
                    restored = any(c['name'] == name and c.get('active_profile') == previous for c in self.backend.snapshot()['cards'])
                except AudioError: pass
            raise AudioError(str(error)+'; profile rollback '+('verified' if restored else 'unverified')) from error

    def request_focus(self, owner, kind):
        if kind not in PRIORITIES or self.suspended: raise AudioError('Invalid focus request or system preparing for sleep')
        if len(self.focus) >= 32: raise AudioError('Too many focus leases')
        token = uuid.uuid4().hex
        previous = dict(self.focus)
        self.focus[token] = dict(owner=owner, kind=kind)
        try:
            self.apply_focus()
        except AudioError as error:
            self.focus = previous
            try:
                self.state.update(self.backend.snapshot())
                self.apply_focus()
            except AudioError as rollback:
                raise AudioError(str(error)+'; focus restoration unverified: '+str(rollback)) from error
            raise
        return token

    def release_focus(self, owner, token=None):
        if token and token in self.focus and self.focus[token]['owner'] != owner:
            raise AudioError('Focus belongs to another client')
        self.focus = {k: v for k, v in self.focus.items() if not (v['owner'] == owner and (token is None or k == token))}
        self.state.update(self.backend.snapshot())
        self.apply_focus()

    @staticmethod
    def fingerprint(row):
        p = row.get('properties', {})
        return (row.get('client'), p.get('application.process.id'), p.get('object.serial'), p.get('media.name'))

    def apply_focus(self):
        top = max((PRIORITIES[f['kind']] for f in self.focus.values()), default=0)
        for row in self.state.get('sink-inputs', []):
            key = str(row['index'])
            saved = self.ducked.get(key)
            if saved and saved['identity'] != self.fingerprint(row):
                self.ducked.pop(key);saved = None
            lower = PRIORITIES.get(category(row), 10) < top
            if lower and not saved:
                before = volume(row)
                applied = min(before, 20)
                self.backend.run('set-sink-input-volume', row['index'], str(applied)+'%')
                self.ducked[key] = dict(identity=self.fingerprint(row), before=before, applied=applied)
            elif not lower and saved:
                # External edits are respected; never overwrite a user's new level.
                if abs(volume(row)-saved['applied']) <= 1:
                    self.backend.run('set-sink-input-volume', row['index'], str(min(100, saved['before']))+'%')
                self.ducked.pop(key)
        active = {str(s['index']) for s in self.state.get('sink-inputs', [])}
        self.ducked = {k:v for k,v in self.ducked.items() if k in active}

    def refresh(self):
        self.state = self.backend.snapshot()
        self.state['sources'] = [s for s in self.state['sources'] if not is_monitor(s)]
        devices = tuple((r['name'], r.get('state')) for r in self.state['sinks']) + tuple((r['name'],) for r in self.state['sources'])
        # Only topology changes trigger automatic routing; meter/volume events do not.
        topology = tuple(r['name'] for r in self.state['sinks']) + ('|',) + tuple(r['name'] for r in self.state['sources'])
        if topology != self.last_devices and self.config['automatic'] and not self.suspended and not self.call_active():
            self.last_devices = topology
            for kind, preference, manual in [('sink','preferredOutput',self.manual_output),('source','preferredInput',self.manual_input)]:
                rows = self.rows(kind)
                if not rows: continue
                chosen = next((r for r in rows if r['name'] == manual), None)
                if chosen is None:
                    chosen = next((r for r in rows if r['name'] == self.config[preference]), None)
                if chosen is None and kind == 'sink':
                    def rank(r):
                        bus = r.get('properties', {}).get('device.bus','')
                        return 3 if bus == 'bluetooth' or r['name'].startswith('bluez_') else 2 if bus == 'usb' else 1 if 'Speaker' in r['name'] else 0
                    chosen = max(rows, key=rank)
                if chosen and chosen['name'] != self.state.get('default-'+kind):
                    try: self.select(kind, chosen['name'], manual=False)
                    except AudioError as e: self.state['routeError'] = str(e)
        for row in self.state['sink-inputs']:
            identity = (row['index'], self.fingerprint(row))
            if self.initialized and identity not in self.seen_streams:
                self.backend.run('set-sink-input-volume', row['index'], str(self.config['categories'][category(row)])+'%')
        self.seen_streams = {(r['index'], self.fingerprint(r)) for r in self.state['sink-inputs']}
        self.initialized = True
        # Read effective levels before conditional focus restoration.
        self.state.update(self.backend.snapshot())
        self.state['sources'] = [s for s in self.state['sources'] if not is_monitor(s)]
        self.apply_focus()
        self.state.update(self.backend.snapshot())
        self.state['sources'] = [s for s in self.state['sources'] if not is_monitor(s)]
        for key in ('sinks','sources','sink-inputs','source-outputs'):
            for row in self.state[key]:
                row['percent'] = volume(row)
                p = row.get('properties', {})
                row['application'] = p.get('application.name') or None
                if key == 'sink-inputs': row['category'] = category(row)
        active = [r for r in self.state['source-outputs'] if not r.get('corked', False)]
        self.state.update(ready=True, timestamp=time.time(), config=self.config, focus=list(self.focus.values()),
                          recording=bool(active), recordingStreams=active, suspended=self.suspended,
                          privacy='Managed capture requires explicit per-request consent. Same-user native apps can bypass this API through Pulse/ALSA; no sandbox isolation is claimed.',
                          callAudio={'supported':False,'operational':False,'verified':False,'error':'Qualcomm modem voice session, earpiece mixer path and a real call have not been validated. A2DP is not HFP call audio.'},
                          earpiece={'supported':None,'verified':False,'error':'No validated native UCM earpiece route'},
                          focusPolicy='Cooperative ducking; pause/resume events. Exclusive hardware isolation unavailable.',
                          diagnostics=self.results)
        return copy.deepcopy(self.state)

    def diagnostic_result(self, kind, result):
        if kind not in ('playback','microphone','usb','bluetooth','routing') or result not in ('heard','not-heard','passed','failed','not-tested'):
            raise AudioError('Invalid diagnostic result')
        self.results = (self.results + [dict(timestamp=time.time(),kind=kind,result=result,
                                           output=self.state.get('default-sink'),input=self.state.get('default-source'))])[-100:]
        self.atomic('diagnostics.json', self.results)
