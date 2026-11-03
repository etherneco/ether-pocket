#!/usr/bin/python3
"""Public non-sensitive diagnostic snapshot; no authentication result interface."""
import json
import signal
import dbus
import dbus.service
from dbus.mainloop.glib import DBusGMainLoop
from gi.repository import GLib
from core import DiagnosticProvider

NAME = 'com.etherneco.EtherFingerprint1'
PATH = '/com/etherneco/EtherFingerprint1'


class Service(dbus.service.Object):
    def __init__(self, bus):
        self.name = dbus.service.BusName(NAME, bus, do_not_queue=True)
        super().__init__(bus, PATH)
        self.provider = DiagnosticProvider()
        self.data = json.dumps(self.provider.status())

    @dbus.service.method(NAME, in_signature='', out_signature='s')
    def GetState(self):
        return self.data

    @dbus.service.method(NAME, in_signature='', out_signature='s')
    def GetCapabilities(self):
        return self.data


if __name__ == '__main__':
    DBusGMainLoop(set_as_default=True)
    service = Service(dbus.SystemBus())
    loop = GLib.MainLoop()
    for sig in (signal.SIGTERM, signal.SIGINT):
        GLib.unix_signal_add(GLib.PRIORITY_DEFAULT, sig, lambda: (service.provider.cancel(), loop.quit(), False)[-1])
    loop.run()
