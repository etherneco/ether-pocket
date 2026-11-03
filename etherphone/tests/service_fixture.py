"""Private-bus integration tests. BOTH system/session buses are isolated.

Never run this against a real system bus. No QMI, PCM, network or suspend I/O.
"""
from pathlib import Path
import json,os,subprocess,sys,tempfile,threading,time,traceback
import dbus,dbus.service
from dbus.mainloop.glib import DBusGMainLoop
from gi.repository import GLib
ROOT=Path(__file__).resolve().parents[1]
MM='org.freedesktop.ModemManager1';BASE='/org/freedesktop/ModemManager1';MODEM=MM+'.Modem';VOICE=MODEM+'.Voice';CALL=MM+'.Call'
NAME='com.etherneco.EtherPhone1';PATH='/com/etherneco/EtherPhone1'
assert os.environ.get('DBUS_SESSION_BUS_ADDRESS'),'Use dbus-run-session'
# Deliberately replace the system bus before any connection is made.
os.environ['DBUS_SYSTEM_BUS_ADDRESS']=os.environ['DBUS_SESSION_BUS_ADDRESS']
DBusGMainLoop(set_as_default=True)
bus=dbus.SessionBus();owner=dbus.service.BusName(MM,bus)

class FakeCall(dbus.service.Object):
    def __init__(self,bus,path,direction=2):
        super().__init__(bus,path);self.path=path;self.state=0;self.reason=0;self.direction=direction;self.requests=[]
    def props(self):return {'State':dbus.Int32(self.state),'StateReason':dbus.Int32(self.reason),'Direction':dbus.Int32(self.direction),'Number':dbus.String('+441234567890')}
    @dbus.service.method(CALL,in_signature='',out_signature='')
    def Start(self):self.requests.append('Start');self.change(1,1)
    @dbus.service.method(CALL,in_signature='',out_signature='')
    def Accept(self):self.requests.append('Accept')
    @dbus.service.method(CALL,in_signature='',out_signature='')
    def Hangup(self):self.requests.append('Hangup')
    @dbus.service.method(CALL,in_signature='s',out_signature='')
    def SendDtmf(self,tone):self.requests.append('Dtmf:'+str(tone))
    @dbus.service.signal(CALL,signature='iiu')
    def StateChanged(self,old,new,reason):pass
    def change(self,state,reason=0):
        old=self.state;self.state=state;self.reason=reason;self.StateChanged(old,state,reason)

class Fixture(dbus.service.Object):
    def __init__(self):
        super().__init__(bus,BASE);self.calls={};self.serial=0;self.registered=True;self.sim=True
    @dbus.service.method('org.freedesktop.DBus.ObjectManager',in_signature='',out_signature='a{oa{sa{sv}}}')
    def GetManagedObjects(self):
        result={BASE+'/Modem/0':{MODEM:{'State':dbus.Int32(8),'Sim':dbus.ObjectPath(BASE+'/SIM/0' if self.sim else '/'),'UnlockRequired':dbus.UInt32(1 if self.sim else 2)},
            VOICE:{'Calls':dbus.Array([dbus.ObjectPath(p) for p in self.calls],signature='o'),'EmergencyOnly':dbus.Boolean(False)},
            MODEM+'.Modem3gpp':{'RegistrationState':dbus.UInt32(1 if self.registered else 0)}}}
        result.update({p:{CALL:c.props()} for p,c in self.calls.items()});return result
    @dbus.service.signal('org.freedesktop.DBus.ObjectManager',signature='oa{sa{sv}}')
    def InterfacesAdded(self,path,interfaces):pass
    def create(self,direction=2):
        self.serial+=1;p=BASE+'/Call/'+str(self.serial);c=FakeCall(bus,p,direction);self.calls[p]=c
        self.InterfacesAdded(p,{CALL:c.props()});return c

class Voice(dbus.service.Object):
    def __init__(self,fixture):super().__init__(bus,BASE+'/Modem/0');self.fixture=fixture
    @dbus.service.method(VOICE,in_signature='a{sv}',out_signature='o')
    def CreateCall(self,props):return dbus.ObjectPath(self.fixture.create().path)
    @dbus.service.method(VOICE,in_signature='o',out_signature='')
    def DeleteCall(self,path):self.fixture.calls.pop(str(path),None)

class FakeAudio(dbus.service.Object):
    def __init__(self):
        self.name=dbus.service.BusName('com.etherneco.EtherAudio1',bus)
        super().__init__(self.name,'/com/etherneco/EtherAudio1')
    @dbus.service.method('com.etherneco.EtherAudio1',in_signature='',out_signature='s')
    def GetState(self):return json.dumps({'callAudio':{'operational':False,'error':'Isolated fixture; no PCM'}})
    @dbus.service.method('com.etherneco.EtherAudio1',in_signature='sss',out_signature='s')
    def Command(self,action,target,data):return 'test-focus-token' if action=='focus' else ''

class FakeNotifications(dbus.service.Object):
    def __init__(self):
        self.name=dbus.service.BusName('org.freedesktop.Notifications',bus)
        super().__init__(self.name,'/org/freedesktop/Notifications');self.messages=[]
    @dbus.service.method('org.freedesktop.Notifications',in_signature='susssasa{sv}i',out_signature='u')
    def Notify(self,app,replaces,icon,summary,body,actions,hints,timeout):
        self.messages.append(str(summary));return dbus.UInt32(len(self.messages))
    @dbus.service.signal('org.freedesktop.Notifications',signature='us')
    def ActionInvoked(self,ident,key):pass

fixture=Fixture();voice=Voice(fixture);audio=FakeAudio();notifications=FakeNotifications();loop=GLib.MainLoop();errors=[];checks=[]

def on_main(fn):
    done=threading.Event();box=[]
    def run():
        try:box.append(fn())
        except Exception as e:box.append(e)
        done.set();return False
    GLib.idle_add(run);assert done.wait(5)
    if box and isinstance(box[0],Exception):raise box[0]
    return box[0] if box else None

def driver():
    process=None
    try:
        with tempfile.TemporaryDirectory() as tmp:
            env=dict(os.environ,XDG_DATA_HOME=tmp+'/data',XDG_CONFIG_HOME=tmp+'/config')
            process=subprocess.Popen([sys.executable,str(ROOT/'service.py')],env=env,stdout=subprocess.PIPE,stderr=subprocess.PIPE)
            client=dbus.SessionBus(private=True)
            until=time.monotonic()+8
            while not client.name_has_owner(NAME):
                if process.poll() is not None:raise AssertionError(process.communicate()[1].decode())
                if time.monotonic()>until:raise AssertionError('Service startup timed out')
                time.sleep(.05)
            api=dbus.Interface(client.get_object(NAME,PATH,introspect=False,follow_name_owner_changes=True),NAME)
            received=[]
            on_main(lambda:bus.add_signal_receiver(lambda kind,document:received.append(str(kind)),signal_name='Event',dbus_interface=NAME,bus_name=NAME))
            def state():
                try:return json.loads(str(api.GetState(timeout=2)))
                except dbus.DBusException:return {}
            def wait(predicate):
                until=time.monotonic()+10
                while time.monotonic()<until:
                    s=state()
                    if predicate(s):return s
                    time.sleep(.05)
                raise AssertionError('Timed out waiting for isolated state: '+json.dumps(s))
            def command(action,target='',data=None):
                until=time.monotonic()+8
                while True:
                    try:return str(api.Command(action,target,json.dumps(data or {}),timeout=5))
                    except dbus.DBusException as e:
                        if e.get_dbus_name().endswith('.Busy') and time.monotonic()<until:time.sleep(.05);continue
                        raise
            def refresh():api.Refresh(timeout=2)
            wait(lambda s:s.get('ready'));checks.append('service startup / isolated bus')
            command('contact-save',data={'name':'Private test','numbers':['+441234567890','+48123456789'],'emails':['test@example.test']})
            wait(lambda s:len(s.get('contacts',[]))==1);checks.append('shared contacts API')
            contact_api=dbus.Interface(client.get_object('com.etherneco.EtherContacts1','/com/etherneco/EtherContacts1',introspect=False),'com.etherneco.EtherContacts1')
            assert len(json.loads(str(contact_api.Search('Private',timeout=2))))==1
            checks.append('reusable EtherContacts D-Bus alias')
            command('dial',data={'number':'+441234567890'})
            s=wait(lambda s:len(s.get('calls',[]))==1);key=s['calls'][0]['key']
            assert s['calls'][0]['state']=='Dialling',s
            assert s['history']==[];checks.append('Start submission does not become Active')
            call=on_main(lambda:next(iter(fixture.calls.values())))
            on_main(lambda:call.change(4,3));wait(lambda s:s.get('calls',[{}])[0].get('state')=='Active')
            command('dtmf',key,{'tone':'5'});assert 'Dtmf:5' in call.requests
            command('end',key);s=wait(lambda s:s.get('calls',[{}])[0].get('requested')=='end')
            assert s['calls'][0]['state']=='Active';checks.append('end request waits for termination evidence')
            on_main(lambda:call.change(7,4));s=wait(lambda s:len(s.get('history',[]))==1)
            assert s['history'][0]['result']=='Outgoing';checks.append('observed terminal history')
            on_main(lambda:fixture.calls.clear());refresh();wait(lambda s:not s.get('calls'))
            incoming=on_main(lambda:fixture.create(1));on_main(lambda:incoming.change(3,2));refresh()
            s=wait(lambda s:len(s.get('calls',[]))==1);key=s['calls'][0]['key']
            command('answer',key);assert state()['calls'][0]['state']=='Incoming'
            on_main(lambda:incoming.change(4,3));wait(lambda s:s.get('calls',[{}])[0].get('state')=='Active')
            on_main(lambda:incoming.change(7,4));s=wait(lambda s:len(s.get('history',[]))==2)
            assert s['history'][0]['result']=='Incoming';checks.append('incoming accept waits for Active indication')
            on_main(lambda:fixture.calls.clear());refresh();wait(lambda s:not s.get('calls'))
            missed=on_main(lambda:fixture.create(1));on_main(lambda:missed.change(3,2));refresh()
            wait(lambda s:len(s.get('calls',[]))==1);on_main(lambda:missed.change(7,4))
            s=wait(lambda s:any(c['result']=='Missed' for c in s.get('history',[])));checks.append('missed classification from observed events')
            assert 'Missed call' in on_main(lambda:notifications.messages),notifications.messages
            checks.append('notification delivery on private bus')
            assert 'Incoming call' not in on_main(lambda:notifications.messages),'Incoming calls must stay in the dedicated overlay'
            on_main(lambda:notifications.ActionInvoked(dbus.UInt32(len(notifications.messages)),'default'))
            wait(lambda s:'OpenHistory' in on_main(lambda:received))
            checks.append('missed notification action opens history without placing a call')
            report=command('diagnostics');assert '+441234567890' not in report and 'Private test' not in report;checks.append('redacted export')
            command('configure',data={'hideCallerOnLock':False,'retentionDays':30})
            s=wait(lambda s:s.get('config',{}).get('retentionDays')==30)
            process.terminate();out,err=process.communicate(timeout=8);assert process.returncode==0 and not err,err.decode()
            process=subprocess.Popen([sys.executable,str(ROOT/'service.py')],env=env,stdout=subprocess.PIPE,stderr=subprocess.PIPE)
            wait(lambda s:s.get('ready') and s.get('config',{}).get('retentionDays')==30);checks.append('settings survive service restart')
            on_main(lambda:fixture.calls.clear());refresh();wait(lambda s:not s.get('calls'))
            on_main(lambda:setattr(fixture,'registered',False));refresh();wait(lambda s:not s.get('status',{}).get('registered',True))
            try:command('dial',data={'number':'+441234567890'});raise AssertionError('No-network call should be refused')
            except dbus.DBusException:pass
            assert not fixture.calls;checks.append('no-network refusal sends no call request')
            try:command('dial',data={'number':'999'});raise AssertionError('Explicit emergency confirmation required')
            except dbus.DBusException:pass
            assert not fixture.calls;checks.append('unconfirmed emergency request never reaches provider')
            print(json.dumps({'isolated':True,'realCalls':False,'checks':checks},indent=2),flush=True)
    except Exception:errors.append(traceback.format_exc());print(errors[-1],file=sys.stderr,flush=True)
    finally:
        if process:
            if process.poll() is None:process.terminate()
            out,err=process.communicate(timeout=8)
            if err:print(err.decode(),file=sys.stderr)
        GLib.idle_add(loop.quit)

threading.Thread(target=driver,daemon=True).start();loop.run()
if errors:sys.exit(1)
