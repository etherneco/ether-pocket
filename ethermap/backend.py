#!/usr/bin/python3
"""Private stdio worker for the native EtherMAP window, never a location daemon."""
import concurrent.futures
import json
import os
from pathlib import Path
import signal
import sys
import threading
import time

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'etherlocation'))
from core import Rejected, atomic, number
from client import Client
from maps import Maps
from domain import Tracks, coordinates, choose, distance
from network import Providers


class Application:
    def __init__(self):
        import dbus
        from gi.repository import GLib
        self.GLib=GLib;self.dbus=dbus
        self.root=Path.home()/'.local/share/ethermap';self.root.mkdir(parents=True,exist_ok=True,mode=0o700)
        self.settings=dict(history=False,background=False,precise=False,retention=7,ipConsent=False,ipEndpoint='',externalConsent=False,geocoder='',driving='',walking='',cycling='',region='auto',onlineTiles=False,tileTemplate='https://tile.openstreetmap.org/{z}/{x}/{y}.png',tileAttribution='© OpenStreetMap contributors · openstreetmap.org/copyright')
        try:
            stored=json.loads((self.root/'settings.json').read_text());self.validate(stored);self.settings.update(stored)
        except (OSError,ValueError,TypeError):pass
        self.tracks=Tracks(self.root/'tracks.sqlite');self.tracks.prune(self.settings['retention']);self.lastPrune=time.monotonic()
        self.maps=Maps(Path.home()/'.local/share/etherlocation/maps')
        # A small bundled ODbL map makes first launch useful without a network or fix.
        # It is a labelled dataset centre, never an inferred device location.
        sample=Path('/usr/share/ethermap/maps/westminster.mbtiles')
        if not self.maps.regions() and sample.is_file():
            try:self.maps.import_file(sample,True)
            except (OSError,ValueError):pass
        self.providers=Providers(self.root/'search-cache')
        self.client=None;self.location={};self.fix=None;self.ip=None;self.manual=None;self.last=None
        self.mode='Off';self.message='';self.results=[];self.route={};self.view=[];self.viewId=None;self.ipAttempt=0;self.stationary=False
        self.progress={};self.busy=False;self.pause=threading.Event();self.focused=True;self.locked=True;self.sleeping=False;self.retry=0;self.nextRead=0;self.started=0;self.interval=10
        self.pool=concurrent.futures.ThreadPoolExecutor(max_workers=1)
        self.bus=dbus.SessionBus()
        try:
            self.system=dbus.SystemBus()
            self.system.add_signal_receiver(self.suspend,signal_name='PrepareForSleep',dbus_interface='org.freedesktop.login1.Manager')
        except dbus.DBusException:self.system=None
        self.bus.add_signal_receiver(self.lock_event,signal_name='Changed',dbus_interface='com.etherneco.EtherLock1')
        self.inputBuffer=b'';os.set_blocking(sys.stdin.fileno(),False)
        self.GLib.io_add_watch(sys.stdin.fileno(),self.GLib.IO_IN|self.GLib.IO_HUP,self.input)
        self.GLib.timeout_add_seconds(2,self.tick)
        self.tick()

    def validate(self,data):
        if set(data)-set(self.settings):raise Rejected('Unknown Maps setting')
        for k in ('history','background','precise','ipConsent','externalConsent','onlineTiles'):
            if k in data and type(data[k]) is not bool:raise Rejected('Invalid Maps switch')
        if 'retention' in data:number(data['retention'],1,90)
        if 'region' in data and (not isinstance(data['region'],str) or data['region'] not in ('auto','online') and (len(data['region'])!=32 or any(c not in '0123456789abcdef' for c in data['region']))):raise Rejected('Invalid default map region')
        for k in ('ipEndpoint','geocoder','driving','walking','cycling','tileTemplate'):
            if k in data and data[k]:
                from ip_provider import endpoint
                endpoint(data[k])
        if 'tileTemplate' in data and not all('{'+x+'}' in data['tileTemplate'] for x in ('x','y','z')):raise Rejected('Tile template requires {z}/{x}/{y}')
        for k,v in data.items():
            if isinstance(v,str) and len(v)>2000:raise Rejected('Setting too long')

    def emit(self):
        p=choose([self.fix,self.ip,self.last])
        rows=self.tracks.list() if not self.locked else []
        track=self.tracks.active
        if track is not None and not self.locked:self.view=self.tracks.points(track)[-10000:]
        info=self.tracks.summary(track) if track is not None and not self.locked else dict(distance=0,duration=0,samples=0)
        payload=dict(ready=True,settings=self.settings,mode=self.mode,message=self.message,position=p if not self.locked else None,manual=self.manual if not self.locked else None,
                     location=self.location,locked=self.locked,interval=self.interval,recording=track is not None,paused=self.tracks.paused,interrupted=self.tracks.interrupted,
                     summary=info,elapsed=max(0,time.time()-self.started) if track is not None else 0,tracks=rows,trail=self.view if not self.locked else [],
                     regions=self.maps.regions(),places=self.tracks.places() if not self.locked else [],results=self.results if not self.locked else [],route=self.route if not self.locked else {},
                     busy=self.busy,progress=self.progress,offlineRouting=False)
        print(json.dumps(payload,allow_nan=False,separators=(',',':')),flush=True)

    def notify(self,title,persistent=False):
        try:
            api=self.dbus.Interface(self.bus.get_object('org.freedesktop.Notifications','/org/freedesktop/Notifications',introspect=False),'org.freedesktop.Notifications')
            self.notice=int(api.Notify('EtherMAP',self.dbus.UInt32(getattr(self,'notice',0)),'find-location',title,'Local tracking. Open EtherMAP for controls.',self.dbus.Array([],signature='s'),self.dbus.Dictionary({'resident':self.dbus.Boolean(persistent)},signature='sv'),0 if persistent else 5000,timeout=1))
        except self.dbus.DBusException:pass

    def opts(self):return dict(precision='precise' if self.settings['precise'] else 'approximate',background=self.settings['background'],interval=self.interval,timeout=3600,maxAge=30)

    def release(self):
        if self.client:
            try:self.client.stop()
            except self.dbus.DBusException:self.client.token=None
        self.fix=None;self.tracks.gap()

    def locked_state(self):
        try:
            api=self.dbus.Interface(self.bus.get_object('com.etherneco.EtherLock1','/com/etherneco/EtherLock1',introspect=False),'com.etherneco.EtherLock1')
            s=json.loads(str(api.GetState(timeout=1)))
            return not(s.get('ready') and s.get('locked') is False and s.get('phase')=='unlocked')
        except (ValueError,self.dbus.DBusException):return True

    def lock_event(self,*args):
        self.locked=self.locked_state()
        if self.locked:
            self.last=None;self.manual=None;self.ip=None;self.results=[];self.route={};self.view=[]
            if not self.settings['background']:self.release()
        self.emit()

    def suspend(self,sleeping):
        self.sleeping=bool(sleeping);self.release();self.retry=0
        self.message='Tracking suspended; no kernel wake guarantee' if sleeping else 'Resumed · waiting for a fresh location; track gap preserved'
        self.emit()

    def job(self, fn, done):
        if self.busy:raise Rejected('Wait for the current operation')
        self.busy=True;self.pause.clear()
        def finish(future):
            self.busy=False
            try:done(future.result())
            except Exception as e:self.message=str(e)[:300]
            self.emit();return False
        future=self.pool.submit(fn);future.add_done_callback(lambda f:self.GLib.idle_add(finish,f))

    def tick(self):
        try:
            if time.monotonic()-self.lastPrune>3600:self.tracks.prune(self.settings['retention']);self.lastPrune=time.monotonic()
            wasLocked=self.locked;self.locked=self.locked_state()
            if self.locked and not wasLocked:
                self.last=None;self.manual=None;self.ip=None;self.results=[];self.route={};self.view=[]
            if self.client is None:self.client=Client()
            self.location=json.loads(str(self.client.api.GetState(timeout=2)))
            active=self.mode!='Off' and not self.sleeping and (self.focused and not self.locked or self.settings['background'])
            # Stationary/thermal policy changes take effect through a renewed bounded subscription.
            wanted=60 if self.location.get('batterySaver') or self.stationary else 10
            if wanted!=self.interval:self.release();self.interval=wanted;self.retry=0
            if active:
                if not self.client.token and time.monotonic()>=self.retry:
                    self.retry=time.monotonic()+30;self.client.start(**self.opts());self.nextRead=0
                if self.client.token and time.monotonic()>=self.nextRead:
                    self.nextRead=time.monotonic()+self.interval
                    try:
                        self.fix=self.client.read();self.last=dict(self.fix,kind='last-known');self.message=''
                        self.stationary=0<=self.fix.get('speed',1)<0.5
                        self.tracks.sample(self.fix)
                    except self.dbus.DBusException as e:
                        self.fix=None;self.tracks.gap();self.message=str(e)[:200]
                        # A revoked/expired session is never silently renewed every tick.
                        if any(s in str(e).lower() for s in ('expired','unknown','permission','foreground','disabled','suspended')):self.release()
            else:self.release()
            if self.fix and time.time()-self.fix['timestamp']>30:self.fix=None;self.tracks.gap()
            if active and not self.fix and self.settings['ipConsent'] and self.settings['ipEndpoint'] and time.monotonic()-self.ipAttempt>900:
                self.request_ip()
        except (self.dbus.DBusException,ValueError,OSError) as e:
            self.message='EtherLocation unavailable · map viewing remains available';self.fix=None;self.tracks.gap()
        self.emit();return True

    def command(self,row):
        op=row['op'];a=row.get('args',{})
        if op=='focus':
            self.focused=bool(a.get('active'))
            if not self.focused and not self.settings['background']:self.release()
            return
        if op=='downloadPause':self.pause.set();return
        if self.locked:raise Rejected('Unlock EtherLock before using Maps controls')
        if op=='settings':
            self.validate(a);self.release();self.settings.update(a);atomic(self.root/'settings.json',self.settings);self.tracks.prune(self.settings['retention'])
            if a.get('history') is False:self.tracks.stop();self.mode='Off'
            if a.get('ipConsent') is False:self.ip=None
        elif op=='permission':
            if self.client is None:raise Rejected('EtherLocation unavailable')
            self.client.request_permission(**self.opts());self.message='Review EtherMAP in Settings → Location → Application permissions'
        elif op=='mode':
            mode=a['value']
            if mode not in ('Off','Follow Me','Track Route','Navigation'):raise Rejected('Unknown tracking mode')
            if mode=='Navigation' and not self.route:raise Rejected('Calculate a route first')
            if mode=='Track Route' and self.tracks.active is None:
                self.tracks.start(self.settings['history']);self.started=time.time();self.viewId=None
                self.notify('Tracking started',self.settings['background'])
            elif mode in ('Follow Me','Navigation') and self.tracks.active is not None:
                self.tracks.stop();self.notify('Tracking stopped')
            if mode=='Off':self.release();self.tracks.stop();self.notify('Tracking stopped')
            self.mode=mode;self.retry=0
        elif op=='pause':self.tracks.pause();self.release();self.mode='Off';self.notify('Tracking paused')
        elif op=='resume':self.tracks.resume();self.mode='Track Route';self.retry=0;self.notify('Tracking resumed',self.settings['background'])
        elif op=='manual':self.manual=dict(coordinates(a['latitude'],a['longitude']),kind='manual',provider='manual',timestamp=time.time());self.message='Manual map point · not a device position'
        elif op=='ip':
            if not self.settings['ipConsent']:raise Rejected('Read and enable IP fallback consent in Maps settings')
            if self.client is None:raise Rejected('EtherLocation unavailable')
            self.request_ip()
        elif op=='search':
            query=a['query'].strip();self.results=self.tracks.places(query)
            try:
                lat,lon=query.split(',');self.results.insert(0,dict(coordinates(lat,lon),name='Coordinates · user-supplied'));return
            except (ValueError,TypeError):pass
            # Optional licensed offline place table, using the installed region DBs.
            import sqlite3
            for region in self.maps.regions():
                path=self.maps.root/(region['id']+'.mbtiles')
                from contextlib import closing
                with closing(sqlite3.connect(path.resolve().as_uri()+'?mode=ro&immutable=1',uri=True)) as db:
                    try:
                        for name,lat,lon in db.execute('SELECT name,latitude,longitude FROM etherlocation_places WHERE name LIKE ? LIMIT 20',('%'+query+'%',)):
                            self.results.append(dict(coordinates(lat,lon),name=name,source='offline'))
                    except sqlite3.OperationalError:pass
            if a.get('online'):
                self.job(lambda:self.providers.search(query,self.settings['geocoder'],self.settings['externalConsent']),lambda rows:self.results.extend(rows) if self.settings['externalConsent'] and not self.locked else None)
        elif op=='route':
            mode=a['profile']
            if mode not in ('walking','cycling','driving'):raise Rejected('Unknown route profile')
            start=coordinates(a['startLatitude'],a['startLongitude']);end=coordinates(a['endLatitude'],a['endLongitude'])
            self.job(lambda:self.providers.route(start,end,self.settings[mode],self.settings['externalConsent']),lambda result:setattr(self,'route',result) if self.settings['externalConsent'] and not self.locked else None)
        elif op=='routeClear':self.route={}
        elif op=='savePlace':self.tracks.save_place(a['name'],a['latitude'],a['longitude'])
        elif op=='deletePlace':self.tracks.delete_place(a['id'])
        elif op=='viewTrack':self.viewId=a['id'];self.view=self.tracks.points(a['id'])[-10000:]
        elif op=='renameTrack':self.tracks.rename(a['id'],a['name'])
        elif op=='deleteTrack':
            self.tracks.delete(a['id'])
            if self.viewId==a['id']:self.view=[];self.viewId=None
        elif op=='export':
            target=self.root/('track-'+str(int(a['id']))+'.gpx')
            fd=os.open(target,os.O_WRONLY|os.O_CREAT|os.O_TRUNC|os.O_NOFOLLOW,0o600)
            with os.fdopen(fd,'w') as file:file.write(self.tracks.export(a['id']))
            self.message='Saved '+str(target)
        elif op=='import':
            path=Path(a['path']).expanduser()
            if path.stat().st_size>16*1024**2:raise Rejected('GPX exceeds 16 MiB')
            self.tracks.import_gpx(path.read_bytes())
        elif op=='importRegion':self.job(lambda:self.maps.import_file(a['path'],a.get('license') is True),lambda _:setattr(self,'message','Offline region imported'))
        elif op=='deleteRegion':self.maps.delete(a['id'])
        elif op=='download':
            def progress(data):self.GLib.idle_add(self.download_progress,data)
            def done(result):
                self.progress=result
                if result['state']=='complete':self.notify('Offline map download completed')
            self.job(lambda:self.maps.download(a['url'],a['sha256'],a.get('license') is True,progress,self.pause),done)
        elif op=='clear':
            self.tracks.clear()
            for f in (self.root/'search-cache').glob('*.json'):f.unlink()
            self.view=[];self.last=None;self.ip=None;self.manual=None;self.results=[]
        elif op=='diagnostics':
            self.message=json.dumps(dict(gnss=self.location.get('fixStatus'),backend=(self.location.get('config') or {}).get('backend'),wifiCell='GeoClue configured sources only; not independently attributable',ip='consented' if self.settings['ipConsent'] else 'disabled',interval=self.interval,offlineRegions=len(self.maps.regions()),offlineRouting=False,suspended=self.sleeping,lastError=self.location.get('lastError')))
        else:raise Rejected('Unknown Maps operation')

    def request_ip(self):
        self.ipAttempt=time.monotonic()
        request=json.dumps(dict(endpoint=self.settings['ipEndpoint'],consent=True,options=self.opts()))
        def got(value):
            if self.settings['ipConsent'] and not self.locked:self.ip=json.loads(str(value));self.message='Approximate region · VPN, proxy and carrier exits may be misleading'
            self.emit()
        self.client.api.GetIpLocation(request,reply_handler=got,error_handler=lambda e:self.ip_error(e),timeout=15)
    def ip_error(self,e):self.message=str(e)[:300];self.emit()
    def download_progress(self,data):self.progress=data;self.emit();return False
    def input(self,fd,condition):
        try:chunk=os.read(fd,32768)
        except BlockingIOError:return True
        if not chunk:self.release();self.tracks.stop();self.loop.quit();return False
        self.inputBuffer+=chunk
        if len(self.inputBuffer)>65536:self.release();self.loop.quit();return False
        while b'\n' in self.inputBuffer:
            raw,self.inputBuffer=self.inputBuffer.split(b'\n',1)
            try:
                if len(raw)>16384:raise Rejected('Request too large')
                self.command(json.loads(raw))
            except Exception as e:self.message=str(e)[:300]
            self.emit()
        return True


if __name__=='__main__':
    os.umask(0o077)
    from dbus.mainloop.glib import DBusGMainLoop
    from gi.repository import GLib
    DBusGMainLoop(set_as_default=True)
    app=Application();app.loop=GLib.MainLoop()
    def stop():app.pause.set();app.release();app.tracks.stop();app.loop.quit();return False
    GLib.unix_signal_add(GLib.PRIORITY_DEFAULT,signal.SIGTERM,stop)
    GLib.unix_signal_add(GLib.PRIORITY_DEFAULT,signal.SIGINT,stop)
    app.loop.run()
