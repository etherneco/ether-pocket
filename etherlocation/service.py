#!/usr/bin/python3
"""Session-owned EtherLocation API. Coordinates are never broadcast."""
import functools
import json
import os
from pathlib import Path
import signal
import time
import dbus
import dbus.service
from dbus.mainloop.glib import DBusGMainLoop
from gi.repository import GLib
from core import Rejected,Permissions,History,Geofences,position,select,age,disclose,options,atomic,number
from identity import caller,foreground
from gnss import Gnss
from providers import Gpsd,GeoClue
from ip_provider import IpProvider,endpoint,disclose_ip
import threading

NAME='com.etherneco.EtherLocation1';PATH='/com/etherneco/EtherLocation1'
def dump(value):return json.dumps(value,allow_nan=False,separators=(',',':'))
def document(value):
    if len(value)>16384:raise Rejected('Request too large')
    data=json.loads(str(value))
    if not isinstance(data,dict):raise Rejected('Expected object')
    return data
def guarded(fn):
    @functools.wraps(fn)
    def call(*a,**kw):
        try:return fn(*a,**kw)
        except (ValueError,OSError,KeyError,TypeError) as e:
            raise dbus.exceptions.DBusException(str(e)[:300],name=NAME+'.Rejected')
    return call

class Service(dbus.service.Object):
    def __init__(self):
        self.bus=dbus.SessionBus();self.system=dbus.SystemBus()
        self.name=dbus.service.BusName(NAME,self.bus,do_not_queue=True)
        super().__init__(self.bus,PATH)
        self.directory=Path.home()/'.local/share/etherlocation';self.directory.mkdir(mode=0o700,parents=True,exist_ok=True)
        os.chmod(self.directory,0o700)
        self.config=dict(enabled=False,accuracy='balanced',history=False,retention=7,grid=10000,backend='qualcomm-loc',networkAuthorized=False)
        self.policy=Permissions();self.history=History(self.directory/'history.sqlite');self.fences=Geofences()
        self.last=None;self.live=None;self.manual=None;self.satellites=None;self.state='Disabled';self.error=''
        self.sleeping=False;self.saver=False;self.timer=0;self.test_until=0;self.notice_errors=set()
        self.gnss=Gnss(self.on_position,self.on_status,self.on_satellites)
        try:
            p=self.directory/'settings.json'
            if p.exists():
                data=json.loads(p.read_text());self.validate_config(data);self.config.update(data)
            p=self.directory/'zones.json'
            if p.exists():
                for key,data in json.loads(p.read_text()).items():self.fences.put(key,data)
        except (OSError,ValueError,KeyError,TypeError):self.config['enabled']=False;self.error='Invalid stored settings; service disabled'
        self.history.enabled=self.config['history'];self.history.retention=self.config['retention']
        self.ip=IpProvider(self.directory/'ip-cache.json');self.ip_busy=False
        self.network_live=None;self.network_adapter=None;self.network_state='Disabled';self.network_retry=0
        self.gnss=self.provider()
        self.bus.add_signal_receiver(self.owner_changed,signal_name='NameOwnerChanged',dbus_interface='org.freedesktop.DBus')
        self.bus.add_signal_receiver(self.lock_changed,signal_name='Changed',dbus_interface='com.etherneco.EtherLock1',bus_name='com.etherneco.EtherLock1')
        self.system.add_signal_receiver(self.suspend,signal_name='PrepareForSleep',dbus_interface='org.freedesktop.login1.Manager',bus_name='org.freedesktop.login1')
        self.system.add_signal_receiver(self.power_changed,signal_name='Changed',dbus_interface='com.etherneco.EtherPower1',bus_name='com.etherneco.EtherPower1')
        try:
            if self.system.name_has_owner('com.etherneco.EtherPower1'):
                api=dbus.Interface(self.system.get_object('com.etherneco.EtherPower1','/com/etherneco/EtherPower1',introspect=False),'com.etherneco.EtherPower1')
                self.power_changed(api.GetState(timeout=2))
        except dbus.DBusException:pass
        if self.config['enabled']:self.state='Idle'

    def provider(self):
        if self.config['backend']=='gpsd':return Gpsd(self.on_position,self.on_status,self.on_satellites)
        if self.config['backend']=='geoclue' and self.config['networkAuthorized']:
            return GeoClue(self.system,True,self.on_position,self.on_status,self.on_satellites)
        return Gnss(self.on_position,self.on_status,self.on_satellites)

    def admin(self,sender):
        pid,app=caller(self.bus,sender)
        if app!='ethershell':raise Rejected('Only the installed EtherShell permission coordinator may manage location')
        if not self.unlocked():raise Rejected('Unlock EtherLock to manage location')
        return app

    def unlocked(self):
        try:
            if not self.bus.name_has_owner('com.etherneco.EtherLock1'):return False
            api=dbus.Interface(self.bus.get_object('com.etherneco.EtherLock1','/com/etherneco/EtherLock1',introspect=False),'com.etherneco.EtherLock1')
            s=json.loads(str(api.GetState(timeout=1)))
            return s.get('ready') is True and s.get('locked') is False and s.get('phase')=='unlocked'
        except (dbus.DBusException,ValueError):return False

    def auth(self,sender,opts):
        pid,app=caller(self.bus,sender)
        if not self.config['enabled'] or self.sleeping:raise Rejected('Location disabled or suspended')
        precision=self.policy.check(sender,app,opts,foreground(app),not self.unlocked())
        return app,precision

    def snapshot(self):
        return dict(schemaVersion=1,ready=True,config=self.config,fixStatus=self.state,locked=not self.unlocked(),
            active=self.gnss.active,provider=self.config['backend'] if self.gnss.active else None,
            live=bool(select([self.live,getattr(self,'network_live',None)])),accuracy=(select([self.live,getattr(self,'network_live',None)]) or {}).get('accuracy'),
            lastUpdate=self.last['timestamp'] if self.last else None,
            activeApplications=sorted(set(s['app'] for s in self.policy.subscriptions.values())),
            pendingRequests=len(self.policy.requests),lastError=self.error,ttff=self.gnss.ttff,
            satellitesVisible=len(self.satellites) if self.satellites is not None else None,
            satellitesUsed=sum(bool(s.get('used')) for s in self.satellites) if self.satellites is not None and self.config['backend']=='gpsd' else self.live.get('satellitesUsed') if self.live and age(self.live)<=30 else None,
            networkProvider='GeoClue explicitly authorised; its configured sources may use the network' if self.config.get('networkAuthorized') else 'Disabled; no positioning observations uploaded',
            networkFallbackState=getattr(self,'network_state','Disabled'),
            internalGnss='Session-capable; operational only after a verified real fix',
            batterySaver=self.saver,suspended=self.sleeping)

    @dbus.service.signal(NAME,signature='s')
    def Changed(self,status):pass
    def changed(self):self.Changed(dump(self.snapshot()))

    @dbus.service.method(NAME,in_signature='',out_signature='s',sender_keyword='sender')
    @guarded
    def GetState(self,sender):caller(self.bus,sender);return dump(self.snapshot())

    @dbus.service.method(NAME,in_signature='',out_signature='s',sender_keyword='sender')
    @guarded
    def GetCapabilities(self,sender):
        caller(self.bus,sender)
        return dump(dict(apiVersion=1,gnss='qualcomm-loc-qrtr',minimumInterval=5,maximumSubscriptions=16,
            precise=True,approximate=True,history=True,geofencing=True,offlineMaps='raster MBTiles',
            network=True,externalGnss='gpsd; explicitly configured local receiver only',
            backgroundDefault=False,browser='Origin-aware API available; browser bridge not installed',
            routing=False,turnByTurn=False,privacyBoundary='Managed API only; same UID/X11/direct QRTR access is not isolated'))

    @dbus.service.method(NAME,in_signature='s',out_signature='s',sender_keyword='sender')
    @guarded
    def RequestPermission(self,data,sender):
        pid,app=caller(self.bus,sender);opts=options(document(data))
        if opts['origin'] and app!='etherbrowser':raise Rejected('No trusted browser bridge installed')
        if not foreground(app) or not self.unlocked():raise Rejected('Unlock and focus requesting application')
        token=self.policy.request(sender,app,opts);self.ensure_timer();self.changed()
        self.notice('Location permission requested','Open Settings → Location to review the request.')
        return token

    @dbus.service.method(NAME,in_signature='',out_signature='s',sender_keyword='sender')
    @guarded
    def GetPermissionRequests(self,sender):
        self.admin(sender)
        return dump([dict(token=k,app=r['app'],options=r['options']) for k,r in self.policy.requests.items()])

    @dbus.service.method(NAME,in_signature='sssb',out_signature='s',sender_keyword='sender')
    @guarded
    def ResolvePermission(self,token,policy,precision,background,sender):
        self.admin(sender);self.policy.resolve(str(token),str(policy),str(precision),bool(background));self.changed();return dump(self.snapshot())

    @dbus.service.method(NAME,in_signature='ss',out_signature='s',sender_keyword='sender')
    @guarded
    def RevokePermission(self,app,origin,sender):
        self.admin(sender);self.policy.revoke(str(app),str(origin));self.reconcile();self.changed();return dump(self.snapshot())

    @dbus.service.method(NAME,in_signature='s',out_signature='s',sender_keyword='sender')
    @guarded
    def GetPermissionState(self,origin,sender):
        pid,app=caller(self.bus,sender);g=self.policy.grants.get((app,str(origin)))
        return dump(g or dict(policy='ask-every-time'))

    def location(self,sender,data,cached=False):
        opts=options(document(data));app,precision=self.auth(sender,opts)
        p=self.last if cached else select([self.live,getattr(self,'network_live',None)],opts['precision']=='precise',opts['maxAge'])
        active=self.gnss.active or bool(getattr(self,'network_adapter',None) and self.network_adapter.active)
        if not p or age(p)>opts['maxAge'] or (not cached and not active):raise Rejected('No acceptable real fix; use StartUpdates to request positioning')
        return dump(disclose(p,precision,self.config['grid'],cached=cached))

    @dbus.service.method(NAME,in_signature='s',out_signature='s',sender_keyword='sender')
    @guarded
    def GetLocation(self,data,sender):return self.location(sender,data)

    @dbus.service.method(NAME,in_signature='s',out_signature='s',sender_keyword='sender')
    @guarded
    def GetLastKnownLocation(self,data,sender):return self.location(sender,data,True)

    @dbus.service.method(NAME,in_signature='s',out_signature='s',sender_keyword='sender')
    @guarded
    def StartUpdates(self,data,sender):
        opts=options(document(data));app,precision=self.auth(sender,opts)
        token=self.policy.subscribe(sender,app,opts);self.ensure_timer();self.reconcile();self.changed();return token

    @dbus.service.method(NAME,in_signature='s',out_signature='',sender_keyword='sender')
    @guarded
    def StopUpdates(self,token,sender):caller(self.bus,sender);self.policy.stop(sender,str(token));self.reconcile();self.changed()

    @dbus.service.method(NAME,in_signature='s',out_signature='s',sender_keyword='sender')
    @guarded
    def ReadUpdate(self,token,sender):
        caller(self.bus,sender);self.policy.expire()
        s=self.policy.subscriptions.get(str(token))
        if not s or s['owner']!=sender:raise Rejected('Unknown or expired subscription')
        now=time.monotonic()
        if now<s['next']:raise Rejected('Update interval not elapsed')
        s['next']=now+s['options']['interval']
        return self.location(sender,dump(s['options']))

    @dbus.service.method(NAME,in_signature='',out_signature='s',sender_keyword='sender')
    @guarded
    def SubscribeToStatus(self,sender):return self.GetState(sender)

    @dbus.service.method(NAME,in_signature='s',out_signature='s',sender_keyword='sender',async_callbacks=('reply','error'))
    def GetIpLocation(self,data,sender,reply,error):
        # Per-call explicit consent, plus the same app permission/lock boundary as GNSS.
        # Endpoint and consent are never inferred from enabling ordinary location.
        def failure(e):error(dbus.exceptions.DBusException(str(e)[:200],name=NAME+'.Rejected'))
        try:
            row=document(data)
            if set(row)-{'endpoint','consent','options'} or row.get('consent') is not True:raise Rejected('Explicit IP service consent required')
            opts=options(row.get('options',{}));self.auth(sender,opts);url=endpoint(row['endpoint'])
            if self.ip_busy:raise Rejected('IP provider request already running')
            self.ip_busy=True
        except Exception as e:failure(e);return
        def complete(result,problem):
            self.ip_busy=False
            try:
                app,precision=self.auth(sender,opts)  # Revocation, focus, lock and suspend may change in flight.
                if problem:raise Rejected(problem)
                reply(dump(disclose_ip(result,precision,self.config['grid'])))
            except Exception as e:failure(e)
            return False
        def work():
            try:result=self.ip.lookup(url,True);problem=None
            except Exception as e:result=None;problem=str(e)
            GLib.idle_add(complete,result,problem)
        threading.Thread(target=work,daemon=True).start()

    @dbus.service.method(NAME,in_signature='',out_signature='s',sender_keyword='sender')
    @guarded
    def GetProviderStatus(self,sender):return self.GetState(sender)

    def validate_config(self,data):
        if set(data)-set(self.config):raise Rejected('Unknown configuration')
        for k in ('enabled','history','networkAuthorized'):
            if k in data and type(data[k]) is not bool:raise Rejected('Invalid switch')
        if 'accuracy' in data and data['accuracy'] not in ('high','balanced','saving'):raise Rejected('Invalid accuracy mode')
        if 'retention' in data:number(data['retention'],1,90)
        if 'grid' in data:number(data['grid'],1000,100000)
        if data.get('backend',self.config['backend']) not in ('qualcomm-loc','gpsd','geoclue'):raise Rejected('Invalid backend')
        if data.get('backend',self.config['backend'])=='geoclue' and not data.get('networkAuthorized',self.config['networkAuthorized']):raise Rejected('Separate online positioning authorisation required')

    @dbus.service.method(NAME,in_signature='s',out_signature='s',sender_keyword='sender')
    @guarded
    def Configure(self,data,sender):
        self.admin(sender);data=document(data);self.validate_config(data)
        backend_changed=any(k in data and data[k]!=self.config[k] for k in ('backend','networkAuthorized'))
        if backend_changed and (self.gnss.active or self.gnss.stopping):raise Rejected('Disable location and wait for provider shutdown before changing backend')
        settings=dict(self.config,**data);atomic(self.directory/'settings.json',settings);self.config=settings
        self.history.enabled=settings['history'];self.history.retention=settings['retention']
        if backend_changed:self.gnss=self.provider()
        if not settings['enabled']:self.test_until=0;self.live=None;self.policy.subscriptions.clear();self.fences.states.clear()
        if self.history.path.exists():
            with self.history.db() as db:self.history.prune(db,time.time())
        if data.get('enabled') is True and self.state in ('Error','Unsupported'):self.state='Idle';self.error=''
        self.reconcile();self.changed();return dump(self.snapshot())

    @dbus.service.method(NAME,in_signature='',out_signature='s',sender_keyword='sender')
    @guarded
    def GetManagement(self,sender):
        self.admin(sender)
        return dump(dict(permissions=[dict(app=k[0],origin=k[1],**v) for k,v in self.policy.grants.items()],
            requests=[dict(token=k,app=r['app'],options=r['options']) for k,r in self.policy.requests.items()],
            permissionHistory=self.policy.audit,zones=self.fences.zones,satellites=self.satellites,
            location=disclose(self.live or self.last,'precise',cached=not bool(self.live and age(self.live)<=30 and self.gnss.active)),
            history=self.history.entries()[:500]))

    @dbus.service.method(NAME,in_signature='s',out_signature='s',sender_keyword='sender')
    @guarded
    def GetHistoryForMap(self,data,sender):
        opts=options(document(data));app,precision=self.auth(sender,opts)
        if not self.unlocked():raise Rejected('Unlock to view history')
        if app!='etherlocation':raise Rejected('History map access is restricted to the native viewer')
        return dump(dict(history=[disclose(p,precision,self.config['grid'],cached=True) for p in self.history.entries()[:500]]))

    @dbus.service.method(NAME,in_signature='ss',out_signature='s',sender_keyword='sender')
    @guarded
    def ManageZone(self,id,data,sender):
        self.admin(sender)
        if str(data)=='delete':self.fences.zones.pop(str(id),None);self.fences.states.pop(str(id),None)
        else:self.fences.put(str(id),document(data))
        atomic(self.directory/'zones.json',self.fences.zones);return self.GetManagement(sender)

    @dbus.service.method(NAME,in_signature='s',out_signature='s',sender_keyword='sender')
    @guarded
    def DeleteHistory(self,ids,sender):
        self.admin(sender)
        if ids=='all':self.history.delete()
        else:
            rows=json.loads(str(ids))
            if not isinstance(rows,list) or len(rows)>10000:raise Rejected('Invalid history selection')
            self.history.delete(rows)
        return self.GetManagement(sender)

    @dbus.service.method(NAME,in_signature='s',out_signature='s',sender_keyword='sender')
    @guarded
    def ExportHistory(self,kind,sender):
        self.admin(sender)
        text=self.history.export(str(kind));suffix='.gpx' if kind=='GPX' else '.geojson'
        path=self.directory/('history-export'+suffix)
        fd=os.open(path,os.O_WRONLY|os.O_CREAT|os.O_TRUNC|os.O_NOFOLLOW,0o600)
        with os.fdopen(fd,'w') as f:f.write(text)
        return str(path)

    @dbus.service.method(NAME,in_signature='s',out_signature='s',sender_keyword='sender')
    @guarded
    def SetManualLocation(self,data,sender):
        self.admin(sender);p=document(data);p.update(provider='manual',timestamp=time.time(),fixType='user-supplied')
        p.setdefault('accuracy',10000);self.manual=position(p);return dump(disclose(self.manual,'precise'))

    @dbus.service.method(NAME,in_signature='u',out_signature='s',sender_keyword='sender')
    @guarded
    def TestGnss(self,seconds,sender):
        self.admin(sender);number(int(seconds),10,180)
        if not self.config['enabled']:raise Rejected('Enable location first')
        self.test_until=time.monotonic()+int(seconds);self.ensure_timer();self.reconcile();return dump(self.snapshot())

    @dbus.service.method(NAME,in_signature='b',out_signature='s',sender_keyword='sender')
    @guarded
    def ExportDiagnostics(self,includeCoordinates,sender):
        self.admin(sender);data=self.snapshot()
        # Error strings may contain provider messages; only allowlisted state is exported.
        data.pop('lastError',None);data.pop('activeApplications',None);data.pop('lastUpdate',None)
        data['coordinates']='redacted'
        if includeCoordinates and self.last:data['position']=disclose(self.last,'precise',cached=True)
        atomic(self.directory/'diagnostics.json',data);return str(self.directory/'diagnostics.json')

    def notice(self,title,body):
        try:
            dbus.Interface(self.bus.get_object('org.freedesktop.Notifications','/org/freedesktop/Notifications',introspect=False),'org.freedesktop.Notifications').Notify('EtherLocation',dbus.UInt32(0),'find-location',title,body,dbus.Array([],signature='s'),dbus.Dictionary({},signature='sv'),5000,timeout=1)
        except dbus.DBusException:pass

    def on_position(self,data):
        try:p=position(data)
        except (ValueError,KeyError):self.on_status('Error','GNSS emitted an invalid position');return
        if age(p)>30 or not self.config['enabled'] or self.sleeping:return
        self.live=p;self.last=p;self.state='Fix acquired';self.error=''
        if self.unlocked():self.history.record(p)
        for event in self.fences.evaluate(p):self.notice('Geofence '+event['event'],'An authorised local zone transition was detected.')
        self.changed()

    def on_status(self,state,error):
        self.state=state;self.error=error
        if state in ('Fix lost','Error'):self.live=None
        if error and error not in self.notice_errors:
            self.notice_errors.add(error)
            if len(self.notice_errors)<=8:self.notice('Location unavailable','Open Location diagnostics for details.')
        self.changed()
    def on_satellites(self,rows):self.satellites=rows;self.changed()

    def on_network_position(self,data):
        try:p=position(data)
        except (ValueError,KeyError):return
        if age(p)>30 or not self.config['enabled'] or not self.config['networkAuthorized'] or self.sleeping:return
        self.network_live=p
        self.last=select([self.live,p])
        if self.unlocked():self.history.record(self.last)
        self.changed()

    def on_network_status(self,state,error):
        self.network_state=state
        if state in ('Fix lost','Error'):self.network_live=None
        self.changed()

    def reconcile_network(self,wanted):
        wanted=wanted and self.config.get('networkAuthorized',False) and self.config.get('backend')!='geoclue'
        adapter=getattr(self,'network_adapter',None)
        if not wanted:
            if adapter:
                try:adapter.stop()
                except dbus.DBusException:pass
            self.network_adapter=None;self.network_live=None;self.network_state='Disabled'
        elif (not adapter or not adapter.active) and time.monotonic()>=self.network_retry:
            self.network_retry=time.monotonic()+60
            try:
                self.network_adapter=GeoClue(self.system,True,self.on_network_position,self.on_network_status)
                self.network_adapter.start(60)
            except (dbus.DBusException,OSError,ValueError):
                if self.network_adapter:
                    try:self.network_adapter.stop()
                    except dbus.DBusException:pass
                self.network_adapter=None;self.network_state='Unavailable';self.network_live=None

    def ensure_timer(self):
        if not self.timer:self.timer=GLib.timeout_add_seconds(2,self.tick)
    def reconcile(self):
        self.policy.expire()
        if self.sleeping:
            self.reconcile_network(False)
            if self.gnss.active:self.gnss.stop()
            self.live=None;self.satellites=None
            self.state='Idle' if self.config['enabled'] else 'Disabled'
            return
        for token,s in list(self.policy.subscriptions.items()):
            try:self.auth(s['owner'],s['options'])
            except (Rejected,dbus.DBusException,OSError):self.policy.stop(s['owner'],token)
        testing=self.test_until>time.monotonic() and self.unlocked()
        demand=bool(self.policy.subscriptions) or testing
        wanted=self.config['enabled'] and not self.sleeping and demand
        self.reconcile_network(wanted)
        if wanted and not self.gnss.active and not self.gnss.stopping and self.state not in ('Error','Unsupported'):
            interval=min([s['options']['interval'] for s in self.policy.subscriptions.values()] or [5])
            interval=max(interval,60 if self.saver or self.config['accuracy']=='saving' else 10 if self.config['accuracy']=='balanced' else 5)
            try:self.gnss.start(interval)
            except (OSError,dbus.DBusException):self.gnss.stop();self.on_status('Error','Selected location backend unavailable')
        if not wanted:
            if self.gnss.active:self.gnss.stop()
            self.live=None;self.satellites=None
            self.state='Disabled' if not self.config['enabled'] else self.state if self.state in ('Error','Unsupported') else 'Idle'
    def tick(self):
        before=dump(self.snapshot());self.reconcile()
        if self.live and age(self.live)>30:self.live=None;self.state='Fix lost'
        if getattr(self,'network_live',None) and age(self.network_live)>30:self.network_live=None;self.network_state='Fix lost'
        if dump(self.snapshot())!=before:self.changed()
        if not self.policy.subscriptions and not self.policy.requests and self.test_until<=time.monotonic():self.timer=0;return False
        return True
    def owner_changed(self,name,old,new):
        if str(name).startswith(':') and not new:
            owned=any(r['owner']==str(name) for pool in (self.policy.requests,self.policy.subscriptions) for r in pool.values()) or any(g.get('once')==str(name) for g in self.policy.grants.values())
            if owned:self.policy.disconnect(str(name));self.reconcile();self.changed()
        if str(name)=='com.etherneco.EtherLock1' and not new:self.lock_changed('')
    def lock_changed(self,*args):
        if not self.unlocked():
            self.test_until=0;self.fences.states.clear()
        self.reconcile();self.changed()
    def suspend(self,sleeping):
        self.sleeping=bool(sleeping);self.test_until=0;self.live=None;self.fences.states.clear()
        self.reconcile();self.changed()
    def power_changed(self,data):
        try:
            p=json.loads(str(data));saving=p.get('profile')=='power-saver' or (p.get('cpuTemperatureC') or 0)>=80 or (p.get('batteryTemperatureC') or 0)>=45
            if saving!=self.saver:
                self.saver=saving
                if self.gnss.active:self.gnss.stop(lambda:self.reconcile())
                self.changed()
        except (ValueError,AttributeError):pass

if __name__=='__main__':
    os.umask(0o077);DBusGMainLoop(set_as_default=True);loop=GLib.MainLoop();service=Service()
    def stop():service.reconcile_network(False);service.gnss.stop(loop.quit);return False
    GLib.unix_signal_add(GLib.PRIORITY_DEFAULT,signal.SIGTERM,stop)
    GLib.unix_signal_add(GLib.PRIORITY_DEFAULT,signal.SIGINT,stop)
    loop.run()
