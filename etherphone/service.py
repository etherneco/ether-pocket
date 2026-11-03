#!/usr/bin/python3
"""User-session telephony service. Existing ModemManager keeps modem ownership."""
import json
import hashlib
import os
from pathlib import Path
import signal
import sys
import time
from concurrent.futures import ThreadPoolExecutor
sys.path.insert(0,str(Path(__file__).resolve().parent))
import dbus
import dbus.service
from dbus.mainloop.glib import DBusGMainLoop
from gi.repository import GLib
from core import Contacts, History, Manager, PhoneError, EMERGENCY_WARNING, diagnostic, private_directory
from provider import ModemManagerProvider, MM, ROOT, CALL

NAME='com.etherneco.EtherPhone1'
PATH='/com/etherneco/EtherPhone1'

class ContactService(dbus.service.Object):
    """Reusable contact API hosted by the same unprivileged process/store."""
    NAME='com.etherneco.EtherContacts1'
    def __init__(self,bus,phone):
        self.name=dbus.service.BusName(self.NAME,bus,do_not_queue=True)
        super().__init__(self.name,'/com/etherneco/EtherContacts1');self.phone=phone
    @dbus.service.method(NAME,in_signature='s',out_signature='s')
    def Search(self,query):
        q=str(query).casefold()[:200]
        return json.dumps([c for c in self.phone.state.get('contacts',[]) if q in (c['name']+' '+' '.join(c['numbers'])+' '+c['notes']).casefold()])
    @dbus.service.method(NAME,in_signature='sss',out_signature='s',async_callbacks=('success','failure'))
    def Command(self,action,target,document,success,failure):
        if str(action) not in ('contact-save','contact-delete','import-vcard','export-vcard','backup-contacts'):
            failure(dbus.DBusException('Unsupported contact operation',name=self.NAME+'.Invalid'));return
        self.phone.Command(action,target,document,None,success,failure)

class Service(dbus.service.Object):
    def __init__(self,bus):
        self.name=dbus.service.BusName(NAME,bus,do_not_queue=True)
        super().__init__(self.name,PATH)
        self.bus=bus;self.pool=ThreadPoolExecutor(max_workers=1)
        self.epoch=time.time()-time.monotonic()
        self.contact_api=ContactService(bus,self)
        self.busy=False;self.dirty=False;self.events=[];self.inhibitor=None;self.focus=''
        self.notification_ids=set()
        bus.add_signal_receiver(self.notification_action,signal_name='ActionInvoked',dbus_interface='org.freedesktop.Notifications',bus_name='org.freedesktop.Notifications')
        self.state={'ready':False,'calls':[],'contacts':[],'history':[],'emergencyWarning':EMERGENCY_WARNING}
        self.provider=None;self.core=None;self.config={};self.audio={}
        self.system=dbus.SystemBus()
        self.system.add_signal_receiver(self.backend_signal,signal_name='PropertiesChanged',dbus_interface='org.freedesktop.DBus.Properties',bus_name=MM)
        self.system.add_signal_receiver(self.call_signal,signal_name='StateChanged',dbus_interface=CALL,bus_name=MM,path_keyword='path',sender_keyword='owner')
        for sig in ('InterfacesAdded','InterfacesRemoved'):
            self.system.add_signal_receiver(self.backend_signal,signal_name=sig,dbus_interface='org.freedesktop.DBus.ObjectManager',bus_name=MM)
        self.system.add_signal_receiver(self.backend_signal,signal_name='NameOwnerChanged',dbus_interface='org.freedesktop.DBus',arg0=MM)
        self.system.add_signal_receiver(self.resume,signal_name='PrepareForSleep',dbus_interface='org.freedesktop.login1.Manager',bus_name='org.freedesktop.login1')
        bus.add_signal_receiver(self.audio_changed,signal_name='Changed',dbus_interface='com.etherneco.EtherAudio1',bus_name='com.etherneco.EtherAudio1')
        GLib.timeout_add_seconds(10,self.tick)
        self.work()

    @dbus.service.signal(NAME,signature='s')
    def Changed(self,document):pass

    @dbus.service.signal(NAME,signature='ss')
    def Event(self,kind,document):pass

    @dbus.service.method(NAME,in_signature='',out_signature='s')
    def GetState(self):return json.dumps(self.state)

    @dbus.service.method(NAME,in_signature='',out_signature='')
    def Refresh(self):self.backend_signal()

    def backend_signal(self,*args,**kwargs):
        if self.busy:self.dirty=True
        else:self.work()

    def tick(self):self.backend_signal();return True

    def resume(self,sleeping):
        if not sleeping:self.backend_signal()

    def audio_changed(self,document):
        try:self.audio=json.loads(str(document)).get('callAudio',{})
        except ValueError:pass

    def call_signal(self,old,new,reason,path=None,owner=None):
        boot=Path('/proc/sys/kernel/random/boot_id').read_text().strip()
        self.events.append((boot+'|'+str(owner)+'|'+str(path),int(new),int(reason),self.timestamp()))
        self.backend_signal()

    def timestamp(self):return self.epoch+time.monotonic()

    def initialize(self):
        data=Path(os.environ.get('XDG_DATA_HOME',str(Path.home()/'.local/share')))
        self.contacts=Contacts(data/'ethercontacts/contacts.sqlite')
        self.history=History(data/'etherphone/history.sqlite')
        self.core=Manager(self.history,self.contacts,self.timestamp)
        self.folder=private_directory(Path(os.environ.get('XDG_CONFIG_HOME',str(Path.home()/'.config')))/'etherphone')
        self.config={'hideCallerOnLock':True,'missedNotifications':True,'retentionDays':90}
        try:
            saved=json.loads((self.folder/'settings.json').read_text())
            self.validate_config(saved);self.config.update(saved)
        except FileNotFoundError:pass
        self.provider=ModemManagerProvider()
        self.worker_session=dbus.SessionBus(private=True)
        self.worker_system=self.provider.bus

    def validate_config(self,data):
        if not isinstance(data,dict) or set(data)-{'hideCallerOnLock','missedNotifications','retentionDays'}:
            raise PhoneError('Unsupported setting')
        for k,v in data.items():
            if k=='retentionDays':
                if type(v) is not int or not 1<=v<=3650:raise PhoneError('Retention must be 1–3650 days')
            elif type(v) is not bool:raise PhoneError('Settings require boolean values')

    def command(self,action,target,data):
        if action=='dial':
            status,_=self.provider.snapshot()
            n=self.core.preflight(data.get('number',''),status)
            if n in ('112','999') and data.get('emergencyConfirmed') is not True:
                raise PhoneError(EMERGENCY_WARNING+' Confirm this emergency attempt explicitly.')
            self.provider.dial(n)
        elif action in ('answer','decline','end','dtmf'):
            c=self.core.request(target,action)
            try:self.provider.command(target.rsplit('|',1)[-1],action,str(data.get('tone','')))
            except Exception:
                c.requested=''
                raise
        elif action=='contact-save':return self.contacts.save(data)
        elif action=='contact-delete':self.contacts.remove(target)
        elif action=='history-delete':self.history.remove(target)
        elif action=='history-clear':
            if data.get('confirmed') is not True:raise PhoneError('Confirm clearing history')
            self.history.clear()
        elif action=='configure':
            self.validate_config(data);new=dict(self.config,**data)
            temp=self.folder/'settings.new'
            fd=os.open(temp,os.O_WRONLY|os.O_CREAT|os.O_TRUNC|os.O_NOFOLLOW,0o600)
            with os.fdopen(fd,'w') as f:json.dump(new,f);f.flush();os.fsync(f.fileno())
            temp.replace(self.folder/'settings.json');self.config=new
        elif action=='import-vcard':return self.contacts.import_vcard(data.get('vcard',''))
        elif action=='export-vcard':return self.contacts.export_vcard()
        elif action=='backup-contacts':
            path=self.folder/('contacts-backup-'+str(time.time_ns())+'.sqlite')
            self.contacts.backup(path);return str(path)
        elif action=='diagnostics':return json.dumps(diagnostic(self.state.get('status',{}),self.audio,self.core.failure),indent=2)
        elif action=='silence':
            # No fabricated ringtone state. Emit for an eventual verified ringer.
            self.EventOnMain('SilenceRequested',{})
        else:raise PhoneError('Unsupported operation; call audio, hold and conference are unverified')
        return ''

    def EventOnMain(self,kind,data):
        GLib.idle_add(lambda:(self.Event(kind,json.dumps(data)),False)[1])

    @dbus.service.method(NAME,in_signature='sss',out_signature='s',sender_keyword='sender',async_callbacks=('success','failure'))
    def Command(self,action,target,document,sender,success,failure):
        # The session bus is per Unix user. Cross-user control is not exported.
        # ModemManager performs its own PolicyKit authorization for that user.
        try:
            if len(document)>2_100_000 or len(target)>256:raise PhoneError('Request too large')
            data=json.loads(str(document))
            if not isinstance(data,dict):raise PhoneError('Command requires an object')
        except (ValueError,PhoneError) as e:
            failure(dbus.DBusException(str(e),name=NAME+'.Invalid'));return
        self.work((str(action),str(target),data),success,failure)

    def work(self,operation=None,success=None,failure=None):
        if self.busy:
            if failure:failure(dbus.DBusException('Telephony service busy; retry shortly',name=NAME+'.Busy'))
            else:self.dirty=True
            return
        self.busy=True
        events=self.events;self.events=[]
        def worker():
            result='';error=None;notices=[];status={};paths={}
            try:
                if self.core is None:self.initialize()
                if operation:
                    try:result=self.command(*operation)
                    except Exception as e:
                        error=self.safe_error(e);self.core.failure=error
                try:status,paths=self.provider.snapshot()
                except dbus.DBusException:status={'modem':False,'voice':False,'simReady':False,'registered':False}
                # StateChanged is modem evidence, including transitions shorter
                # than one refresh. Apply it before the latest object snapshot.
                for key,state,reason,stamp in events:
                    c=self.core.calls.get(key)
                    row=paths.get(key)
                    if c or row:
                        props=dict(row['props']) if row else {'Number':c.number,'Direction':1 if c.direction=='Incoming' else 2}
                        props.update(State=state,StateReason=reason)
                        self.core.observe(key,props,stamp=stamp)
                for key,row in paths.items():self.core.observe(key,row['props'])
                self.core.lost(set(self.core.calls)-set(paths))
                try:
                    api=dbus.Interface(self.worker_session.get_object('com.etherneco.EtherAudio1','/com/etherneco/EtherAudio1',introspect=False),'com.etherneco.EtherAudio1')
                    self.audio=json.loads(str(api.GetState(timeout=3))).get('callAudio',{})
                except (dbus.DBusException,ValueError):self.audio={'operational':False,'error':'EtherAudio unavailable'}
                active={k:c for k,c in self.core.calls.items() if c.state not in ('Ended','Failed','Uncertain')}
                self.lifecycle(active)
                for kind,key in self.core.events:
                    c=self.core.calls[key]
                    notices.append((kind,{'key':key,'name':c.name,'number':c.number}))
                self.core.events=[]
                # Bound memory and keep terminal calls in persistent history.
                self.core.calls=dict(list(self.core.calls.items())[-100:])
                with self.history.db:
                    self.history.db.execute('DELETE FROM calls WHERE end<?',(time.time()-self.config['retentionDays']*86400,))
                calls=[dict(c.public(self.timestamp()),key=k) for k,c in active.items()]
                history=[dict(row,name=self.contacts.lookup(row['number']).get('name','')) for row in self.history.list()]
                state={'ready':True,'status':status,'calls':calls,'contacts':self.contacts.list(),
                    'history':history,'config':self.config,'audio':self.audio,
                    'emergencyWarning':EMERGENCY_WARNING,'lastFailure':self.core.failure,
                    'capabilities':{'hold':False,'conference':False,'routes':False,'mute':False,'dtmf':bool(status.get('voice'))},
                    'ims':'Unavailable / unverified','volte':'Blocked','incomingWake':'Not tested',
                    'ringtone':'Blocked: no validated cellular ringtone lifecycle',
                    'powerInhibited':self.inhibitor is not None,'realCallVerified':False}
            except Exception as e:
                error=self.safe_error(e)
                state={'ready':False,'status':{},'calls':[],'contacts':[],'history':[],
                    'emergencyWarning':EMERGENCY_WARNING,'lastFailure':error}
            def finish():
                self.state=state;self.busy=False
                self.Changed(json.dumps(state))
                for kind,data in notices:
                    self.Event(kind,json.dumps(data));self.notify(kind,data)
                if error and failure:failure(dbus.DBusException(error,name=NAME+'.Failed'))
                elif success:success(str(result))
                if self.dirty or self.events:self.dirty=False;self.work()
                return False
            GLib.idle_add(finish)
        self.pool.submit(worker)

    def safe_error(self,e):
        if isinstance(e,PhoneError):return str(e)
        if isinstance(e,dbus.DBusException):return 'Backend request failed: '+e.get_dbus_name()
        # Exception messages can contain a number, SQL arguments or a vCard.
        return 'Telephony operation failed ('+type(e).__name__+'); no automatic retry'

    def lifecycle(self,active):
        if active and self.inhibitor is None:
            try:
                api=dbus.Interface(self.worker_system.get_object('org.freedesktop.login1','/org/freedesktop/login1',introspect=False),'org.freedesktop.login1.Manager')
                self.inhibitor=api.Inhibit('sleep','EtherPhone','Observed cellular call','block',timeout=3).take()
            except dbus.DBusException:pass
        if not active and self.inhibitor is not None:os.close(self.inhibitor);self.inhibitor=None
        try:
            api=dbus.Interface(self.worker_session.get_object('com.etherneco.EtherAudio1','/com/etherneco/EtherAudio1',introspect=False),'com.etherneco.EtherAudio1')
            if active and not self.focus:self.focus=str(api.Command('focus','call','{}',timeout=3))
            elif not active and self.focus:api.Command('release-focus',self.focus,'{}',timeout=3);self.focus=''
        except dbus.DBusException:pass

    def notify(self,kind,data):
        if kind=='Incoming':return  # Dedicated incoming-call UI owns presentation.
        if kind=='Missed' and not self.config.get('missedNotifications',True):return
        try:
            api=dbus.Interface(self.bus.get_object('org.freedesktop.Notifications','/org/freedesktop/Notifications',introspect=False),'org.freedesktop.Notifications')
            # Privacy-safe text for the desktop and lock screen.
            api.Notify('EtherPhone',dbus.UInt32(0),'call-start','Incoming call' if kind=='Incoming' else 'Missed call',
                'Open EtherPhone for call controls or history',dbus.Array(['default','Open call history'],signature='s'),dbus.Dictionary({'urgency':dbus.Byte(1),'category':'call.missed','x-ether-privacy':'sensitive','x-ether-event-id':hashlib.sha256((str(kind)+str(data.get('key',''))).encode()).hexdigest()},signature='sv'),dbus.Int32(-1),
                reply_handler=self.notification_registered,error_handler=lambda *a:None)
        except dbus.DBusException:pass

    def notification_registered(self,ident):
        self.notification_ids.add(int(ident))
        if len(self.notification_ids)>100:self.notification_ids.remove(min(self.notification_ids))

    def notification_action(self,ident,key):
        if str(key)=='default' and int(ident) in self.notification_ids:
            self.notification_ids.discard(int(ident));self.Event('OpenHistory','{}')

    def stop(self):
        self.pool.shutdown(wait=True)
        if self.inhibitor is not None:os.close(self.inhibitor)
        # EtherAudio automatically releases leases when this connection exits.

if __name__=='__main__':
    os.umask(0o077);DBusGMainLoop(set_as_default=True)
    service=Service(dbus.SessionBus());loop=GLib.MainLoop()
    for sig in (signal.SIGTERM,signal.SIGINT):GLib.unix_signal_add(GLib.PRIORITY_DEFAULT,sig,lambda:(loop.quit(),False)[1])
    try:loop.run()
    finally:service.stop()
