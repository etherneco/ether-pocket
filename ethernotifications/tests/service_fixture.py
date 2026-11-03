"""Run ONLY under dbus-run-session. Uses a private store; never connects system bus."""
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import threading
import time
import unittest
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import dbus
from dbus.mainloop.glib import DBusGMainLoop
from gi.repository import GLib
from service import Service, NAME, PATH, STANDARD, STANDARD_PATH, process_identity
assert os.environ.get('DBUS_SESSION_BUS_ADDRESS'), 'Use dbus-run-session'
os.environ['DBUS_SYSTEM_BUS_ADDRESS'] = 'unix:path=/nonexistent/ethernotifications-test'
DBusGMainLoop(set_as_default=True)

class FakeAudio(dbus.service.Object):
    def __init__(self,bus):
        self.name=dbus.service.BusName('com.etherneco.EtherAudio1',bus,do_not_queue=True)
        super().__init__(self.name,'/com/etherneco/EtherAudio1')
    @dbus.service.method('com.etherneco.EtherAudio1',in_signature='s',out_signature='')
    def PlayNotification(self,sound):pass

if len(sys.argv)>1 and sys.argv[1] in ('--server','--qt-client'):
    folder=Path(sys.argv[2]); bus=dbus.SessionBus()
    service=Service(bus,folder/'history.sqlite',authorize=lambda sender:str(sender)==bus.get_name_owner('com.etherneco.NotificationTestUI'),system=False)
    audio=FakeAudio(bus)
    (folder/'ready').write_text('ready')
    loop=GLib.MainLoop()
    if sys.argv[1]=='--qt-client':
        result=[]
        def run_client():
            p=subprocess.run([sys.argv[3]],capture_output=True,text=True,timeout=15)
            result.append(p);GLib.idle_add(loop.quit)
        worker=threading.Thread(target=run_client,daemon=True);worker.start()
    loop.run()
    if sys.argv[1]=='--qt-client':
        worker.join();print(result[0].stdout+result[0].stderr);sys.exit(result[0].returncode)
    sys.exit(0)


class ProtocolTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.folder=tempfile.TemporaryDirectory()
        cls.a=dbus.SessionBus(private=True); cls.b=dbus.SessionBus(private=True); cls.ui=dbus.SessionBus(private=True)
        for client in (cls.a,cls.b,cls.ui):client.set_exit_on_disconnect(False)
        cls.ui_name=dbus.service.BusName('com.etherneco.NotificationTestUI',cls.ui,do_not_queue=True)
        cls.events=[]; cls.b_events=[]; cls.extra_peers=[]
        for client, events in ((cls.a,cls.events),(cls.b,cls.b_events)):
            client.add_signal_receiver(lambda ident,reason,events=events:events.append(('closed',int(ident),int(reason))),signal_name='NotificationClosed',dbus_interface=STANDARD)
            client.add_signal_receiver(lambda ident,key,events=events:events.append(('action',int(ident),str(key))),signal_name='ActionInvoked',dbus_interface=STANDARD)
        cls.loop=GLib.MainLoop();cls.thread=threading.Thread(target=cls.loop.run,daemon=True);cls.thread.start()
        cls.start()

    @classmethod
    def start(cls):
        ready=Path(cls.folder.name)/'ready'; ready.unlink(missing_ok=True)
        cls.server=subprocess.Popen([sys.executable,__file__,'--server',cls.folder.name],stdout=subprocess.PIPE,stderr=subprocess.PIPE)
        for _ in range(200):
            if ready.exists():break
            if cls.server.poll() is not None:raise RuntimeError(cls.server.communicate()[1].decode())
            time.sleep(.02)
        assert ready.exists()
        cls.api=dbus.Interface(cls.a.get_object(STANDARD,STANDARD_PATH,introspect=False),STANDARD)
        cls.other=dbus.Interface(cls.b.get_object(STANDARD,STANDARD_PATH,introspect=False),STANDARD)
        cls.control=dbus.Interface(cls.ui.get_object(NAME,PATH,introspect=False),NAME)

    @classmethod
    def tearDownClass(cls):
        cls.server.terminate();cls.server.communicate(timeout=5);cls.loop.quit();cls.thread.join(timeout=3)
        cls.ui_name=None
        for client in [cls.a,cls.b,cls.ui]+cls.extra_peers:client.close()
        cls.folder.cleanup()

    def setUp(self):
        self.command('session',data=dict(locked=False,callActive=False,screenOff=False))
        self.command('configure',data=dict(dnd='off',manualDnd=True))

    def command(self,action,ident=0,data=None):return json.loads(self.control.Command(action,dbus.UInt32(ident),json.dumps(data or {})))
    def send(self,api=None,replaces=0,body='PRIVATE-FIXTURE-BODY',hints=None,timeout=0):
        return int((api or self.api).Notify('Spoofed App',dbus.UInt32(replaces),'mail-unread','Test',body,dbus.Array(['default','Open'],signature='s'),dbus.Dictionary(hints or {},signature='sv'),dbus.Int32(timeout)))
    def state(self):return json.loads(self.control.GetState())
    def wait_event(self,event):
        for _ in range(100):
            if event in self.events:return
            time.sleep(.02)
        self.fail((event,self.events))

    def test_01_standard_identity_ownership_and_private_ui(self):
        self.assertEqual(list(self.api.GetCapabilities()),['body','actions','persistence'])
        self.assertEqual(str(self.api.GetServerInformation()[0]),'EtherNotifications')
        who=process_identity(self.a,self.a.get_unique_name())
        self.assertNotEqual(who['app'],'Spoofed App')
        ident=self.send()
        self.assertNotEqual(next(c for c in self.state()['cards'] if c['id']==ident)['appId'],'Spoofed App')
        with self.assertRaises(dbus.DBusException):self.other.CloseNotification(dbus.UInt32(ident))
        with self.assertRaises(dbus.DBusException):self.send(api=self.other,replaces=ident)
        bad=dbus.Interface(self.b.get_object(NAME,PATH,introspect=False),NAME)
        with self.assertRaises(dbus.DBusException):bad.GetState()
        with self.assertRaises(dbus.DBusException):bad.Command('configure',dbus.UInt32(0),'{}')
        self.assertEqual(self.send(replaces=ident),ident)
        self.command('invoke',ident,dict(key='default'))
        self.wait_event(('action',ident,'default'));self.wait_event(('closed',ident,2))
        self.assertNotIn(('action',ident,'default'),self.b_events)
        self.assertNotIn(('closed',ident,2),self.b_events)

    def test_02_expiry_close_dnd_lock_and_settings(self):
        ident=self.send(timeout=100)
        self.wait_event(('closed',ident,1))
        ident=self.send();self.api.CloseNotification(dbus.UInt32(ident));self.wait_event(('closed',ident,3))
        self.command('configure',data=dict(dnd='silence',silent=True))
        self.assertEqual(self.state()['dnd'],'silence')
        ident=self.send()
        self.command('session',data=dict(locked=True,callActive=False,screenOff=False))
        card=next(c for c in self.state()['cards'] if c['id']==ident)
        self.assertEqual(card['body'],'');self.assertFalse(card['actions'])
        with self.assertRaises(dbus.DBusException):self.command('invoke',ident,dict(key='default'))

    def test_03_service_restart_history_and_no_replay(self):
        ident=self.send()
        self.server.terminate();self.server.communicate(timeout=5);self.start()
        self.assertTrue(self.state()['locked'])
        self.command('session',data=dict(locked=False,callActive=False,screenOff=False))
        card=next(c for c in self.state()['cards'] if c['id']==ident)
        self.assertEqual(card['body'],'');self.assertFalse(card['actions'])
        self.assertGreater(self.send(),ident)
        self.assertNotIn(b'PRIVATE-FIXTURE-BODY',(Path(self.folder.name)/'history.sqlite').read_bytes())

    def test_04_competing_daemon_refuses_name(self):
        p=subprocess.run([sys.executable,__file__,'--server',self.folder.name],capture_output=True,text=True,timeout=5)
        self.assertNotEqual(p.returncode,0)
        self.assertIn('NameExistsException',p.stderr)
        self.assertEqual(str(self.api.GetServerInformation()[0]),'EtherNotifications')

    def test_05_burst_is_bounded_and_ui_remains_responsive(self):
        peers=[dbus.SessionBus(private=True) for _ in range(6)]
        for peer in peers:peer.set_exit_on_disconnect(False)
        accepted=0;rejected=0;started=time.monotonic()
        try:
            for peer in peers:
                api=dbus.Interface(peer.get_object(STANDARD,STANDARD_PATH,introspect=False),STANDARD)
                for _ in range(20):
                    try:self.send(api=api);accepted+=1
                    except dbus.DBusException as e:
                        self.assertIn('rate limit',str(e));rejected+=1
            elapsed=time.monotonic()-started
            self.assertGreater(accepted,0);self.assertLessEqual(accepted,100);self.assertGreater(rejected,0)
            self.assertLess(elapsed,10,'Burst must finish before the rate window renews')
            started=time.monotonic();snapshot=self.state();latency=time.monotonic()-started
            self.assertTrue(snapshot['ready']);self.assertLess(latency,1)
            self.assertLessEqual(len(snapshot['cards']),512)
            print(json.dumps({'burstAccepted':accepted,'burstRejected':rejected,'burstSeconds':elapsed,'snapshotSeconds':latency}))
        finally:
            # Keep dispatched connections alive until the GLib dispatch thread
            # has stopped; dbus-python cannot close them concurrently with it.
            self.extra_peers.extend(peers)


if __name__=='__main__':unittest.main(verbosity=2)
