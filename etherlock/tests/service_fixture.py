"""Real D-Bus protocol test on private bus; no login1 or display mutations."""
import json
import os
import pathlib
import subprocess
import sys
import tempfile
import time
import dbus
import dbus.service
from dbus.mainloop.glib import DBusGMainLoop
from gi.repository import GLib
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))


def fake_logind():
    DBusGMainLoop(set_as_default=True)
    bus = dbus.SessionBus()
    name = dbus.service.BusName('org.freedesktop.login1', bus)

    class Manager(dbus.service.Object):
        @dbus.service.method('org.freedesktop.login1.Manager', out_signature='a(susso)')
        def ListSessions(self): return [('fixture', os.getuid(), 'fixture', 'seat0', '/org/freedesktop/login1/session/fixture')]
    manager = Manager(bus, '/org/freedesktop/login1')
    GLib.MainLoop().run()


if len(sys.argv) > 1 and sys.argv[1] == '--logind':
    fake_logind()
elif len(sys.argv) > 1 and sys.argv[1] == '--service':
    import service
    class Idle:
        def seconds(self): return 0
    service.Idle = Idle
    DBusGMainLoop(set_as_default=True)
    instance = service.Service()
    GLib.MainLoop().run()
else:
    assert os.getuid() != 0, 'Run fixture as an unprivileged user under dbus-run-session'
    assert not pathlib.Path('/etc/etherlock/validation.json').exists(), 'Do not run against an attested host'
    env = dict(os.environ, DBUS_SYSTEM_BUS_ADDRESS=os.environ['DBUS_SESSION_BUS_ADDRESS'])
    with tempfile.TemporaryDirectory(prefix='etherlock-protocol-') as folder:
        pathlib.Path(folder, 'runtime').mkdir(mode=0o700)
        env.update(HOME=folder, XDG_RUNTIME_DIR=folder+'/runtime')
        logind = subprocess.Popen([sys.executable, __file__, '--logind'], env=env)
        backend = None
        try:
            bus = dbus.SessionBus()
            for _ in range(40):
                if bus.name_has_owner('org.freedesktop.login1'): break
                time.sleep(.05)
            backend = subprocess.Popen([sys.executable, __file__, '--service'], env=env)
            for _ in range(50):
                if bus.name_has_owner('com.etherneco.EtherLock1'): break
                time.sleep(.05)
            obj = bus.get_object('com.etherneco.EtherLock1', '/com/etherneco/EtherLock1')
            api = dbus.Interface(obj, 'com.etherneco.EtherLock1')
            initial = json.loads(api.GetState())
            assert initial['phase'] == 'unlocked' and not initial['enabled'] and not initial['enforced']
            assert not api.Lock('manual'), 'Missing recovery evidence must block locking'
            assert json.loads(api.GetState())['phase'] == 'unlocked'
            try: api.Configure('{"enabled":true}')
            except dbus.DBusException: pass
            else: raise AssertionError('Enable bypassed acceptance')
            changed = json.loads(api.Configure('{"timeout":30}'))
            assert changed['config']['timeout'] == 30 and not changed['enabled']
            xml = dbus.Interface(obj, 'org.freedesktop.DBus.Introspectable').Introspect()
            assert 'name="Unlock"' not in xml and 'name="Authenticate"' not in xml
            assert all(set(row) == {'timestamp', 'event'} for row in json.loads(api.ExportEvents()))
            backend.terminate(); backend.wait(timeout=5)
            pathlib.Path(folder, 'runtime/etherlock-active').touch()
            backend = subprocess.Popen([sys.executable, __file__, '--service'], env=env)
            for _ in range(50):
                if bus.name_has_owner('com.etherneco.EtherLock1'): break
                time.sleep(.05)
            obj = bus.get_object('com.etherneco.EtherLock1', '/com/etherneco/EtherLock1')
            api = dbus.Interface(obj, 'com.etherneco.EtherLock1')
            restarted = json.loads(api.GetState())
            assert restarted['phase'] == 'unknown' and restarted['locked'] and not restarted['enforced']
            assert restarted['config']['timeout'] == 30
            print(json.dumps(dict(initialDisabled=True, noEvidenceNoLock=True, enableGate=True,
                policyPersists=True, noUnlockIPC=True, redactedEvents=True, interruptedRestartPrivate=True)))
        finally:
            if backend: backend.terminate(); backend.wait(timeout=5)
            logind.terminate(); logind.wait(timeout=5)
