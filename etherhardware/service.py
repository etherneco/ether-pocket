#!/usr/bin/python3
"""Cache-only system API; one worker, targeted coalesced hardware events, no timer polling."""
import json
import logging
import os
import signal
import socket
import struct
import time
from concurrent.futures import ThreadPoolExecutor
import dbus
import dbus.service
from dbus.mainloop.glib import DBusGMainLoop
from gi.repository import GLib
from core import CATEGORIES, Inventory, Registry
from backends import Backends

NAME = 'com.etherneco.EtherHardware1'
PATH = '/com/etherneco/EtherHardware1'
SUBSYSTEMS = {'usb': 'usb', 'udc': 'usb', 'typec': 'usb', 'dual_role_usb': 'usb',
    'net': 'wireless', 'bluetooth': 'wireless', 'ieee80211': 'wireless', 'rfkill': 'wireless',
    'drm': 'display', 'input': 'display', 'backlight': 'display', 'power_supply': 'power',
    'sound': 'audio', 'video4linux': 'camera', 'media': 'camera', 'iio': 'sensors', 'block': 'storage'}


class Service(dbus.service.Object):
    def __init__(self, bus, directory='/var/lib/etherhardware'):
        super().__init__(dbus.service.BusName(NAME, bus), PATH)
        self.bus = bus
        self.directory = directory
        self.pool = ThreadPoolExecutor(max_workers=1)
        self.registry = None
        self.data = {'schemaVersion': 1, 'available': True, 'ready': False, 'busy': True, 'components': [], 'capabilities': []}
        self.pending = False
        self.dirty = set()
        self.event_timer = 0
        self.explicit_after = 0
        self.last_diagnostic = 0
        self.requests = {}
        self.last_event_refresh = {}
        self.history_cache = []
        self.stopping = False
        self.share_signature = None
        for name, groups in [('org.freedesktop.NetworkManager', ('wireless', 'usb')),
                              ('org.bluez', ('wireless', 'audio')),
                              ('org.freedesktop.ModemManager1', ('cellular',)),
                              ('com.etherneco.EtherShare1', ('wireless', 'usb'))]:
            for sig, interface in [('PropertiesChanged', 'org.freedesktop.DBus.Properties'),
                                   ('InterfacesAdded', 'org.freedesktop.DBus.ObjectManager'),
                                   ('InterfacesRemoved', 'org.freedesktop.DBus.ObjectManager')]:
                callback = (lambda *a, g=groups: self.property_event(g, *a)) if sig == 'PropertiesChanged' else (lambda *a, g=groups: self.schedule(g))
                bus.add_signal_receiver(callback, signal_name=sig,
                    dbus_interface=interface, bus_name=name)
        bus.add_signal_receiver(self.share_event, signal_name='Changed',
                                dbus_interface='com.etherneco.EtherShare1', bus_name='com.etherneco.EtherShare1')
        bus.add_signal_receiver(self.owner_changed, signal_name='NameOwnerChanged', dbus_interface='org.freedesktop.DBus')
        bus.add_signal_receiver(lambda *a: self.schedule(('cellular',)), signal_name='PropertiesChanged',
            dbus_interface='org.freedesktop.DBus.Properties', bus_name='org.freedesktop.systemd1',
            path='/org/freedesktop/systemd1/unit/ethermobile_2ddata_2eservice')
        try:
            manager = dbus.Interface(bus.get_object('org.freedesktop.systemd1', '/org/freedesktop/systemd1', introspect=False), 'org.freedesktop.systemd1.Manager')
            manager.Subscribe(timeout=3)
        except dbus.DBusException:
            self.data['serviceEventWarning'] = 'Systemd events unavailable; use Refresh for data-owner state'
        try:
            self.netlink = socket.socket(socket.AF_NETLINK, socket.SOCK_DGRAM, 15)
            self.netlink.setblocking(False)
            self.netlink.bind((os.getpid(), 1))
            self.netlink.setsockopt(socket.SOL_SOCKET, socket.SO_PASSCRED, 1)
            GLib.io_add_watch(self.netlink.fileno(), GLib.IO_IN, self.uevent)
        except OSError:
            self.data['eventWarning'] = 'Kernel event subscription unavailable; use Refresh'
        self.work(tuple(CATEGORIES))

    def owner_changed(self, name, previous, owner):
        groups = {'org.freedesktop.NetworkManager': ('wireless', 'usb'), 'org.bluez': ('wireless', 'audio'),
                  'org.freedesktop.ModemManager1': ('cellular',), 'com.etherneco.EtherShare1': ('wireless', 'usb')}
        if str(name) in groups:
            self.schedule(groups[str(name)])

    def share_event(self, document):
        try:
            data = json.loads(str(document))
            signature = (str(data.get('radioWarning', '')), data.get('hotspotAvailable'),
                         json.dumps(data.get('active', []), sort_keys=True))
            if signature != self.share_signature:
                self.share_signature = signature
                self.schedule(('wireless', 'usb'))
        except (ValueError, TypeError):
            pass

    def property_event(self, groups, interface, changed, invalidated=()):
        # Signal strengths and throughput counters do not invalidate hardware.
        relevant = {'State', 'StateReason', 'Powered', 'Discovering', 'WirelessEnabled',
            'WirelessHardwareEnabled', 'ActiveAccessPoint', 'ActiveConnection', 'Sim',
            'UnlockRequired', 'RegistrationState', 'CurrentCapabilities', 'Connected',
            'UUIDs', 'Ports', 'Driver', 'WirelessCapabilities', 'Percentage', 'Online'}
        if relevant.intersection(str(k) for k in list(changed) + list(invalidated)):
            self.schedule(groups)

    def uevent(self, *args):
        # Only accept kernel-originated datagrams, never user-injected evidence.
        for _ in range(64):
            try:
                payload, anc, flags, address = self.netlink.recvmsg(8192, socket.CMSG_SPACE(12))
            except BlockingIOError:
                break
            if address[0] != 0:
                continue
            props = dict(s.split('=', 1) for s in payload.decode(errors='replace').split('\0') if '=' in s)
            group = SUBSYSTEMS.get(props.get('SUBSYSTEM'))
            if group:
                self.schedule((group,))
                if props.get('SUBSYSTEM') == 'net':
                    self.schedule(('usb', 'cellular'))
        return not self.stopping

    def schedule(self, groups):
        self.dirty.update(groups)
        if not self.event_timer:
            self.event_timer = GLib.timeout_add_seconds(3, self.flush)

    def flush(self):
        self.event_timer = 0
        if self.stopping:
            return False
        if self.pending:
            self.event_timer = GLib.timeout_add_seconds(3, self.flush)
        elif self.dirty:
            stamp = time.monotonic()
            groups = tuple(g for g in self.dirty if stamp - self.last_event_refresh.get(g, -100) >= (60 if g == 'power' else 10))
            if groups:
                self.dirty.difference_update(groups)
                self.last_event_refresh.update({g: stamp for g in groups})
                self.work(groups)
            if self.dirty:
                self.event_timer = GLib.timeout_add_seconds(10, self.flush)
        return False

    @dbus.service.signal(NAME, signature='s')
    def Changed(self, snapshot):
        pass

    @dbus.service.method(NAME, in_signature='', out_signature='s')
    def GetState(self):
        return json.dumps(self.data)

    @dbus.service.method(NAME, in_signature='', out_signature='s')
    def GetCapabilities(self):
        return json.dumps({'schemaVersion': 1, 'ready': self.data.get('ready', False), 'busy': self.pending,
                           'capabilities': self.data.get('capabilities', [])})

    @dbus.service.method(NAME, in_signature='s', out_signature='s')
    def GetCapability(self, identifier):
        return json.dumps(next((c for c in self.data.get('capabilities', []) if c['id'] == identifier), None))

    def rate_limit(self, sender):
        stamp = time.monotonic()
        self.requests = {k: v for k, v in self.requests.items() if stamp - v < 60}
        if stamp - self.requests.get(str(sender), -60) < 5 or stamp < self.explicit_after:
            raise dbus.exceptions.DBusException('Refresh is rate limited', name=NAME + '.Busy')
        self.requests[str(sender)] = stamp
        self.explicit_after = stamp + 5

    @dbus.service.method(NAME, in_signature='s', out_signature='', sender_keyword='sender')
    def Refresh(self, category, sender):
        if str(category) not in ('all', *CATEGORIES):
            raise dbus.exceptions.DBusException('Unknown category', name=NAME + '.Invalid')
        self.rate_limit(sender)
        self.schedule(tuple(CATEGORIES) if category == 'all' else (str(category),))

    @dbus.service.method(NAME, in_signature='s', out_signature='', sender_keyword='sender')
    def RunDiagnostics(self, category, sender):
        if str(category) not in ('all', *CATEGORIES):
            raise dbus.exceptions.DBusException('Unknown category', name=NAME + '.Invalid')
        self.rate_limit(sender)
        if self.pending or time.monotonic() - self.last_diagnostic < 30:
            raise dbus.exceptions.DBusException('Diagnostics busy; retry later', name=NAME + '.Busy')
        self.last_diagnostic = time.monotonic()
        self.work(tuple(CATEGORIES) if category == 'all' else (str(category),), True)

    @dbus.service.method(NAME, in_signature='ss', out_signature='s')
    def GetHistory(self, query, component):
        if len(query) > 128 or len(component) > 256:
            raise dbus.exceptions.DBusException('Filter too long', name=NAME + '.Invalid')
        return json.dumps([r for r in self.history_cache if str(query).lower() in
            (r['component'] + r['reason'] + r['current']).lower() and (not component or component == r['component'])][:200])

    @dbus.service.method(NAME, in_signature='s', out_signature='s')
    def ExportReport(self, format):
        if format not in ('json', 'text'):
            raise dbus.exceptions.DBusException('Unsupported format', name=NAME + '.Invalid')
        data = dict(self.data, history=self.history_cache)
        document = json.dumps(data, indent=2)
        return document if format == 'json' else 'EtherHardware support report (redacted)\n' + '\n'.join(
            r['title'] + ': ' + r['status'] + ' — ' + r['reason'] for r in data.get('components', [])) + '\n\n' + document

    @dbus.service.method(NAME, in_signature='', out_signature='', sender_keyword='sender', async_callbacks=('success', 'failure'))
    def ClearHistory(self, sender, success, failure):
        authority = dbus.Interface(self.bus.get_object('org.freedesktop.PolicyKit1', '/org/freedesktop/PolicyKit1/Authority'), 'org.freedesktop.PolicyKit1.Authority')
        def allowed(result):
            if not result[0]:
                failure(dbus.exceptions.DBusException('Authorization required', name=NAME + '.PermissionDenied'))
            elif self.pending:
                failure(dbus.exceptions.DBusException('Discovery busy; retry later', name=NAME + '.Busy'))
            else:
                self.work((), clear=True, success=success, failure=failure)
        authority.CheckAuthorization(('system-bus-name', {'name': dbus.String(sender, variant_level=1)}),
            'com.etherneco.etherhardware.clear-history', {}, dbus.UInt32(1), '',
            reply_handler=allowed, error_handler=failure, timeout=60)

    def work(self, groups, diagnostic=False, clear=False, success=None, failure=None):
        if self.pending or self.stopping:
            return
        self.pending = True
        self.data['busy'] = True
        self.Changed(json.dumps(self.data))
        def worker():
            error = False
            try:
                if self.registry is None:
                    self.registry = Registry(self.directory, Inventory(backend=Backends()))
                if clear:
                    self.registry.clear()
                    data = self.registry.snapshot()
                else:
                    data = self.registry.refresh(groups, diagnostic)
                history = self.registry.history(limit=1000)
            except Exception as e:
                logging.error('Hardware collection failed: %s', type(e).__name__)
                data = dict(self.data, ready=False, message='Hardware collection failed; evidence is stale')
                data['capabilities'] = []
                error, history = True, []
            def finish():
                self.data = dict(data, busy=False)
                self.history_cache = history
                self.pending = False
                self.Changed(json.dumps(self.data))
                if error and failure:
                    failure(dbus.exceptions.DBusException('Collection failed', name=NAME + '.Failed'))
                elif success:
                    success()
                return False
            GLib.idle_add(finish)
        self.pool.submit(worker)


if __name__ == '__main__':
    logging.basicConfig(level=logging.INFO)
    DBusGMainLoop(set_as_default=True)
    loop = GLib.MainLoop()
    service = Service(dbus.SystemBus())
    def stop(*args):
        service.stopping = True
        loop.quit()
    signal.signal(signal.SIGTERM, stop)
    signal.signal(signal.SIGINT, stop)
    loop.run()
    service.pool.shutdown(wait=True)
