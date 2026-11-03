import argparse
import dbus
import json
p = argparse.ArgumentParser(description='EtherLock state and manual lock; no unlock IPC')
p.add_argument('command', choices=['state', 'lock', 'events'])
a = p.parse_args()
bus = dbus.SessionBus()
api = dbus.Interface(bus.get_object('com.etherneco.EtherLock1', '/com/etherneco/EtherLock1'), 'com.etherneco.EtherLock1')
if a.command == 'lock':
    if not api.Lock('manual'): raise SystemExit('Lock enforcement not confirmed')
else: print(json.dumps(json.loads(api.GetState() if a.command == 'state' else api.ExportEvents()), indent=2))
