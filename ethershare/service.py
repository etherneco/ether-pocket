#!/usr/bin/python3
"""System D-Bus API, PolicyKit authorization, one serialized network worker."""
import json
import logging
import os
import signal
import sys
import threading
import time
from concurrent.futures import ThreadPoolExecutor

import dbus
import dbus.service
from dbus.mainloop.glib import DBusGMainLoop
from gi.repository import GLib

from core import LinuxShare, ShareError
from nm import NetworkManager

NAME = 'com.etherneco.EtherShare1'
PATH = '/com/etherneco/EtherShare1'
ACTION = 'com.etherneco.ethershare.manage'


class Service(dbus.service.Object):
    def __init__(self, bus):
        super().__init__(dbus.service.BusName(NAME, bus), PATH)
        self.bus = bus
        self.pool = ThreadPoolExecutor(max_workers=1, thread_name_prefix='network')
        self.pending = False
        self.queued = False
        self.stopping = False
        self.data = {'available': True, 'ready': False, 'busy': True, 'active': [], 'interfaces': [], 'clients': [], 'message': 'Reading network state'}
        self.core = None
        self.last_notice = ''
        self.perform(self.initialize)
        GLib.timeout_add_seconds(5, self.tick)
        bus.add_signal_receiver(self.network_event, signal_name='PropertiesChanged', dbus_interface='org.freedesktop.DBus.Properties', bus_name='org.freedesktop.NetworkManager')
        bus.add_signal_receiver(self.network_event, signal_name='PrepareForSleep', dbus_interface='org.freedesktop.login1.Manager', bus_name='org.freedesktop.login1')

    def initialize(self):
        self.core = LinuxShare(NetworkManager())
        self.core.recover()
        # Persisted preferences do not implicitly restart sharing.
        # Explicit autostart is limited to USB and is still capability checked.
        if self.core.config['autostart']:
            rows, _ = self.core.discover()
            usb = next((x for x in rows if x['kind'] == 'usb'), None)
            if usb:
                self.core.start('usb', usb['interface'])

    @dbus.service.signal(NAME, signature='s')
    def Changed(self, snapshot):
        pass

    @dbus.service.signal(NAME, signature='ss')
    def Notice(self, title, message):
        pass

    @dbus.service.method(NAME, in_signature='', out_signature='s')
    def GetState(self):
        return json.dumps(self.data)

    def authorize(self, sender, success, failure, fn):
        if self.stopping or self.queued:
            failure(dbus.exceptions.DBusException('Another sharing operation is running', name=NAME + '.Busy'))
            return
        if self.pending:
            # A bounded monitor/probe must not make a user's Stop unreliable.
            # Reserve one foreground request; event refreshes yield to it.
            self.queued = True
            deadline = time.monotonic()+35
            def retry():
                if self.stopping or time.monotonic()>deadline:
                    self.queued=False
                    failure(dbus.exceptions.DBusException('Sharing operation timed out',name=NAME+'.Busy'))
                    return False
                if self.pending:
                    return True
                self.queued=False
                self.authorize(sender,success,failure,fn)
                return False
            GLib.timeout_add(100,retry)
            return
        self.pending = True
        authority = dbus.Interface(self.bus.get_object('org.freedesktop.PolicyKit1', '/org/freedesktop/PolicyKit1/Authority'), 'org.freedesktop.PolicyKit1.Authority')
        subject = ('system-bus-name', {'name': dbus.String(sender, variant_level=1)})
        def allowed(result):
            self.pending = False
            if not result[0]:
                failure(dbus.exceptions.DBusException('Authorization required', name=NAME + '.PermissionDenied'))
                return
            self.perform(fn, success, failure)
        def denied(error):
            self.pending = False
            failure(dbus.exceptions.DBusException('Authorization unavailable', name=NAME + '.PermissionDenied'))
        authority.CheckAuthorization(subject, ACTION, {}, dbus.UInt32(1), '', reply_handler=allowed, error_handler=denied, timeout=60)

    @dbus.service.method(NAME, in_signature='ssb', out_signature='', sender_keyword='sender', async_callbacks=('success','failure'))
    def Start(self, method, interface, replaceWifi, sender, success, failure):
        self.authorize(sender, success, failure, lambda: self.core.start(str(method), str(interface), bool(replaceWifi)))

    @dbus.service.method(NAME, in_signature='s', out_signature='', sender_keyword='sender', async_callbacks=('success','failure'))
    def StartConcurrentHotspot(self, parent, sender, success, failure):
        self.authorize(sender, success, failure, lambda: self.core.start_concurrent_hotspot(str(parent)))

    @dbus.service.method(NAME, in_signature='s', out_signature='', sender_keyword='sender', async_callbacks=('success','failure'))
    def Stop(self, method, sender, success, failure):
        def stop():
            for key in list(self.core.active) if str(method) == 'all' else [str(method)]:
                self.core.stop(key)
        self.authorize(sender, success, failure, stop)

    @dbus.service.method(NAME, in_signature='s', out_signature='', sender_keyword='sender', async_callbacks=('success','failure'))
    def Configure(self, document, sender, success, failure):
        if len(document) > 4096:
            failure(dbus.exceptions.DBusException('Configuration too large', name=NAME + '.Invalid'))
            return
        self.authorize(sender, success, failure, lambda: self.core.save(json.loads(document)))

    @dbus.service.method(NAME, in_signature='', out_signature='', sender_keyword='sender', async_callbacks=('success','failure'))
    def Refresh(self, sender, success, failure):
        # Explicit connectivity probes are authorized; GetState is cache-only.
        def refresh():
            self.core.refresh_sources()
        self.authorize(sender, success, failure, refresh)

    @dbus.service.method(NAME, in_signature='', out_signature='s', sender_keyword='sender', async_callbacks=('success','failure'))
    def RevealHotspotPassword(self, sender, success, failure):
        self.authorize(sender, lambda: success(self.core.config['password']), failure, lambda: None)

    @dbus.service.method(NAME, in_signature='ss', out_signature='', sender_keyword='sender', async_callbacks=('success','failure'))
    def RenameClient(self, mac, name, sender, success, failure):
        self.authorize(sender, success, failure, lambda: self.core.rename_client(str(mac),str(name)))

    def network_event(self, *args, **kw):
        if not self.pending and not self.queued:
            self.perform(lambda: self.core.monitor() if self.core else None)

    def tick(self):
        if not self.pending and not self.queued and not self.stopping and self.core:
            if self.core.active or int(time.monotonic()) % 30 < 5:
                self.perform(self.core.monitor)
        return not self.stopping

    def perform(self, operation, success=None, failure=None):
        if self.pending:
            return
        self.pending = True
        self.data['busy'] = True
        self.Changed(json.dumps(self.data))
        def worker():
            error = None
            try:
                operation()
            except ShareError as e:
                error = str(e)
            except Exception as e:
                # Do not log arbitrary D-Bus exception strings or NM settings.
                logging.error('Network operation failed: %s', type(e).__name__)
                error = 'Network operation failed. Inspect capability diagnostics and current connection.'
            try:
                data = self.core.snapshot() if self.core else dict(self.data)
                data.update(available=True, ready=bool(self.core), busy=False)
            except Exception as e:
                data = dict(self.data, busy=False, ready=False, message='Network inventory unavailable')
                error = error or 'NetworkManager is unavailable; sharing guards remain installed'
            if error:
                data['message'] = error
            events = list(self.core.events) if self.core else []
            if self.core:
                self.core.events.clear()
            def finish():
                self.pending = False
                self.data = data
                self.Changed(json.dumps(data))
                for title,text in events:
                    self.Notice(title,text)
                message = data.get('message', '')
                if message and message != self.last_notice:
                    self.last_notice = message
                    self.Notice('Internet Sharing', message)
                if error and failure:
                    failure(dbus.exceptions.DBusException(error, name=NAME + '.OperationFailed'))
                elif success:
                    success()
            GLib.idle_add(finish)
        self.pool.submit(worker)

    def shutdown(self):
        self.stopping = True
        def clean():
            if self.core:
                for method in list(self.core.active):
                    try:
                        self.core.stop(method)
                    except Exception:
                        logging.error('Cleanup retained in recovery journal')
            GLib.idle_add(loop.quit)
        self.pool.submit(clean)


if __name__ == '__main__':
    if os.geteuid() != 0:
        sys.exit('The network service requires system privileges; the GUI must run as a user')
    logging.basicConfig(level=logging.INFO)
    DBusGMainLoop(set_as_default=True)
    bus = dbus.SystemBus()
    loop = GLib.MainLoop()
    service = Service(bus)
    GLib.unix_signal_add(GLib.PRIORITY_DEFAULT, signal.SIGTERM, lambda: service.shutdown() or False)
    GLib.unix_signal_add(GLib.PRIORITY_DEFAULT, signal.SIGINT, lambda: service.shutdown() or False)
    loop.run()
