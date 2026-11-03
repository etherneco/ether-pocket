"""Single local session coordinator; XSecureLock owns authentication/enforcement."""
import ctypes
import ctypes.util
import json
import os
import pathlib
import select
import subprocess
import time
import dbus
import dbus.service
from dbus.mainloop.glib import DBusGMainLoop
from gi.repository import GLib
from core import DEFAULTS, LockState, Events, accepted, validation, policy, locker_environment

NAME = 'com.etherneco.EtherLock1'
PATH = '/com/etherneco/EtherLock1'


class Idle:
    class Info(ctypes.Structure):
        _fields_ = [('window', ctypes.c_ulong), ('state', ctypes.c_int), ('kind', ctypes.c_int),
                    ('since', ctypes.c_ulong), ('idle', ctypes.c_ulong), ('mask', ctypes.c_ulong)]

    def __init__(self):
        self.x = ctypes.CDLL(ctypes.util.find_library('X11'))
        self.ss = ctypes.CDLL(ctypes.util.find_library('Xss'))
        self.x.XOpenDisplay.argtypes = [ctypes.c_char_p]; self.x.XOpenDisplay.restype = ctypes.c_void_p
        self.x.XDefaultRootWindow.argtypes = [ctypes.c_void_p]; self.x.XDefaultRootWindow.restype = ctypes.c_ulong
        self.x.XScreenCount.argtypes = [ctypes.c_void_p]; self.x.XScreenCount.restype = ctypes.c_int
        self.ss.XScreenSaverQueryInfo.argtypes = [ctypes.c_void_p, ctypes.c_ulong, ctypes.POINTER(self.Info)]
        self.display = self.x.XOpenDisplay(None)
        if not self.display: raise RuntimeError('X11 display unavailable')
        if self.x.XScreenCount(self.display) != 1: raise RuntimeError('Multiple X11 roots are unsupported; refusing partial coverage')
        self.root = self.x.XDefaultRootWindow(self.display)

    def seconds(self):
        info = self.Info()
        if not self.ss.XScreenSaverQueryInfo(self.display, self.root, ctypes.byref(info)):
            raise RuntimeError('X11 idle query failed')
        return info.idle / 1000


class Service(dbus.service.Object):
    def __init__(self):
        self.bus = dbus.SessionBus(); self.system = dbus.SystemBus()
        self.name = dbus.service.BusName(NAME, self.bus, do_not_queue=True)
        super().__init__(self.bus, PATH)
        self.runtime = pathlib.Path(os.environ['XDG_RUNTIME_DIR']) / 'etherlock-active'
        existing = subprocess.run(['/usr/bin/pgrep', '-u', str(os.getuid()), '-x', 'xsecurelock'], capture_output=True).returncode == 0
        self.state = LockState(self.runtime.exists() or existing)
        self.events = Events(pathlib.Path.home() / '.local/share/etherlock')
        self.config_path = pathlib.Path.home() / '.config/etherlock/policy.json'
        try: self.config = policy(DEFAULTS, json.loads(self.config_path.read_text()), True)
        except (OSError, ValueError): self.config = dict(DEFAULTS)
        self.child = None; self.error = ''; self.block = None; self.idle = Idle()
        self.manager = dbus.Interface(self.system.get_object('org.freedesktop.login1', '/org/freedesktop/login1'), 'org.freedesktop.login1.Manager')
        # Find the active graphical session by display and uid; user services have no XDG_SESSION_ID.
        sessions = [row for row in self.manager.ListSessions() if int(row[1]) == os.getuid() and str(row[3])]
        if len(sessions) != 1: raise RuntimeError('Ambiguous local graphical session')
        self.session_path = str(sessions[0][4])
        self.session = dbus.Interface(self.system.get_object('org.freedesktop.login1', self.session_path), 'org.freedesktop.login1.Session')
        self.system.add_signal_receiver(self.session_lock, signal_name='Lock', dbus_interface='org.freedesktop.login1.Session',
                                        bus_name='org.freedesktop.login1', path=self.session_path)
        self.system.add_signal_receiver(self.sleep, signal_name='PrepareForSleep', dbus_interface='org.freedesktop.login1.Manager',
                                        bus_name='org.freedesktop.login1', path='/org/freedesktop/login1')
        GLib.timeout_add(200, self.tick)

    def own(self, sender):
        if int(self.bus.get_unix_user(sender)) != os.getuid():
            raise dbus.exceptions.DBusException('Wrong session owner', name=NAME+'.Denied')

    def enabled(self): return self.config['enabled'] and accepted(validation())

    def snapshot(self):
        return dict(ready=True, phase=self.state.phase, locked=self.state.private, enforced=self.state.enforced,
                    enabled=self.enabled(), validated=accepted(validation()), config=self.config,
                    error=self.error, backend='XSecureLock + PAM authenticate/account',
                    pin='Linux credential only; separate PIN unavailable', biometrics=False, emergency=False,
                    suspend='Blocked while policy is enabled; hardware resume acceptance outstanding',
                    encryption='Unencrypted ext4; screen locking does not protect offline data',
                    remote='SSH sessions are preserved; local screen locking is a separate control')

    @dbus.service.signal(NAME, signature='s')
    def Changed(self, document): pass

    def changed(self): self.Changed(json.dumps(self.snapshot()))

    @dbus.service.method(NAME, in_signature='', out_signature='s', sender_keyword='sender')
    def GetState(self, sender):
        self.own(sender); return json.dumps(self.snapshot())

    @dbus.service.method(NAME, in_signature='s', out_signature='s', sender_keyword='sender')
    def Configure(self, document, sender):
        self.own(sender)
        if len(document) > 2048: raise ValueError('Policy too large')
        updated = policy(self.config, json.loads(document), accepted(validation()))
        if updated['enabled'] and self.block is None:
            self.block = self.manager.Inhibit('sleep', 'EtherLock', 'Suspend security acceptance pending', 'block').take()
        self.config = updated
        self.config_path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
        temp = self.config_path.with_suffix('.new')
        temp.write_text(json.dumps(self.config)); temp.chmod(0o600); temp.replace(self.config_path)
        self.events.add('policy-changed'); self.changed(); return json.dumps(self.snapshot())

    @dbus.service.method(NAME, in_signature='s', out_signature='b', sender_keyword='sender')
    def Lock(self, reason, sender):
        self.own(sender); return self.lock()

    @dbus.service.method(NAME, in_signature='', out_signature='s', sender_keyword='sender')
    def ExportEvents(self, sender):
        self.own(sender); return json.dumps(self.events.export())

    def lock(self):
        if self.state.enforced: return True
        if not validation().get('recovery'): self.error = 'Verify independent recovery for this boot/build first'; self.changed(); return False
        if self.state.phase != 'unlocked': return False
        self.state.request(); self.runtime.touch(mode=0o600); self.changed()
        try:
            self.child = subprocess.Popen(['/usr/bin/xsecurelock', '--', '/usr/bin/printf', 'ETHERLOCK_READY\\n'],
                env=locker_environment(os.environ), stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, start_new_session=True)
            # A mapped Qt surface or running process is never an enforcement acknowledgement.
            ready, _, _ = select.select([self.child.stdout], [], [], 5)
            if ready and self.child.stdout.readline(128) == b'ETHERLOCK_READY\n' and self.child.poll() is None:
                self.state.ready()
                try: self.session.SetLockedHint(True)
                except dbus.DBusException: self.error = 'Enforced, but logind hint could not be updated'
                self.events.add('locked'); self.changed(); return True
            self.error = 'Locker did not confirm input capture and coverage; no screen-off/suspend permission'
        except (OSError, dbus.DBusException): self.error = 'Lock enforcement unavailable; independent recovery required'
        self.state.phase = 'fault'; self.state.private = True; self.events.add('lock-failed'); self.changed(); return False

    def tick(self):
        try: return self.tick_checked()
        except (dbus.DBusException, OSError, RuntimeError):
            self.error = 'Session/power coordination failed; protection requires administrator recovery'
            self.state.phase = 'fault'; self.state.private = True; self.changed(); return True

    def tick_checked(self):
        if self.child and self.child.poll() is not None:
            success = self.state.exited(self.child.returncode); self.child = None
            if success:
                self.runtime.unlink(missing_ok=True); self.session.SetLockedHint(False); self.events.add('unlocked')
            else:
                self.error = 'Locker exited unexpectedly. Protection is unknown; use administrator recovery.'; self.events.add('recovery-required')
            self.changed()
        if self.enabled():
            # A delay inhibitor alone expires even if locking failed. Keep a block
            # until real suspend/wake acceptance exists; never pretend delay is veto.
            if self.block is None:
                self.block = self.manager.Inhibit('sleep', 'EtherLock', 'Suspend security acceptance pending', 'block').take()
            if self.state.phase == 'unlocked' and self.idle.seconds() >= self.config['timeout']: self.lock()
        # Never release an existing suspend block while protection is uncertain.
        elif self.block is not None and self.state.phase == 'unlocked':
            os.close(self.block); self.block = None
        return True

    def session_lock(self): self.lock()
    def sleep(self, sleeping):
        if self.enabled(): self.lock()


if __name__ == '__main__':
    if os.getuid() == 0: raise SystemExit('Run as the graphical session user')
    os.umask(0o077)
    DBusGMainLoop(set_as_default=True); service = Service(); GLib.MainLoop().run()
