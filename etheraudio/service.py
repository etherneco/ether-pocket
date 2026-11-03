#!/usr/bin/python3
"""Unprivileged session policy service; leaves PipeWire/WirePlumber as owners."""
import array
import json
import logging
import math
import os
from pathlib import Path
import signal
import struct
import subprocess
import sys
import tempfile
import time
import uuid
import wave
from concurrent.futures import ThreadPoolExecutor
sys.path.insert(0, str(Path(__file__).resolve().parent))
import dbus
import dbus.service
from dbus.mainloop.glib import DBusGMainLoop
from gi.repository import GLib
from core import Audio, AudioError, is_monitor

NAME = 'com.etherneco.EtherAudio1'
PATH = '/com/etherneco/EtherAudio1'


class Service(dbus.service.Object):
    def __init__(self, bus):
        super().__init__(dbus.service.BusName(NAME, bus), PATH)
        self.bus = bus
        self.core = Audio(Path(os.environ.get('XDG_CONFIG_HOME', str(Path.home()/'.config')))/'etheraudio')
        self.pool = ThreadPoolExecutor(max_workers=1)
        self.busy = False
        self.dirty = False
        self.timer = 0
        self.captures = {}
        self.state = {'ready':False,'message':'Reading existing audio server'}
        self.dead_owners = set()
        self.sleep_requested = None
        self.registry = {}
        self.registry_stamp = 0
        self.hardware_bus = None
        bus.add_signal_receiver(self.owner_changed, signal_name='NameOwnerChanged', dbus_interface='org.freedesktop.DBus')
        system = dbus.SystemBus()
        system.add_signal_receiver(self.power_event, signal_name='Event', dbus_interface='com.etherneco.EtherPower1', bus_name='com.etherneco.EtherPower1')
        system.add_signal_receiver(self.sleep, signal_name='PrepareForSleep', dbus_interface='org.freedesktop.login1.Manager', bus_name='org.freedesktop.login1')
        self.subscription = None
        self.start_subscription()
        GLib.timeout_add_seconds(60, self.fallback)
        GLib.timeout_add_seconds(1, self.capture_tick)
        self.work()

    @dbus.service.signal(NAME, signature='s')
    def Changed(self, state): pass

    @dbus.service.signal(NAME, signature='ss')
    def Event(self, kind, document): pass

    @dbus.service.method(NAME, in_signature='', out_signature='s')
    def GetState(self): return json.dumps(self.state)

    @dbus.service.method(NAME, in_signature='', out_signature='')
    def Refresh(self): self.schedule()

    def publish(self):
        self.state['busy'] = self.busy
        self.state['managedCaptures'] = [dict(id=k,application=v['application'],source=v['source'],expires=v['expires']) for k,v in self.captures.items()]
        self.Changed(json.dumps(self.state))

    def work(self, operation=None, success=None, failure=None):
        if self.busy:
            if failure: failure(dbus.exceptions.DBusException('Audio service busy; retry shortly', name=NAME+'.Busy'))
            else: self.dirty = True
            return
        self.busy = True
        self.publish()
        def worker():
            result = ''
            error = None
            try:
                if self.sleep_requested is not None:
                    self.core.suspended = self.sleep_requested
                    self.sleep_requested = None
                    if self.core.suspended:
                        self.core.focus.clear()
                for owner in list(self.dead_owners):
                    self.core.release_focus(owner)
                    self.dead_owners.discard(owner)
                if operation: result = operation()
                data = self.core.refresh()
                if time.monotonic()-self.registry_stamp>60:
                    try:
                        if self.hardware_bus is None:self.hardware_bus=dbus.SystemBus(private=True)
                        api=dbus.Interface(self.hardware_bus.get_object('com.etherneco.EtherHardware1','/com/etherneco/EtherHardware1',introspect=False),'com.etherneco.EtherHardware1')
                        registry=json.loads(str(api.GetCapabilities(timeout=4)))
                        self.registry={'ready':bool(registry.get('ready')),'capabilities':[c for c in registry.get('capabilities',[]) if c['id'].startswith('audio.')]}
                    except (dbus.DBusException,ValueError):self.registry={'ready':False,'error':'EtherHardware capability registry unavailable'}
                    self.registry_stamp=time.monotonic()
                data['hardwareRegistry']=self.registry
                data['backendDiagnostics']=self.diagnostics()
            except Exception as e:
                logging.exception('Audio operation failed')
                error = str(e) if isinstance(e, AudioError) else 'Audio operation failed; see user journal'
                data = dict(self.core.state, message=error)
                # A disconnected backend must never leave stale operational evidence.
                if operation is None: data['ready'] = False
            def finish():
                previous_recording=self.state.get('recording')
                previous_focus=self.state.get('focus')
                self.state = data
                self.busy = False
                self.publish()
                if previous_recording!=data.get('recording'):
                    self.Event('MicrophoneActivity',json.dumps({'recording':bool(data.get('recording')),'streams':data.get('recordingStreams',[])}))
                if previous_focus is not None and previous_focus!=data.get('focus'):
                    self.focus_event()
                if error and failure: failure(dbus.exceptions.DBusException(error, name=NAME+'.Failed'))
                elif success: success(str(result) if result is not None else '')
                if self.dirty:
                    self.dirty = False
                    self.schedule()
                return False
            GLib.idle_add(finish)
        self.pool.submit(worker)

    @dbus.service.method(NAME, in_signature='sss', out_signature='s', sender_keyword='sender', async_callbacks=('success','failure'))
    def Command(self, action, target, document, sender, success, failure):
        if len(document)>4096 or len(target)>512:
            failure(dbus.exceptions.DBusException('Request too large',name=NAME+'.Invalid'));return
        try:
            data = json.loads(str(document))
            if not isinstance(data,dict): raise AudioError('Command requires an object')
            def operation():
                if action == 'select': self.core.select(str(target), data['name'])
                elif action == 'volume': self.core.set_volume(str(target), data['id'], data['percent'])
                elif action == 'mute': self.core.mute(str(target), data['id'], data['muted'])
                elif action == 'move': self.core.move(data['stream'], data['sink'])
                elif action == 'category': self.core.set_category(str(target), data['percent'])
                elif action == 'card-profile': self.core.set_card_profile(str(target), data['profile'])
                elif action == 'configure': self.core.configure(data)
                elif action == 'focus':
                    token=self.core.request_focus(str(sender),str(target))
                    return token
                elif action == 'release-focus':
                    self.core.release_focus(str(sender),str(target))
                elif action == 'call-route': raise AudioError(self.state.get('callAudio',{}).get('error','Native modem voice route is not validated'))
                elif action == 'result': self.core.diagnostic_result(str(target),data['result'])
                elif action == 'play-test':
                    if data.get('consent') is not True: raise AudioError('Playback test requires explicit user interaction')
                    self.play_test(str(target))
                else: raise AudioError('Unknown audio command')
            self.work(operation,success,failure)
        except (ValueError,AudioError) as e:
            failure(dbus.exceptions.DBusException(str(e),name=NAME+'.Invalid'))

    def focus_event(self):
        requests=list(self.core.focus.values())
        self.Event('FocusChanged',json.dumps({'requests':requests,'action':'duck-or-pause-lower-priority' if requests else 'resume-eligible-streams','cooperative':True}))
        return False

    @dbus.service.method(NAME, in_signature='s', out_signature='', sender_keyword='sender', async_callbacks=('success','failure'))
    def PlayNotification(self, sound, sender, success, failure):
        """Bounded built-in cue through existing category/focus/output policy."""
        try:
            owner = self.bus.get_name_owner('org.freedesktop.Notifications')
            pid = int(self.bus.call_blocking('org.freedesktop.DBus','/org/freedesktop/DBus','org.freedesktop.DBus','GetConnectionUnixProcessID','s',(sender,)))
            args = (Path('/proc')/str(pid)/'cmdline').read_bytes().split(b'\0')
            source = Path('/usr/share/ethernotifications/service.py')
            entry = next((arg for arg in args[1:] if arg not in (b'-I',b'-s',b'-E',b'-B',b'-u')),b'')
            if str(sender) != owner or entry != os.fsencode(str(source)) or source.stat().st_uid != 0 or source.stat().st_mode & 0o022:
                raise AudioError('Notification playback is reserved for the installed notification policy service')
            if sound not in ('default','soft'): raise AudioError('Unknown notification cue')
            if time.monotonic()-getattr(self,'last_notification',0)<2: raise AudioError('Notification audio rate limited')
            self.last_notification = time.monotonic()
            def operation():
                self.core.state.update(self.core.backend.snapshot())
                if self.core.suspended or self.core.call_active(): return
                token = self.core.request_focus(str(sender),'notification')
                try:
                    with tempfile.TemporaryDirectory(prefix='etheraudio-notification-') as folder:
                        path = Path(folder)/'cue.wav'
                        frequency = 660 if sound=='default' else 440
                        with wave.open(str(path),'wb') as f:
                            f.setparams((1,2,24000,0,'NONE','not compressed'))
                            f.writeframes(b''.join(struct.pack('<h',int(1600*min(1,i/240,(4800-i)/480)*math.sin(2*math.pi*frequency*i/24000))) for i in range(4800)))
                        percent=self.core.config['categories']['notification']
                        p=subprocess.run(['paplay','--property=media.role=event','--property=application.name=EtherNotifications','--volume='+str(int(65536*percent/100)),str(path)],capture_output=True,timeout=4)
                        if p.returncode: raise AudioError('Notification cue playback failed')
                finally:
                    self.core.release_focus(str(sender),token)
            self.work(operation,success,failure)
        except (dbus.DBusException, OSError, AudioError) as e:
            failure(dbus.DBusException(str(e),name=NAME+'.Denied'))

    def diagnostics(self):
        # Cached alongside the capability inventory; metadata never opens a PCM.
        if hasattr(self,'diagnostic_cache') and time.monotonic()-self.diagnostic_stamp<60:return self.diagnostic_cache
        def read(path):
            try:return Path(path).read_text().strip()
            except OSError:return None
        p=subprocess.run(['systemctl','--user','is-active','pipewire','pipewire-pulse','wireplumber','pulseaudio'],capture_output=True,text=True,timeout=4)
        self.diagnostic_cache={'alsaCards':read('/proc/asound/cards'),'alsaPcm':read('/proc/asound/pcm'),
            'services':dict(zip(['pipewire','pipewire-pulse','wireplumber','pulseaudio'],p.stdout.splitlines())),
            'scope':'Read-only metadata; physical audio, call paths and external codecs need explicit endpoint tests'}
        self.diagnostic_stamp=time.monotonic();return self.diagnostic_cache

    @dbus.service.method(NAME,in_signature='i',out_signature='s',async_callbacks=('success','failure'))
    def AdjustVolume(self,delta,success,failure):
        if not -100<=int(delta)<=100:
            failure(dbus.exceptions.DBusException('Invalid volume step',name=NAME+'.Invalid'));return
        def operation():
            from core import category,volume
            self.core.state=self.core.backend.snapshot()
            calls=[r for r in self.core.state['sink-inputs'] if category(r)=='call' and not r.get('corked',False)]
            kind='sink-input' if calls else 'sink'
            row=calls[0] if calls else self.core.find('sink',self.core.state['default-sink'])
            percent=max(0,min(100,volume(row)+int(delta)))
            self.core.set_volume(kind,row['index'],percent)
            return json.dumps({'percent':percent,'target':'call' if calls else 'media'})
        self.work(operation,success,failure)

    def play_test(self, sink):
        self.core.find('sink',sink)
        if self.core.call_active(): raise AudioError('Playback test blocked during call')
        with tempfile.TemporaryDirectory(prefix='etheraudio-') as folder:
            path=Path(folder)/'tone.wav'
            with wave.open(str(path),'wb') as f:
                f.setparams((1,2,48000,0,'NONE','not compressed'))
                f.writeframes(b''.join(struct.pack('<h',int(900*math.sin(2*math.pi*440*i/48000))) for i in range(24000)))
            p=subprocess.run(['paplay','--device='+sink,str(path)],capture_output=True,timeout=8)
            if p.returncode: raise AudioError('Playback failed; check selected endpoint')
        self.core.diagnostic_result('playback','not-tested')

    @dbus.service.method(NAME,in_signature='ssbu',out_signature='sh',sender_keyword='sender')
    def StartCapture(self, source, purpose, consent, seconds, sender):
        # Consent is cooperative application policy, not a security boundary against
        # other same-UID clients. Direct Pulse/ALSA remains governed by Unix ACLs.
        if not consent or self.core.config['microphonePolicy']!='ask-each-time' or self.core.suspended or self.sleep_requested is True:
            raise dbus.exceptions.DBusException('Capture denied: explicit consent required or policy blocks capture',name=NAME+'.Denied')
        if not 1<=int(seconds)<=60 or len(purpose)>200 or len(self.captures)>=4 or not self.state.get('ready'):
            raise dbus.exceptions.DBusException('Invalid or unavailable capture request',name=NAME+'.Invalid')
        row=self.core.find('source',str(source))
        if is_monitor(row):raise dbus.exceptions.DBusException('Speaker monitor capture is disabled',name=NAME+'.Denied')
        # get_unix_user plus server-assigned PID gives actual peer identity; no
        # client-supplied application name is used for the activity indicator.
        pid=int(dbus.Interface(self.bus.get_object('org.freedesktop.DBus','/org/freedesktop/DBus'),'org.freedesktop.DBus').GetConnectionUnixProcessID(sender))
        try: application=Path('/proc',str(pid),'comm').read_text().strip()
        except OSError: application='Unknown client'
        process=subprocess.Popen(['parec','--raw','--format=s16le','--rate=16000','--channels=1','--latency-msec=60','--process-time-msec=20','--device='+row['name'],'--property=application.name=EtherAudio managed capture'],stdout=subprocess.PIPE,stderr=subprocess.DEVNULL)
        token=uuid.uuid4().hex
        self.captures[token]=dict(process=process,owner=str(sender),application=application,source=row['name'],expires=time.monotonic()+int(seconds))
        self.publish();self.Event('CaptureStarted',json.dumps({'application':application,'source':row['name']}));self.schedule()
        return token, dbus.types.UnixFd(process.stdout.fileno())

    @dbus.service.method(NAME,in_signature='s',out_signature='',sender_keyword='sender')
    def StopCapture(self, token, sender):
        row=self.captures.get(str(token))
        if row and row['owner']!=str(sender): raise dbus.exceptions.DBusException('Capture belongs to another client',name=NAME+'.Denied')
        self.stop_capture(str(token))

    def stop_capture(self, token):
        row=self.captures.pop(token,None)
        if not row:return
        p=row['process']
        if p.poll() is None:
            p.terminate()
            GLib.timeout_add(750,lambda: (p.kill() if p.poll() is None else None) or False)
        p.stdout.close()
        self.publish();self.Event('CaptureStopped',json.dumps({'application':row['application']}));self.schedule()

    def capture_tick(self):
        for token,row in list(self.captures.items()):
            if time.monotonic()>=row['expires'] or row['process'].poll() is not None:self.stop_capture(token)
        return True

    def owner_changed(self,name,old,new):
        if str(name).startswith(':') and old and not new:
            for token,row in list(self.captures.items()):
                if row['owner']==str(name):self.stop_capture(token)
            if any(f['owner']==str(name) for f in self.core.focus.values()):
                self.dead_owners.add(str(name));self.schedule()

    def sleep(self, sleeping):
        self.sleep_requested=bool(sleeping)
        if sleeping:
            for token in list(self.captures):self.stop_capture(token)
        self.Event('SuspendRequested' if sleeping else 'ResumeCompleted',json.dumps({'recordingRestarts':False,'audioServerRestarts':False}))
        self.schedule()

    def power_event(self,kind,document):
        if kind=='SuspendRequested':self.sleep(True)
        elif kind=='ResumeCompleted':self.sleep(False)

    def start_subscription(self):
        try:
            self.subscription=subprocess.Popen(['pactl','subscribe'],stdout=subprocess.PIPE,stderr=subprocess.DEVNULL,env=dict(os.environ,LC_ALL='C.UTF-8'))
            os.set_blocking(self.subscription.stdout.fileno(),False)
            GLib.io_add_watch(self.subscription.stdout.fileno(),GLib.IO_IN|GLib.IO_HUP,self.backend_event)
        except OSError:self.subscription=None

    def backend_event(self, fd, condition):
        if condition & GLib.IO_HUP:
            self.subscription.wait();self.subscription.stdout.close();self.subscription=None;self.schedule();return False
        try: payload=os.read(fd,65536).decode(errors='replace')
        except BlockingIOError:return True
        if any(('on '+kind+' ') in payload for kind in ('sink','source','sink-input','source-output','server','card')):self.schedule()
        return True

    def schedule(self):
        if not self.timer:self.timer=GLib.timeout_add(700,self.flush)

    def flush(self):
        self.timer=0;self.work();return False

    def fallback(self):
        if self.subscription is None:self.start_subscription()
        self.schedule();return True

    def close(self):
        for token in list(self.captures):self.stop_capture(token)
        if self.subscription and self.subscription.poll() is None:self.subscription.terminate()
        self.pool.shutdown(wait=True)
        # Restore only untouched levels that this instance ducked.
        try:self.core.focus.clear();self.core.refresh()
        except Exception:logging.exception('Could not restore focus levels on exit')


if __name__=='__main__':
    if os.geteuid()==0:sys.exit('EtherAudio must run in the desktop user session')
    DBusGMainLoop(set_as_default=True)
    loop=GLib.MainLoop();service=Service(dbus.SessionBus())
    signal.signal(signal.SIGTERM,lambda *args:loop.quit())
    signal.signal(signal.SIGINT,lambda *args:loop.quit())
    try:loop.run()
    finally:service.close()
