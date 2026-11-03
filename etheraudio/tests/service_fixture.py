"""Private-bus protocol tests. Fake pactl/parec never open audio hardware."""
from pathlib import Path
import json,os,subprocess,sys,tempfile,time,unittest
import dbus
from dbus.mainloop.glib import DBusGMainLoop
from gi.repository import GLib

SOURCE=Path(__file__).resolve().parents[1]/'service.py'
NAME='com.etherneco.EtherAudio1';PATH='/com/etherneco/EtherAudio1'


class ProtocolTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        DBusGMainLoop(set_as_default=True)
        cls.temp=tempfile.TemporaryDirectory();root=Path(cls.temp.name);bin=root/'bin';bin.mkdir()
        pactl=bin/'pactl'
        pactl.write_text('''#!/usr/bin/python3
import sys,json,time
args=sys.argv[1:]
if args==['subscribe']:time.sleep(120)
elif args[0].startswith('get-default-'):print('fixture_mic' if args[0].endswith('source') else 'fixture_sink')
elif args[:2]==['--format=json','list']:
 kind=args[-1];print(json.dumps([{'name':'fixture_mic' if kind=='sources' else 'fixture_sink','index':1,'description':'Protocol fixture','volume':{},'mute':False,'properties':{}}] if kind in ('sinks','sources') else []))
else:sys.exit(1)
''')
        parec=bin/'parec';parec.write_text('''#!/usr/bin/python3
import os,time
os.write(1,b'fixture-pcm')
time.sleep(90)
''')
        pactl.chmod(0o755);parec.chmod(0o755)
        env=dict(os.environ,PATH=str(bin)+':/usr/bin:/bin',XDG_CONFIG_HOME=str(root/'config'))
        cls.log=(root/'service.log').open('w+')
        cls.process=subprocess.Popen([sys.executable,str(SOURCE)],env=env,stdout=cls.log,stderr=cls.log)
        cls.bus=dbus.SessionBus(private=True)
        cls.bus.set_exit_on_disconnect(False)
        for _ in range(150):
            try:
                if not cls.bus.name_has_owner(NAME):
                    time.sleep(.1);continue
                cls.api=dbus.Interface(cls.bus.get_object(NAME,PATH,introspect=False),NAME)
                state=json.loads(str(cls.api.GetState()))
                if state.get('ready') and not state.get('busy'):break
            except dbus.DBusException:pass
            if cls.process.poll() is not None:
                cls.log.seek(0);raise AssertionError(cls.log.read())
            time.sleep(.1)
        else:
            cls.log.seek(0)
            cls.process.terminate();cls.process.wait(timeout=10)
            raise AssertionError('Fixture service did not become ready: '+repr(cls.bus.list_names())+' '+cls.log.read())
    @classmethod
    def tearDownClass(cls):
        cls.bus.close();cls.process.terminate();cls.process.wait(timeout=10);cls.log.close();cls.temp.cleanup()
    def state(self):return json.loads(str(self.api.GetState()))
    def test_capture_without_consent_never_starts(self):
        with self.assertRaises(dbus.DBusException):self.api.StartCapture('fixture_mic','test',False,dbus.UInt32(1))
        self.assertEqual(self.state()['managedCaptures'],[])
    def test_notification_sound_cannot_be_triggered_by_ordinary_client(self):
        with self.assertRaises(dbus.DBusException):self.api.PlayNotification('default')
        self.assertEqual(self.state()['managedCaptures'],[])
    def test_capture_fd_and_owner_enforcement(self):
        token,handle=self.api.StartCapture('fixture_mic','Synthetic fixture only',True,dbus.UInt32(2))
        fd=handle.take();self.assertEqual(os.read(fd,11),b'fixture-pcm')
        other=dbus.SessionBus(private=True)
        other.set_exit_on_disconnect(False)
        try:
            api=dbus.Interface(other.get_object(NAME,PATH),NAME)
            with self.assertRaises(dbus.DBusException):api.StopCapture(token)
        finally:other.close()
        self.api.StopCapture(token);os.close(fd);self.assertEqual(self.state()['managedCaptures'],[])
    def test_capture_ends_after_client_disconnect(self):
        bus=dbus.SessionBus(private=True);bus.set_exit_on_disconnect(False);api=dbus.Interface(bus.get_object(NAME,PATH),NAME)
        token,handle=api.StartCapture('fixture_mic','Synthetic fixture only',True,dbus.UInt32(5));fd=handle.take();bus.close()
        for _ in range(30):
            if not self.state()['managedCaptures']:break
            time.sleep(.1)
        os.close(fd);self.assertEqual(self.state()['managedCaptures'],[])
    def test_timeout_stops_capture_without_restart(self):
        token,handle=self.api.StartCapture('fixture_mic','Synthetic fixture only',True,dbus.UInt32(1));fd=handle.take()
        for _ in range(30):
            if not self.state()['managedCaptures']:break
            time.sleep(.1)
        os.close(fd);self.assertEqual(self.state()['managedCaptures'],[])
    def test_unknown_source_rejected(self):
        with self.assertRaises(dbus.DBusException):self.api.StartCapture('real-device-never-used','test',True,dbus.UInt32(1))
    def test_capture_duration_is_bounded(self):
        for seconds in (0,61):
            with self.assertRaises(dbus.DBusException):self.api.StartCapture('fixture_mic','test',True,dbus.UInt32(seconds))
    def test_focus_crash_notifies_other_clients_to_resume(self):
        received=[]
        receiver=self.bus.add_signal_receiver(lambda kind,document:received.append((str(kind),str(document))),signal_name='Event',dbus_interface=NAME)
        other=dbus.SessionBus(private=True);other.set_exit_on_disconnect(False);peer=dbus.Interface(other.get_object(NAME,PATH),NAME)
        for _ in range(30):
            if not self.state().get('busy'):break
            time.sleep(.1)
        peer.Command('focus','call','{}');other.close()
        context=GLib.MainContext.default()
        for _ in range(60):
            while context.pending():context.iteration(False)
            if any(kind=='FocusChanged' and json.loads(data).get('action')=='resume-eligible-streams' for kind,data in received):break
            time.sleep(.1)
        receiver.remove()
        self.assertTrue(any(kind=='FocusChanged' and json.loads(data).get('action')=='resume-eligible-streams' for kind,data in received))
        self.assertEqual(self.state()['focus'],[])


if __name__=='__main__':unittest.main(verbosity=2)
