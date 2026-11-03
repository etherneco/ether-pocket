#!/usr/bin/python3
"""One controlled policy owner; cached API, coarse samples and hardware events."""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
import json
import logging
import os
import signal
import socket
import time
from concurrent.futures import ThreadPoolExecutor
import dbus
import dbus.service
from dbus.mainloop.glib import DBusGMainLoop
from gi.repository import GLib
from power import Power, PowerError, PROFILES

NAME='com.etherneco.EtherPower1'
PATH='/com/etherneco/EtherPower1'


class Service(dbus.service.Object):
    def __init__(self, bus):
        super().__init__(dbus.service.BusName(NAME,bus),PATH)
        self.bus=bus
        self.pool=ThreadPoolExecutor(max_workers=1,thread_name_prefix='power')
        self.core=None
        self.owner=None
        self.pending=False
        self.authorizing=False
        self.dirty=False
        self.last_refresh=0
        self.event_timer=0
        self.timer=0
        self.histories={}
        self.data={'schemaVersion':1,'ready':False,'busy':True,'message':'Reading power interfaces'}
        self.sleep_state='awake'
        self.resume_pending=False
        self.session={}
        self.session_sender=None
        self.power_event_signatures={}
        self.process_cache={}
        bus.add_signal_receiver(self.hardware_event,signal_name='Changed',dbus_interface='com.etherneco.EtherHardware1',bus_name='com.etherneco.EtherHardware1')
        bus.add_signal_receiver(self.prepare_sleep,signal_name='PrepareForSleep',dbus_interface='org.freedesktop.login1.Manager',bus_name='org.freedesktop.login1')
        bus.add_signal_receiver(self.owner_changed,signal_name='NameOwnerChanged',dbus_interface='org.freedesktop.DBus')
        self.hardware_signature=None
        try:
            self.netlink=socket.socket(socket.AF_NETLINK,socket.SOCK_DGRAM,15)
            self.netlink.setblocking(False);self.netlink.bind((os.getpid(),1))
            GLib.io_add_watch(self.netlink.fileno(),GLib.IO_IN,self.uevent)
        except OSError:
            self.data['eventWarning']='Kernel events unavailable; coarse telemetry sampling remains active'
        self.work(initialize=True)

    @dbus.service.signal(NAME,signature='s')
    def Changed(self,document):pass

    @dbus.service.signal(NAME,signature='ss')
    def Event(self,kind,document):pass

    @dbus.service.signal(NAME,signature='ss')
    def Notice(self,title,message):pass

    @dbus.service.method(NAME,in_signature='',out_signature='s')
    def GetState(self):return json.dumps(self.data)

    @dbus.service.method(NAME,in_signature='u',out_signature='s')
    def GetHistory(self,hours):
        if int(hours) not in (1,24,168,720):raise dbus.exceptions.DBusException('Invalid history range',name=NAME+'.Invalid')
        self.schedule_history(int(hours))
        return json.dumps({'schemaVersion':1,'hours':int(hours),'ready':int(hours) in self.histories,'samples':self.histories.get(int(hours),[])})

    @dbus.service.method(NAME,in_signature='',out_signature='')
    def Refresh(self):self.schedule()

    @dbus.service.method(NAME,in_signature='',out_signature='s',sender_keyword='sender',async_callbacks=('success','failure'))
    def GetProcessImpact(self,sender,success,failure):
        uid=int(self.bus.get_unix_user(sender));stamp=time.monotonic()
        self.process_cache={u:v for u,v in self.process_cache.items() if stamp-v[0]<300}
        if uid in self.process_cache and stamp-self.process_cache[uid][0]<20:
            success(self.process_cache[uid][1]);return
        if self.pending or self.authorizing or not self.core:
            failure(dbus.exceptions.DBusException('Power service busy',name=NAME+'.Busy'));return
        self.pending=True;self.publish()
        def worker():
            try:result=json.dumps(self.core.process_impact(uid));self.process_cache[uid]=(time.monotonic(),result);error=None
            except Exception:result='{}';error='Process resource query failed'
            def finish():
                self.pending=False;self.publish()
                if error:failure(dbus.exceptions.DBusException(error,name=NAME+'.Failed'))
                else:success(result)
                return False
            GLib.idle_add(finish)
        self.pool.submit(worker)

    def schedule(self,*args):
        self.dirty=True
        if not self.event_timer:self.event_timer=GLib.timeout_add_seconds(5,self.flush)

    def flush(self):
        self.event_timer=0
        if self.pending or self.authorizing or time.monotonic()-self.last_refresh<5:
            self.event_timer=GLib.timeout_add_seconds(5,self.flush)
        elif self.dirty:
            self.dirty=False;self.work()
        return False

    def tick(self):
        if not self.pending and not self.authorizing:self.work()
        return True

    def uevent(self,*args):
        for _ in range(64):
            try:payload,addr=self.netlink.recvfrom(8192)
            except BlockingIOError:break
            if addr[0]!=0:continue
            values=dict(s.split('=',1) for s in payload.decode(errors='replace').split('\0') if '=' in s)
            if values.get('SUBSYSTEM')=='power_supply':
                name=values.get('POWER_SUPPLY_NAME',values.get('DEVPATH',''))
                keys=('POWER_SUPPLY_STATUS','POWER_SUPPLY_CAPACITY','POWER_SUPPLY_HEALTH','POWER_SUPPLY_PRESENT','POWER_SUPPLY_ONLINE','POWER_SUPPLY_PD_ACTIVE','POWER_SUPPLY_REAL_TYPE','POWER_SUPPLY_TYPEC_MODE')
                signature=tuple(values.get(k) for k in keys)
                if self.power_event_signatures.get(name)==signature:continue
                self.power_event_signatures[name]=signature
            if values.get('SUBSYSTEM') in ('power_supply','thermal','backlight','drm'):
                self.schedule()
        return True

    def hardware_event(self,document):
        try:
            data=json.loads(str(document))
            signature=(data.get('ready'),tuple((c['id'],c.get('supported'),c.get('operational')) for c in data.get('capabilities',[]) if c['id'].startswith(('power.','display.','sensors.light'))))
            if signature!=self.hardware_signature:self.hardware_signature=signature;self.schedule()
        except (ValueError,KeyError):pass

    def owner_changed(self,name,old,new):
        if str(name)==self.session_sender and not new:
            self.session={};self.session_sender=None;self.publish()
        if str(name)=='com.etherneco.EtherHardware1':self.schedule()

    def prepare_sleep(self,sleeping):
        self.sleep_state='preparing' if sleeping else 'resuming'
        if sleeping:self.Event('SuspendRequested',json.dumps({'timestamp':time.time(),'owner':'systemd-logind','servicesRestarted':False}))
        else:self.resume_pending=True
        self.schedule()

    def resume_checks(self):
        result={'timestamp':time.time(),'servicesRestarted':False,'scope':'Read-only service/capability metadata; physical input, acoustic routing and external transmission are not certified'}
        try:
            name='com.etherneco.EtherHardware1';path='/com/etherneco/EtherHardware1'
            old=json.loads(str(self.owner_call(name,path,name,'GetState'))).get('generation',0)
            try:self.owner_call(name,path,name,'Refresh','all')
            except dbus.DBusException:pass
            deadline=time.monotonic()+10
            while True:
                state=json.loads(str(self.owner_call(name,path,name,'GetState')))
                if state.get('generation',0)>old and not state.get('busy') or time.monotonic()>=deadline:break
                time.sleep(.25)
            result['freshInventory']=state.get('generation',0)>old
            result['capabilities']=[c for c in state.get('capabilities',[]) if c['id'] in ('wifi.client','bluetooth.adapter','cellular.data','display.external','display.touch','audio.microphone','audio.speaker','usb.gadget')]
        except (dbus.DBusException,ValueError):result['freshInventory']=False
        result['services']={}
        for unit in ('NetworkManager.service','ModemManager.service','bluetooth.service','ssh.service','ethershare.service','ethermobile-data.service'):
            try:
                path=self.owner_call('org.freedesktop.systemd1','/org/freedesktop/systemd1','org.freedesktop.systemd1.Manager','GetUnit',unit)
                value=self.owner_call('org.freedesktop.systemd1',path,'org.freedesktop.DBus.Properties','Get','org.freedesktop.systemd1.Unit','ActiveState')
                result['services'][unit]=str(value)
            except dbus.DBusException:result['services'][unit]='unavailable'
        self.resume_pending=False;self.sleep_state='awake'
        self.core.emit('ResumeCompleted',result)
        return result

    def owner_call(self,name,path,interface,method,*args):
        return getattr(dbus.Interface(self.owner.get_object(name,path,introspect=False),interface),method)(*args,timeout=8)

    def hardware(self):
        try:
            doc=json.loads(str(self.owner_call('com.etherneco.EtherHardware1','/com/etherneco/EtherHardware1','com.etherneco.EtherHardware1','GetCapabilities')))
            return {'ready':bool(doc.get('ready')),'capabilities':[c for c in doc.get('capabilities',[]) if c['id'].startswith(('power.','display.','sensors.'))]}
        except (ValueError,dbus.DBusException):return {'ready':False,'capabilities':[],'error':'EtherHardware capability registry unavailable'}

    def competitors(self):
        active=[]
        for unit in ('power-profiles-daemon.service','tlp.service','tuned.service'):
            try:
                path=self.owner_call('org.freedesktop.systemd1','/org/freedesktop/systemd1','org.freedesktop.systemd1.Manager','GetUnit',unit)
                state=self.owner_call('org.freedesktop.systemd1',path,'org.freedesktop.DBus.Properties','Get','org.freedesktop.systemd1.Unit','ActiveState')
                if str(state)=='active':active.append(unit)
            except dbus.DBusException:pass
        if active:raise PowerError('Another CPU power manager is active: '+', '.join(active))

    def authorize(self,sender,action,operation,success,failure):
        if self.authorizing:
            failure(dbus.exceptions.DBusException('Power service busy; retry shortly',name=NAME+'.Busy'));return
        if self.pending:
            self.authorizing=True;self.publish();deadline=time.monotonic()+15
            def retry():
                if time.monotonic()>deadline:
                    self.authorizing=False;self.publish();failure(dbus.exceptions.DBusException('Power collection timed out',name=NAME+'.Busy'));return False
                if self.pending:return True
                self.authorizing=False;self.authorize(sender,action,operation,success,failure);return False
            GLib.timeout_add(100,retry);return
        self.authorizing=True
        authority=dbus.Interface(self.bus.get_object('org.freedesktop.PolicyKit1','/org/freedesktop/PolicyKit1/Authority'),'org.freedesktop.PolicyKit1.Authority')
        def denied(error):self.authorizing=False;self.publish();failure(error)
        def allowed(result):
            self.authorizing=False
            if not result[0]:self.publish();failure(dbus.exceptions.DBusException('Authorization required',name=NAME+'.PermissionDenied'))
            else:self.work(operation=operation,success=success,failure=failure)
        authority.CheckAuthorization(('system-bus-name',{'name':dbus.String(sender,variant_level=1)}),action,{},dbus.UInt32(1),'',reply_handler=allowed,error_handler=denied,timeout=60)

    @dbus.service.method(NAME,in_signature='ss',out_signature='',sender_keyword='sender',async_callbacks=('success','failure'))
    def ApplyProfile(self,profile,custom,sender,success,failure):
        if profile not in PROFILES or len(custom)>4096:
            failure(dbus.exceptions.DBusException('Invalid profile',name=NAME+'.Invalid'));return
        try:values=json.loads(str(custom)) if custom else None
        except ValueError:failure(dbus.exceptions.DBusException('Invalid custom JSON',name=NAME+'.Invalid'));return
        def apply():
            self.competitors();self.core.apply(str(profile),values)
        self.authorize(sender,'com.etherneco.etherpower.manage',apply,success,failure)

    @dbus.service.method(NAME,in_signature='s',out_signature='',sender_keyword='sender',async_callbacks=('success','failure'))
    def Configure(self,document,sender,success,failure):
        if len(document)>4096:failure(dbus.exceptions.DBusException('Configuration too large',name=NAME+'.Invalid'));return
        try:changes=json.loads(str(document))
        except ValueError:failure(dbus.exceptions.DBusException('Invalid JSON',name=NAME+'.Invalid'));return
        self.authorize(sender,'com.etherneco.etherpower.manage',lambda:self.core.configure(changes),success,failure)

    @dbus.service.method(NAME,in_signature='',out_signature='',sender_keyword='sender',async_callbacks=('success','failure'))
    def RestoreOriginal(self,sender,success,failure):
        def restore():self.competitors();self.core.restore_original()
        self.authorize(sender,'com.etherneco.etherpower.manage',restore,success,failure)

    @dbus.service.method(NAME,in_signature='s',out_signature='',sender_keyword='sender',async_callbacks=('success','failure'))
    def PowerAction(self,action,sender,success,failure):
        if action not in ('suspend','shutdown','restart'):
            failure(dbus.exceptions.DBusException('Invalid action',name=NAME+'.Invalid'));return
        def perform():
            if action=='suspend' and not self.core.suspend()['verified']:
                raise PowerError(self.core.suspend()['error'])
            inhibitors=self.owner_call('org.freedesktop.login1','/org/freedesktop/login1','org.freedesktop.login1.Manager','ListInhibitors')
            required='sleep' if action=='suspend' else 'shutdown'
            if any(required in str(row[0]).split(':') and str(row[4])=='block' for row in inhibitors):
                raise PowerError('A blocking '+required+' inhibitor is active; nothing was stopped')
            self.core.emit('SuspendRequested' if action=='suspend' else 'PowerActionRequested',{'action':str(action),'owner':'systemd-logind'})
            # logind performs existing application delay/inhibitor coordination.
            method={'suspend':'Suspend','shutdown':'PowerOff','restart':'Reboot'}[str(action)]
            self.owner_call('org.freedesktop.login1','/org/freedesktop/login1','org.freedesktop.login1.Manager',method,dbus.Boolean(True))
        self.authorize(sender,'com.etherneco.etherpower.power-action',perform,success,failure)

    @dbus.service.method(NAME,in_signature='s',out_signature='',sender_keyword='sender')
    def ReportDisplayState(self,document,sender):
        if len(document)>2048:raise dbus.exceptions.DBusException('Display state too large',name=NAME+'.Invalid')
        # Only an active local graphical user may report its own display policy.
        uid=int(self.bus.get_unix_user(sender))
        pid=int(dbus.Interface(self.bus.get_object('org.freedesktop.DBus','/org/freedesktop/DBus'),'org.freedesktop.DBus').GetConnectionUnixProcessID(sender))
        manager=dbus.Interface(self.bus.get_object('org.freedesktop.login1','/org/freedesktop/login1'),'org.freedesktop.login1.Manager')
        try:
            path=manager.GetSessionByPID(pid,timeout=3)
            props=dbus.Interface(self.bus.get_object('org.freedesktop.login1',path),'org.freedesktop.DBus.Properties').GetAll('org.freedesktop.login1.Session',timeout=3)
            if not props.get('Active') or props.get('Remote') or int(props.get('User',(0,))[0])!=uid:
                # Managed shell stages may inherit an SSH launcher cgroup. The
                # bus UID must still own the active local graphical session.
                user=manager.GetUser(dbus.UInt32(uid),timeout=3)
                display=dbus.Interface(self.bus.get_object('org.freedesktop.login1',user),'org.freedesktop.DBus.Properties').Get('org.freedesktop.login1.User','Display',timeout=3)
                props=dbus.Interface(self.bus.get_object('org.freedesktop.login1',display[1]),'org.freedesktop.DBus.Properties').GetAll('org.freedesktop.login1.Session',timeout=3)
            if not props.get('Active') or props.get('Remote') or str(props.get('Type')) not in ('x11','wayland'):raise ValueError()
            if int(props.get('User',(0,))[0])!=uid:raise ValueError()
            data=json.loads(str(document))
            if set(data)-{'timeoutSeconds','brightnessPercent','screenBlank','externalConnected','policy','error'}:raise ValueError()
            if data.get('timeoutSeconds') not in (0,15,30,60,120,300):raise ValueError()
        except (dbus.DBusException,ValueError):raise dbus.exceptions.DBusException('Active local display session required',name=NAME+'.PermissionDenied')
        self.session=dict(data,uid=uid,verifiedAt=time.time());self.session_sender=str(sender)
        self.publish()

    def schedule_history(self,hours):
        if hours in self.histories or self.pending or not self.core:return
        self.work(history=hours)

    def publish(self):
        self.data['busy']=self.pending or self.authorizing
        self.data['sessionDisplay']=self.session
        self.Changed(json.dumps(self.data))

    def work(self,operation=None,initialize=False,history=None,success=None,failure=None):
        if self.pending:return
        self.pending=True;self.publish()
        def worker():
            error=None
            try:
                if self.core is None:
                    self.owner=dbus.SystemBus(private=True)
                    self.core=Power('/var/lib/etherpower')
                    self.core.guard=self.competitors
                    if self.core.requested:
                        self.competitors();self.core.apply(self.core.requested,persist=False)
                if operation:operation()
                if history:
                    self.histories[history]=self.core.store.history(history)
                    data=dict(self.data)
                else:
                    self.core.registry=self.hardware()
                    data=self.core.refresh(persist=bool(operation) or initialize)
                    if self.resume_pending:data['resumeDiagnostics']=self.resume_checks()
                    elif 'resumeDiagnostics' in self.data:data['resumeDiagnostics']=self.data['resumeDiagnostics']
                    self.histories.clear()
                    self.last_refresh=time.monotonic()
                events=list(self.core.events);self.core.events.clear()
            except Exception as e:
                error=str(e) if isinstance(e,PowerError) else 'Power query/operation failed; inspect permissions and current interfaces'
                logging.error('Power operation failed: %s',type(e).__name__)
                if self.core:
                    self.core.error=error
                    try:data=dict(self.core.refresh(),message=error)
                    except Exception:data=dict(self.data,ready=False,message=error)
                else:data=dict(self.data,ready=False,message=error)
                events=[]
            def finish():
                self.data=data;self.pending=False
                self.publish()
                interval=self.core.store.config['monitorSeconds'] if self.core else 60
                if not self.timer or getattr(self,'interval',None)!=interval:
                    if self.timer:GLib.source_remove(self.timer)
                    self.interval=interval;self.timer=GLib.timeout_add_seconds(interval,self.tick)
                for event in events:
                    self.Event(event['kind'],json.dumps(event))
                    if event['kind'].startswith(('Battery','Thermal')):self.Notice('EtherPower',event['kind']+': '+json.dumps(event['data']))
                if error and failure:failure(dbus.exceptions.DBusException(error,name=NAME+'.Failed'))
                elif success:success()
                return False
            GLib.idle_add(finish)
        self.pool.submit(worker)


if __name__=='__main__':
    logging.basicConfig(level=logging.INFO)
    DBusGMainLoop(set_as_default=True)
    loop=GLib.MainLoop();service=Service(dbus.SystemBus())
    signal.signal(signal.SIGTERM,lambda *a:loop.quit())
    signal.signal(signal.SIGINT,lambda *a:loop.quit())
    loop.run();service.pool.shutdown(wait=True)
