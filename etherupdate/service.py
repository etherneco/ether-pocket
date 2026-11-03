#!/usr/bin/python3
"""Privileged system-bus agent. UI stays in the ordinary user session."""
import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parent))
from concurrent.futures import ThreadPoolExecutor
from contextlib import contextmanager
import json
import os
import time
import dbus
import dbus.service
from dbus.mainloop.glib import DBusGMainLoop
from gi.repository import GLib
from agent import Agent
from device import identity, token
from security import Rejected, protected_json
from credentials import CredentialStore, read_descriptor

NAME='com.etherneco.EtherUpdate1';PATH='/com/etherneco/EtherUpdate1'
def dump(value):return json.dumps(value,allow_nan=False,separators=(',',':'))


class Service(dbus.service.Object):
    def __init__(self):
        self.bus=dbus.SystemBus();self.name=dbus.service.BusName(NAME,self.bus,do_not_queue=True)
        super().__init__(self.bus,PATH)
        self.pool=ThreadPoolExecutor(max_workers=1);self.agent=None;self.busy=False;self.authorizing=False
        self.state=dict(ready=False,status='Starting');self.last_check=0;self.downloading=False
        GLib.timeout_add_seconds(1,self.publish_progress)
        self.work(self.initialize,lambda _:None,lambda _:None)
        GLib.timeout_add_seconds(3600,self.scheduled)

    def initialize(self):
        self.agent=Agent('/var/lib/etherupdate','/var/cache/etherupdate',protected_json('/etc/etherupdate/policy.json'),
                         protected_json('/etc/etherupdate/trusted-keys.json'),identity(),token())
        return None

    @dbus.service.signal(NAME,signature='s')
    def Changed(self,document):pass

    def publish_progress(self):
        if self.downloading and self.agent:
            self.state['progress']=dict(self.agent.progress)
            self.Changed(self.GetState())
        return True

    @dbus.service.signal(NAME,signature='ss')
    def Event(self,kind,message):pass

    @dbus.service.method(NAME,in_signature='',out_signature='s')
    def GetState(self):return dump(dict(self.state,busy=self.busy,authorizing=self.authorizing))

    def work(self,operation,success,failure):
        if self.busy or self.authorizing:
            failure(dbus.DBusException('Update service busy',name=NAME+'.Busy'));return
        self.busy=True;self.Changed(self.GetState())
        def worker():
            result=None;error=None;snapshot=None
            try:
                result=operation()
                if self.agent:snapshot=self.agent.snapshot()
            except Exception as e:
                # Network/provider exceptions never disclose request URLs, tokens,
                # server bodies, subprocess output or release text.
                error=str(e) if isinstance(e,Rejected) else 'Operation failed; inspect update history and connectivity'
                if self.agent:
                    try:snapshot=self.agent.snapshot()
                    except Exception:pass
            def finish():
                self.busy=False
                previous=self.state
                if snapshot:self.state=snapshot
                if error:self.state['lastError']=error
                else:self.state.pop('lastError',None)
                self.Changed(self.GetState())
                if error:
                    failure(dbus.DBusException(error,name=NAME+'.Rejected'));self.Event('failed',error)
                else:
                    success(dump(result))
                    if self.downloading:self.Event('downloaded','Download verified; ready for review')
                    if self.state.get('discovery')!=previous.get('discovery') and self.state.get('discovery',{}).get('status')=='Update available':
                        self.Event('available','Software updates are available in Settings')
                    old={t['id']:t['state'] for t in previous.get('history',[])}
                    for tx in self.state.get('history',[]):
                        if tx['state']!=old.get(tx['id']) and tx['state'] in ('Completed','Rolled Back','Recovery Required','Manual Intervention Required'):
                            self.Event(tx['state'],tx['state']+'; review Software Updates history')
                self.downloading=False
                return False
            GLib.idle_add(finish)
        self.pool.submit(worker)

    def authorize(self,sender,action,operation,success,failure):
        if self.busy or self.authorizing:
            failure(dbus.DBusException('Update service busy',name=NAME+'.Busy'));return
        uid=int(self.bus.get_unix_user(sender));self.authorizing=True
        authority=dbus.Interface(self.bus.get_object('org.freedesktop.PolicyKit1','/org/freedesktop/PolicyKit1/Authority'),'org.freedesktop.PolicyKit1.Authority')
        def denied(error):self.authorizing=False;failure(error)
        def allowed(result):
            self.authorizing=False
            if not result[0]:failure(dbus.DBusException('Administrator authorization required',name=NAME+'.Denied'));return
            # A vanished bus caller cannot leave an unattended privileged operation.
            try:
                if int(self.bus.get_unix_user(sender))!=uid:raise Rejected('Caller changed')
            except Exception:failure(dbus.DBusException('Caller disconnected',name=NAME+'.Denied'));return
            self.work(lambda:operation(uid),success,failure)
        authority.CheckAuthorization(('system-bus-name',{'name':dbus.String(sender,variant_level=1)}),
            'com.etherneco.etherupdate.'+action,{},dbus.UInt32(1),'',reply_handler=allowed,error_handler=denied,timeout=60)

    @dbus.service.method(NAME,in_signature='',out_signature='s',sender_keyword='sender',async_callbacks=('success','failure'))
    def CheckUpdates(self,sender,success,failure):
        self.authorize(sender,'manage',lambda uid:self.check(),success,failure)

    @dbus.service.method(NAME,in_signature='h',out_signature='s',sender_keyword='sender',async_callbacks=('success','failure'))
    def SetCredential(self,descriptor,sender,success,failure):
        # D-Bus transports a Unix FD, never the secret as a message string.
        held=[descriptor.take()]
        def close():
            if held:os.close(held.pop())
        def fail(error):close();failure(error)
        def save(uid):
            try:return self.agent.set_credential(read_descriptor(held[0]),CredentialStore())
            finally:close()
        try:self.authorize(sender,'credentials',save,success,fail)
        except Exception:
            close();self.authorizing=False
            failure(dbus.DBusException('Credential authorization unavailable',name=NAME+'.Denied'))

    @dbus.service.method(NAME,in_signature='',out_signature='s',sender_keyword='sender',async_callbacks=('success','failure'))
    def RemoveCredential(self,sender,success,failure):
        self.authorize(sender,'credentials',lambda uid:self.agent.remove_credential(CredentialStore()),success,failure)

    def check(self):
        if time.monotonic()-self.last_check<60:raise Rejected('Wait one minute between update checks')
        self.last_check=time.monotonic();return self.agent.check()

    def scheduled(self):
        if self.agent and not self.busy and not self.authorizing:
            last=self.state.get('discovery',{}).get('lastSuccessfulCheck',0) or 0
            if time.time()-last>86400:self.work(self.check,lambda _:None,lambda _:None)
        return True

    @dbus.service.method(NAME,in_signature='ssb',out_signature='s',sender_keyword='sender',async_callbacks=('success','failure'))
    def SetChannel(self,project,channel,confirmed,sender,success,failure):
        self.authorize(sender,'manage',lambda uid:self.agent.channel(str(project),str(channel),bool(confirmed)),success,failure)

    @dbus.service.method(NAME,in_signature='s',out_signature='s',sender_keyword='sender',async_callbacks=('success','failure'))
    def Download(self,ident,sender,success,failure):
        def download(uid):
            self.downloading=True
            return self.agent.download(str(ident))
        self.authorize(sender,'manage',download,success,failure)

    @dbus.service.method(NAME,in_signature='',out_signature='s',sender_keyword='sender')
    def CancelDownload(self,sender):
        # Same active administrator required; no cancellation during installation.
        authority=dbus.Interface(self.bus.get_object('org.freedesktop.PolicyKit1','/org/freedesktop/PolicyKit1/Authority'),'org.freedesktop.PolicyKit1.Authority')
        result=authority.CheckAuthorization(('system-bus-name',{'name':dbus.String(sender,variant_level=1)}),'com.etherneco.etherupdate.manage',{},dbus.UInt32(0),'',timeout=3)
        if not result[0]:raise dbus.DBusException('Authorization required',name=NAME+'.Denied')
        if self.agent and self.busy and any(t['state']=='Downloading' for t in self.state.get('history',[])):
            self.agent.cancel.set();return 'Cancellation requested'
        # State is cached before download; progress cannot be read through SQLite
        # on this thread. The explicit operation marker covers that interval.
        if self.agent and self.busy and getattr(self,'downloading',False):self.agent.cancel.set();return 'Cancellation requested'
        raise dbus.DBusException('No cancellable download',name=NAME+'.Rejected')

    @dbus.service.method(NAME,in_signature='s',out_signature='s',sender_keyword='sender',async_callbacks=('success','failure'))
    def PrepareInstall(self,ident,sender,success,failure):
        self.authorize(sender,'install',lambda uid:self.agent.prepare(str(ident),uid,self.safety()),success,failure)

    @dbus.service.method(NAME,in_signature='s',out_signature='s',sender_keyword='sender',async_callbacks=('success','failure'))
    def InstallApproved(self,approval,sender,success,failure):
        self.authorize(sender,'install',lambda uid:self.agent.install(str(approval),uid,self.safety(),self.inhibit),success,failure)

    def session(self):
        uid=int(self.agent.config.get('sessionUid',1000))
        return dbus.bus.BusConnection('unix:path=/run/user/%d/bus'%uid)

    def safety(self):
        def state(bus,component):
            name='com.etherneco.'+component+'1'
            value=json.loads(str(dbus.Interface(bus.get_object(name,'/com/etherneco/'+component+'1',introspect=False),name).GetState(timeout=3)))
            if not value.get('ready'):raise Rejected('Safety provider unavailable')
            return value
        try:
            bus=dbus.SystemBus(private=True);power=state(bus,'EtherPower')
            session=self.session();phone=state(session,'EtherPhone');camera=state(session,'EtherCamera')
            # Any unresolved/uncertain call remains a blocker.
            return dict(battery=power.get('telemetry',power.get('data',power)).get('capacity'),
                        charging=power.get('telemetry',power.get('data',power)).get('externalPower'),
                        callActive=bool(phone['calls']),recording=camera['recording'],criticalActivity=camera['busy'])
        except (dbus.DBusException,KeyError,ValueError):raise Rejected('Safety state unavailable; defer installation') from None

    @contextmanager
    def inhibit(self):
        bus=dbus.SystemBus(private=True)
        api=dbus.Interface(bus.get_object('org.freedesktop.login1','/org/freedesktop/login1',introspect=False),'org.freedesktop.login1.Manager')
        # EtherPower already checks logind's blocking inhibitors before suspend.
        fd=api.Inhibit('sleep:shutdown','EtherUpdate','Approved installation and recovery','block',timeout=3).take()
        try:yield
        finally:os.close(fd)


if __name__=='__main__':
    DBusGMainLoop(set_as_default=True)
    service=Service();GLib.MainLoop().run()
