#!/usr/bin/python3
"""Read cached, non-sensitive EtherFingerprint diagnostics."""
import json
import dbus

bus = dbus.SystemBus()
api = dbus.Interface(bus.get_object('com.etherneco.EtherFingerprint1',
    '/com/etherneco/EtherFingerprint1'), 'com.etherneco.EtherFingerprint1')
print(json.dumps(json.loads(str(api.GetState(timeout=5))), indent=2))
