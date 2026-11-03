#!/usr/bin/python3
"""Single session-bus owner. Content never travels in broadcast extension signals."""
import hashlib
import json
import logging
import os
from pathlib import Path
import signal
import sys
import time
sys.path.insert(0, str(Path(__file__).resolve().parent))
import dbus
import dbus.service
from dbus.mainloop.glib import DBusGMainLoop
from gi.repository import GLib
from core import Engine, Invalid

NAME = 'com.etherneco.EtherNotifications1'
PATH = '/com/etherneco/EtherNotifications1'
STANDARD = 'org.freedesktop.Notifications'
STANDARD_PATH = '/org/freedesktop/Notifications'


def installed(path):
    """Require root-owned code under root-owned, non-writable parent directories."""
    path = Path(path).resolve()
    try:
        for part in (path, *path.parents):
            st = part.stat()
            if st.st_uid != 0 or st.st_mode & 0o022: return False
        return True
    except OSError:
        return False


def process_identity(bus, sender):
    uid = int(bus.get_unix_user(sender))
    if uid != os.getuid(): raise Invalid('Session UID mismatch')
    pid = int(bus.call_blocking('org.freedesktop.DBus', '/org/freedesktop/DBus', 'org.freedesktop.DBus', 'GetConnectionUnixProcessID', 's', (sender,)))
    proc = Path('/proc') / str(pid)
    exe = (proc / 'exe').resolve(strict=True)
    args = (proc / 'cmdline').read_bytes().split(b'\0')
    script = ''
    if exe.name.startswith('python'):
        for arg in args[1:]:
            value = os.fsdecode(arg)
            if value in ('-I', '-s', '-E', '-B', '-u'): continue
            if value.startswith('/') and value.endswith('.py'): script = str(Path(value).resolve())
            break  # -c/-m and arguments after the entry point cannot spoof a script
    source = script or str(exe)
    return dict(pid=pid, source=source, app=Path(source).stem + '-' + hashlib.sha256(source.encode()).hexdigest()[:12],
                installed=installed(source))


class Standard(dbus.service.Object):
    def __init__(self, service):
        self.service = service
        super().__init__(service.bus, STANDARD_PATH)

    @dbus.service.method(STANDARD, in_signature='', out_signature='as')
    def GetCapabilities(self):
        return dbus.Array(['body', 'actions', 'persistence'], signature='s')

    @dbus.service.method(STANDARD, in_signature='', out_signature='ssss')
    def GetServerInformation(self):
        return ('EtherNotifications', 'Etherneco LTD', '0.1.0', '1.2')

    @dbus.service.method(STANDARD, in_signature='susssasa{sv}i', out_signature='u', sender_keyword='sender')
    def Notify(self, app_name, replaces_id, app_icon, summary, body, actions, hints, expire_timeout, sender):
        try:
            who = self.service.identity(sender)
            # SMS/phone urgency remains high; only internal verified power events
            # receive critical system status.
            ident, delivery = self.service.engine.notify(str(sender), who['app'], str(app_name), int(replaces_id), str(app_icon),
                str(summary), str(body), [str(a) for a in actions], hints, int(expire_timeout), False)
            self.service.flush()
            if delivery: self.service.deliver(ident, delivery)
            return dbus.UInt32(ident)
        except (Invalid, OSError, ValueError) as e:
            raise dbus.DBusException(str(e), name=NAME + '.Invalid')

    @dbus.service.method(STANDARD, in_signature='u', out_signature='', sender_keyword='sender')
    def CloseNotification(self, ident, sender):
        try:
            self.service.engine.close(int(ident), 3, str(sender)); self.service.flush()
        except Invalid as e:
            raise dbus.DBusException(str(e), name=NAME + '.Denied')

    # Signatures appear in introspection. Actual emission is unicast to the
    # original unique sender, so private action/reply routing cannot be stolen.
    @dbus.service.signal(STANDARD, signature='uu')
    def NotificationClosed(self, ident, reason): pass

    @dbus.service.signal(STANDARD, signature='us')
    def ActionInvoked(self, ident, action): pass


class Service(dbus.service.Object):
    def __init__(self, bus, filename=None, authorize=None, identity=None, system=True):
        self.bus = bus
        # Never queue for, replace, or steal another daemon's name.
        self.standard_name = dbus.service.BusName(STANDARD, bus, allow_replacement=False, replace_existing=False, do_not_queue=True)
        self.name = dbus.service.BusName(NAME, bus, do_not_queue=True)
        super().__init__(self.name, PATH)
        state = Path(os.environ.get('STATE_DIRECTORY', str(Path(os.environ.get('XDG_STATE_HOME', str(Path.home()/'.local/state')))/'ethernotifications')))
        self.engine = Engine(filename or state/'history.sqlite')
        self.authorize_override = authorize
        self.identity_override = identity
        self.ui_owner = ''
        self.ui_locked = True
        self.external_locks = {}
        self.logind_sleeping = False
        self.audio_status = 'not-tested'
        self.expiration_timer = 0
        self.schedule_timer = 0
        self.ui_lease = 0
        self.standard = Standard(self)
        bus.add_signal_receiver(self.owner_changed, signal_name='NameOwnerChanged', dbus_interface='org.freedesktop.DBus', bus_name='org.freedesktop.DBus')
        if system:
            self.system = dbus.SystemBus()
            self.system.add_signal_receiver(self.sleep, signal_name='PrepareForSleep', dbus_interface='org.freedesktop.login1.Manager', bus_name='org.freedesktop.login1')
            self.system.add_signal_receiver(self.power_notice, signal_name='Notice', dbus_interface='com.etherneco.EtherPower1', bus_name='com.etherneco.EtherPower1')
            self.system.add_signal_receiver(self.power_state, signal_name='Changed', dbus_interface='com.etherneco.EtherPower1', bus_name='com.etherneco.EtherPower1')
            self.system.add_signal_receiver(self.lock_properties, signal_name='PropertiesChanged', dbus_interface='org.freedesktop.DBus.Properties', bus_name='org.freedesktop.login1', path_keyword='path')
            self.system.add_signal_receiver(self.lock_requested, signal_name='Lock', dbus_interface='org.freedesktop.login1.Session', bus_name='org.freedesktop.login1', path_keyword='path')
            self.system.add_signal_receiver(self.unlock_requested, signal_name='Unlock', dbus_interface='org.freedesktop.login1.Session', bus_name='org.freedesktop.login1', path_keyword='path')
            try:
                manager = dbus.Interface(self.system.get_object('org.freedesktop.login1', '/org/freedesktop/login1'), 'org.freedesktop.login1.Manager')
                for session, uid, user, seat, path in manager.ListSessions():
                    if int(uid) == os.getuid() and str(seat):
                        self.external_locks[str(path)] = True
                        self.read_lock(str(path))
            except dbus.DBusException: pass  # No authenticated locker is invented.
        self.flush()
        GLib.timeout_add_seconds(3600, self.maintenance)

    def identity(self, sender):
        return self.identity_override(sender) if self.identity_override else process_identity(self.bus, sender)

    def authorize(self, sender):
        if self.authorize_override:
            if self.authorize_override(sender): return
            raise Invalid('Notification UI access denied')
        who = self.identity(sender)
        source = Path(who['source'])
        allowed = str(source) == '/usr/bin/ethershell' or (str(source).startswith('/opt/ethershell2/') and str(source).endswith('/usr/bin/ethershell'))
        if not who['installed'] or not allowed: raise Invalid('Only the installed EtherShell UI may access notification content/settings')

    @dbus.service.signal(NAME, signature='')
    def Changed(self): pass

    @dbus.service.signal(NAME, signature='u')
    def Banner(self, ident): pass

    @dbus.service.method(NAME, in_signature='', out_signature='s', sender_keyword='sender')
    def GetState(self, sender):
        try:
            self.authorize(sender)
            return json.dumps(dict(self.engine.snapshot(), audioStatus=self.audio_status))
        except Invalid as e: raise dbus.DBusException(str(e), name=NAME+'.Denied')

    @dbus.service.method(NAME, in_signature='sus', out_signature='s', sender_keyword='sender')
    def Command(self, action, ident, document, sender):
        try:
            self.authorize(sender)
            if len(document) > 32768: raise Invalid('Command too large')
            data = json.loads(str(document))
            if not isinstance(data, dict): raise Invalid('Command object required')
            if action == 'session':
                if set(data) != {'locked', 'callActive', 'screenOff'} or any(type(v) is not bool for v in data.values()): raise Invalid('Invalid session state')
                self.ui_owner = str(sender)
                self.ui_locked = data['locked']
                self.engine.locked = self.ui_locked or any(self.external_locks.values())
                self.engine.call_active = data['callActive']
                self.engine.sleeping = data['screenOff'] or self.logind_sleeping
                if self.ui_lease: GLib.source_remove(self.ui_lease)
                self.ui_lease = GLib.timeout_add_seconds(90, self.lease_expired)
            elif self.engine.locked: raise Invalid('Unlock before changing notification state')
            elif action == 'configure': self.engine.configure(data)
            elif action == 'dismiss': self.engine.close(int(ident))
            elif action == 'read': self.engine.mark_read(int(ident))
            elif action == 'invoke': self.engine.invoke(int(ident), str(data.get('key', 'default')))
            elif action == 'clear': self.engine.clear()
            elif action == 'delete-history': self.engine.delete_history()
            elif action == 'restore': self.engine.restore(int(ident))
            elif action == 'export': return json.dumps(self.engine.export())
            else: raise Invalid('Unknown notification command')
            self.flush()
            return '{}'
        except (Invalid, ValueError, TypeError) as e:
            raise dbus.DBusException(str(e), name=NAME+'.Invalid')

    def lease_expired(self):
        self.ui_lease = 0; self.ui_locked = True; self.engine.locked = True; self.Changed(); return False

    def flush(self):
        while self.engine.events:
            kind, owner, ident, value = self.engine.events.pop(0)
            if not owner.startswith(':'): continue
            msg = dbus.lowlevel.SignalMessage(STANDARD_PATH, STANDARD, 'ActionInvoked' if kind == 'action' else 'NotificationClosed')
            msg.set_destination(owner)
            msg.append(ident, value, signature='us' if kind == 'action' else 'uu')
            self.bus.send_message(msg)
        if self.expiration_timer: GLib.source_remove(self.expiration_timer); self.expiration_timer = 0
        deadlines = [r['expires'] for r in self.engine.rows.values() if r['active'] and r['expires']]
        if deadlines:
            self.expiration_timer = GLib.timeout_add(max(1, int((min(deadlines)-time.time())*1000)), self.expire)
        if self.schedule_timer: GLib.source_remove(self.schedule_timer); self.schedule_timer = 0
        if self.engine.config['schedule']['enabled']:
            self.schedule_timer = GLib.timeout_add_seconds(max(1, 60-int(time.time())%60), self.schedule_boundary)
        self.Changed()

    def expire(self):
        self.expiration_timer = 0; self.engine.expire(); self.flush(); return False

    def schedule_boundary(self):
        self.schedule_timer = 0; self.flush(); return False

    def maintenance(self):
        self.engine.prune(); self.flush(); return True

    def deliver(self, ident, delivery):
        if delivery['banner']: self.Banner(dbus.UInt32(ident))
        if delivery['sound'] != 'silent':
            try:
                audio = dbus.Interface(self.bus.get_object('com.etherneco.EtherAudio1', '/com/etherneco/EtherAudio1', introspect=False), 'com.etherneco.EtherAudio1')
                audio.PlayNotification(delivery['sound'], reply_handler=lambda *a: self.audio_result('pipeline-completed; physical audibility unverified'), error_handler=lambda *a: self.audio_result('unavailable or suppressed by audio policy'))
            except dbus.DBusException: self.audio_result('audio service unavailable')
        # No direct sysfs write: EtherHardware currently has no verified haptic API.

    def audio_result(self, status):
        self.audio_status = status; self.Changed()

    def owner_changed(self, name, old, new):
        if old and not new:
            affected = any(r['owner'] == str(old) for r in self.engine.rows.values())
            self.engine.owner_lost(str(old))
            if str(old) == self.ui_owner:
                self.ui_locked = True; self.engine.locked = True; self.ui_owner = ''; self.Changed()
            elif affected: self.Changed()

    def read_lock(self, path):
        try:
            props = dbus.Interface(self.system.get_object('org.freedesktop.login1', path), 'org.freedesktop.DBus.Properties')
            self.external_locks[path] = bool(props.Get('org.freedesktop.login1.Session', 'LockedHint'))
        except dbus.DBusException:
            self.external_locks[path] = True
        self.engine.locked = self.ui_locked or any(self.external_locks.values())

    def lock_properties(self, interface, changed, invalidated, path=None):
        if str(interface) != 'org.freedesktop.login1.Session' or str(path) not in self.external_locks: return
        if 'LockedHint' in changed:
            self.external_locks[str(path)] = bool(changed['LockedHint'])
            self.engine.locked = self.ui_locked or any(self.external_locks.values()); self.Changed()
        elif 'LockedHint' in invalidated:
            self.read_lock(str(path)); self.Changed()

    def lock_requested(self, path=None):
        if str(path) in self.external_locks:
            self.external_locks[str(path)] = True; self.engine.locked = True; self.Changed()

    def unlock_requested(self, path=None):
        if str(path) in self.external_locks:
            self.read_lock(str(path)); self.Changed()

    def sleep(self, sleeping):
        self.logind_sleeping = bool(sleeping)
        self.engine.sleeping = bool(sleeping)
        if sleeping: self.ui_locked = True; self.engine.locked = True
        else: self.engine.expire()
        # Resume refreshes cards, never replays transient banners or sounds.
        self.flush()

    def power_state(self, document):
        try:
            data = json.loads(str(document))
            self.engine.low_battery = data.get('profileState', {}).get('effective') == 'power-saver'
        except (ValueError, TypeError): pass

    def power_notice(self, title, body):
        try:
            # Signal owner is verified by the system bus match rule above.
            kind = str(body).split(':', 1)[0][:80]
            category = 'system.power.' + kind
            priority = 3 if kind == 'BatteryEmergency' else 2 if kind in ('BatteryCritical', 'ThermalWarning') else 1
            replaces = next((r['id'] for r in self.engine.rows.values() if r['appId']=='etherpower' and r['category']==category and r['active']), 0)
            # Restored system records are owned by this daemon, never a session app.
            if replaces: self.engine.rows[replaces]['owner']='system:etherpower'
            ident, delivery = self.engine.notify('system:etherpower', 'etherpower', 'EtherPower', replaces, 'battery-caution', str(title), str(body), [],
                {'urgency': 1, 'x-ether-priority': priority, 'resident': True, 'category': category, 'x-ether-privacy': 'public'}, 0, True)
            self.flush()
            if delivery: self.deliver(ident, delivery)
        except Invalid: pass


def main():
    os.umask(0o077)
    DBusGMainLoop(set_as_default=True)
    bus = dbus.SessionBus()
    try: service = Service(bus)
    except dbus.exceptions.NameExistsException:
        logging.error('Notification name is already owned; refusing to compete with the existing daemon')
        return 73
    loop = GLib.MainLoop()
    for sig in (signal.SIGTERM, signal.SIGINT):
        GLib.unix_signal_add(GLib.PRIORITY_DEFAULT, sig, lambda: (loop.quit(), False)[1])
    loop.run()
    service.engine.db.close()
    return 0


if __name__ == '__main__': sys.exit(main())
