#!/usr/bin/python3
"""Session-owned camera API. All capture is opt-in; D-Bus carries metadata and FDs."""
import functools
import io
import json
import os
from pathlib import Path
import time
from concurrent.futures import ThreadPoolExecutor
import dbus
import dbus.service
from dbus.mainloop.glib import DBusGMainLoop
from gi.repository import GLib
from core import CameraError, Library, Scanner, Sessions, Preferences, UsageHistory, manual_code, options
from audio import AudioLease
from devices import enumerate_devices
from provider import UvcProvider
from spectra_provider import SpectraProvider,DEVICE as SPECTRA_DEVICE,available as spectra_available
from power_guard import recording_guard

NAME='com.etherneco.EtherCamera1'
PATH='/com/etherneco/EtherCamera1'

def guarded(fn):
    @functools.wraps(fn)
    def call(*args,**kwargs):
        try:return fn(*args,**kwargs)
        except (CameraError,ValueError,OSError,ImportError,KeyError) as e:
            raise dbus.exceptions.DBusException(str(e),name=NAME+'.Rejected')
    return call

class Service(dbus.service.Object):
    def __init__(self):
        self.bus=dbus.SessionBus();self.system=dbus.SystemBus()
        self.name=dbus.service.BusName(NAME,self.bus,do_not_queue=True)
        super().__init__(self.bus,PATH)
        self.sessions=Sessions();self.provider=None;self.timer=0;self.inhibitor=None
        self.record=None;self.settings={};self.record_settings={};self.error='';self.frame_request=0
        self.audio=None
        self.location_token=None;self.geotag_requested=False
        self.power_state={}
        self.preferences=Preferences(Path.home()/'.config/ethercamera/preferences.json')
        self.devices=enumerate_devices();self.scanner=Scanner();self.pool=ThreadPoolExecutor(max_workers=1)
        self.jobs={};self.job_owners={};self.verified={}
        self.usage=UsageHistory(Path.home()/'.local/share/ethercamera/usage.json');self.history=self.usage.entries
        self.library=Library(Path.home()/'Pictures/EtherCamera')
        self.hardware_camera_signature=None
        self.system.add_signal_receiver(self.hardware_changed,signal_name='Changed',dbus_interface='com.etherneco.EtherHardware1',bus_name='com.etherneco.EtherHardware1')
        self.bus.add_signal_receiver(self.owner_changed,signal_name='NameOwnerChanged',dbus_interface='org.freedesktop.DBus')
        self.bus.add_signal_receiver(self.lock_changed,signal_name='Changed',dbus_interface='com.etherneco.EtherLock1',bus_name='com.etherneco.EtherLock1')
        self.system.add_signal_receiver(self.sleep,signal_name='PrepareForSleep',dbus_interface='org.freedesktop.login1.Manager',bus_name='org.freedesktop.login1')
        self.system.add_signal_receiver(self.power_changed,signal_name='Changed',dbus_interface='com.etherneco.EtherPower1',bus_name='com.etherneco.EtherPower1')
        self.system.add_signal_receiver(self.power_owner_changed,signal_name='NameOwnerChanged',dbus_interface='org.freedesktop.DBus',arg0='com.etherneco.EtherPower1')

    def own(self, sender):
        if self.bus.get_unix_user(sender)!=os.getuid():raise CameraError('Wrong session user')

    def unlocked(self):
        try:
            # EtherLock deployment is staged separately; never auto-start its policy.
            if not self.bus.name_has_owner('com.etherneco.EtherLock1'):return False
            api=dbus.Interface(self.bus.get_object('com.etherneco.EtherLock1','/com/etherneco/EtherLock1',introspect=False),'com.etherneco.EtherLock1')
            data=json.loads(str(api.GetState(timeout=2)))
            return data.get('ready') is True and data.get('locked') is False and data.get('phase')=='unlocked'
        except (dbus.DBusException,ValueError):return False

    def check(self, sender, token):
        self.own(sender)
        s=self.sessions.check(sender,str(token))
        if not self.unlocked():self.close('Session locked');raise CameraError('Camera denied on lock screen')
        return s

    def snapshot(self):
        s=self.sessions.session
        return dict(schemaVersion=1,ready=True,devices=self.devices,active=bool(self.provider and self.provider.pipeline),busy=bool(s),recording=bool(self.record),
            owner=s['owner'] if s else '',purpose=s['purpose'] if s else '',
            frames=self.provider.frames if self.provider else 0,verified=self.verified,
            recordingSeconds=round(time.monotonic()-self.record[3],1) if self.record else 0,
            lastError=self.error,history=self.history[-30:],
            permissionCoordinatorAvailable=bool(self.bus.name_has_owner('com.etherneco.EtherLock1')),
            privacy='Managed API checks same-UID D-Bus ownership, explicit per-session consent and EtherLock. Same-user applications and direct device access are outside this boundary.',
            config=self.preferences.data,configurationError=self.preferences.error,
            microphone='Active via EtherAudio' if self.audio else 'Off; separate consent required for every recording',
            internalCamera='Rear IMX586: native Spectra RAW10; fixed exposure/focus' if spectra_available() else 'Native rear camera driver not provisioned',
            previewTransport='GetFrame returns a sealed JPEG file descriptor; no raw frames in D-Bus messages',
            hardwareAcceleration='Not verified',jobs={k:{'state':v['state']} for k,v in self.jobs.items()})

    @dbus.service.signal(NAME,signature='s')
    def Changed(self, document):pass

    def changed(self):self.Changed(json.dumps(self.snapshot()))

    def event(self, kind):
        if hasattr(self,'usage'):
            try:self.history=self.usage.add(kind)
            except (OSError,CameraError):self.error='Usage history could not be persisted'
        else:
            self.history.append(dict(event=kind,timestamp=int(time.time())))
            self.history=self.history[-100:]

    def notice(self, message):
        try:
            dbus.Interface(self.bus.get_object('org.freedesktop.Notifications','/org/freedesktop/Notifications',introspect=False),'org.freedesktop.Notifications').Notify('EtherCamera',dbus.UInt32(0),'camera-photo','EtherCamera',message,dbus.Array([],signature='s'),dbus.Dictionary({},signature='sv'),5000,timeout=2)
        except dbus.DBusException:pass

    @dbus.service.method(NAME,in_signature='',out_signature='s',sender_keyword='sender')
    @guarded
    def GetState(self,sender):self.own(sender);return json.dumps(self.snapshot())

    @dbus.service.method(NAME,in_signature='',out_signature='s',sender_keyword='sender')
    @guarded
    def Refresh(self,sender):
        self.own(sender)
        if self.sessions.session:raise CameraError('Release active session before refreshing')
        self.devices=enumerate_devices();self.changed();return json.dumps(self.snapshot())

    @dbus.service.method(NAME,in_signature='s',out_signature='s',sender_keyword='sender')
    @guarded
    def Configure(self, document, sender):
        self.own(sender)
        if len(document)>2048:raise CameraError('Settings too large')
        changes=json.loads(str(document))
        if changes!={'cameraPolicy':'deny'} and not self.unlocked():raise CameraError('Unlock session to change camera settings')
        self.preferences.validate(changes)
        denying=changes.get('cameraPolicy')=='deny'
        if denying:
            self.preferences.data['cameraPolicy']='deny'
            if self.sessions.session:self.close('Camera permission revoked')
        try:self.preferences.update(changes)
        except (OSError,CameraError):
            if denying:self.preferences.error='Camera denied in memory; policy could not be persisted';self.changed()
            raise
        self.changed();return json.dumps(self.snapshot())

    @dbus.service.method(NAME,in_signature='ssbs',out_signature='s',sender_keyword='sender')
    @guarded
    def RequestSession(self, device, purpose, consent, document, sender):
        self.own(sender)
        if self.preferences.data['cameraPolicy']=='deny':raise CameraError('Managed camera permission denied by policy')
        if not consent:raise CameraError('Explicit user consent is required')
        if len(document)>1024:raise CameraError('Options too large')
        settings=self.preferences.capture_options(json.loads(str(document)))
        self.devices=enumerate_devices()
        if not any(d['id']==device and d.get('supportedProvider') for d in self.devices):
            raise CameraError('No supported physical capture device')
        token=self.sessions.acquire(sender,str(device),str(purpose),bool(consent),self.unlocked())
        self.settings=settings;self.scanner=Scanner();self.error='';self.event('session-granted');self.changed()
        # Expires even when a caller requests a session but never starts preview.
        self.timer=GLib.timeout_add(500,self.tick)
        return token

    def acquire_inhibitor(self):
        api=dbus.Interface(self.system.get_object('org.freedesktop.login1','/org/freedesktop/login1',introspect=False),'org.freedesktop.login1.Manager')
        self.inhibitor=api.Inhibit('sleep','EtherCamera','Active physical camera capture','block',timeout=3).take()

    def validate_device(self, device):
        self.devices=enumerate_devices()
        if not any(d['id']==device and d.get('supportedProvider') for d in self.devices):
            raise CameraError('Selected UVC device disconnected or changed')

    @dbus.service.method(NAME,in_signature='s',out_signature='',sender_keyword='sender')
    @guarded
    def StartPreview(self, token, sender):
        s=self.check(sender,token)
        if self.provider:raise CameraError('Preview already active')
        self.validate_device(s['device'])
        try:
            self.acquire_inhibitor();self.check(sender,token);self.provider=SpectraProvider() if s['device']==SPECTRA_DEVICE else UvcProvider()
            self.check(sender,token)
            self.provider.start(s['device'],self.settings)
        except Exception as e:
            self.error=str(e)[:400]
            self.close('Preview start failed');raise
        self.event('preview-starting');self.changed();self.notice('Camera in use: '+s['purpose'])

    @dbus.service.method(NAME,in_signature='s',out_signature='h',sender_keyword='sender')
    @guarded
    def GetFrame(self, token, sender):
        self.check(sender,token)
        if not self.provider:raise CameraError('Start preview first')
        now=time.monotonic()
        if now-self.frame_request<1/30:raise CameraError('Frame request rate exceeded')
        self.frame_request=now
        data,_,_=self.provider.frame()
        import fcntl
        fd=os.memfd_create('ethercamera-preview',os.MFD_CLOEXEC|os.MFD_ALLOW_SEALING)
        try:
            with os.fdopen(os.dup(fd),'wb') as stream:stream.write(data)
            os.lseek(fd,0,os.SEEK_SET)
            fcntl.fcntl(fd,fcntl.F_ADD_SEALS,fcntl.F_SEAL_SEAL|fcntl.F_SEAL_SHRINK|fcntl.F_SEAL_GROW|fcntl.F_SEAL_WRITE)
            return dbus.types.UnixFd(fd)
        finally:os.close(fd)

    @dbus.service.method(NAME,in_signature='s',out_signature='s',sender_keyword='sender')
    @guarded
    def CapturePhoto(self, token, sender):
        s=self.check(sender,token)
        if not self.provider:raise CameraError('Start preview first')
        data,w,h=self.provider.frame();suffix='.jpg' if self.settings['format']=='JPEG' else '.png'
        ref,p=self.library.allocate(suffix)
        try:
            from PIL import Image
            image=Image.open(io.BytesIO(data));image.load()
            if image.size!=(w,h):raise CameraError('Frame dimensions disagree')
            # Re-encoding discards source EXIF/location. Orientation remains explicitly unknown.
            image.info.clear()
            metadata=b''
            if getattr(self,'geotag_requested',False):
                try:
                    from location_metadata import gps_exif
                    api=self.location_api()
                    fix=json.loads(str(api.GetLocation('{"precision":"precise","maxAge":30}',timeout=2)))
                    metadata=gps_exif(fix)
                except (dbus.DBusException,ValueError):self.error='Photo saved without location: no permitted current fix'
            image.save(p,'JPEG' if suffix=='.jpg' else 'PNG',exif=metadata)
            self.check(sender,token)
            result=self.library.commit(ref,suffix,dict(camera=s['device'],width=w,height=h,orientation=None,kind='photo'))
        except Exception:p.unlink(missing_ok=True);raise
        self.verified.setdefault(s['device'],{})['stillVerified']=True
        self.event('photo-saved');self.changed();return json.dumps(result)

    def location_api(self):
        return dbus.Interface(self.bus.get_object('com.etherneco.EtherLocation1','/com/etherneco/EtherLocation1',introspect=False),'com.etherneco.EtherLocation1')

    def photo_location_owner(self,sender):
        # The camera must not become a location-permission proxy for arbitrary
        # capture API clients. Other applications need their own location grant.
        pid=int(self.bus.call_blocking('org.freedesktop.DBus','/org/freedesktop/DBus','org.freedesktop.DBus','GetConnectionUnixProcessID','s',(sender,),timeout=2))
        executable=(Path('/proc')/str(pid)/'exe').resolve(strict=True)
        if str(executable)!='/usr/bin/ethercamera-app' or executable.stat().st_uid!=0 or executable.stat().st_mode&0o022:
            raise CameraError('Photo geotagging proxy is restricted to the installed EtherCamera app; request your own application location permission')

    @dbus.service.method(NAME,in_signature='s',out_signature='s',sender_keyword='sender')
    @guarded
    def RequestPhotoLocation(self,token,sender):
        self.check(sender,token)
        self.photo_location_owner(sender)
        return str(self.location_api().RequestPermission('{"precision":"precise","timeout":300}',timeout=3))

    @dbus.service.method(NAME,in_signature='sb',out_signature='',sender_keyword='sender')
    @guarded
    def EnablePhotoLocation(self,token,consent,sender):
        self.check(sender,token)
        self.photo_location_owner(sender)
        if self.location_token:
            try:self.location_api().StopUpdates(self.location_token,timeout=2)
            except dbus.DBusException:pass
            self.location_token=None
        self.geotag_requested=False
        if consent:
            self.location_token=str(self.location_api().StartUpdates('{"precision":"precise","interval":10,"timeout":300}',timeout=3))
            self.geotag_requested=True

    @dbus.service.method(NAME,in_signature='ssi',out_signature='',sender_keyword='sender')
    @guarded
    def SetControl(self, token, control, value, sender):
        s=self.check(sender,token)
        # Standard UVC integer controls only. No arbitrary ioctl/register/vendor commands.
        allow={'focus_auto','focus_absolute','exposure_auto','exposure_absolute',
               'focus_automatic_continuous','auto_exposure','exposure_time_absolute','white_balance_automatic',
               'exposure_auto_priority','white_balance_temperature_auto',
               'white_balance_temperature','gain','zoom_absolute','brightness','contrast','saturation'}
        control=str(control)
        if control not in allow:raise CameraError('Unsupported control')
        device=next((d for d in self.devices if d['id']==s['device']),{})
        import re,subprocess
        if not re.search(r'^\s*'+re.escape(control)+r'\s+0x',device.get('controls',''),re.M):raise CameraError('Control not advertised by this camera')
        p=subprocess.run(['v4l2-ctl','-d',s['device'],'--set-ctrl',control+'='+str(int(value))],capture_output=True,text=True,timeout=3)
        if p.returncode:raise CameraError(p.stderr[:300] or 'Driver rejected control')

    @dbus.service.method(NAME,in_signature='s',out_signature='',sender_keyword='sender')
    @guarded
    def StartRecording(self, token, sender):
        return self.start_recording(token,sender,False)

    @dbus.service.method(NAME,in_signature='sb',out_signature='',sender_keyword='sender')
    @guarded
    def StartRecordingWithAudio(self, token, microphoneConsent, sender):
        if not microphoneConsent:raise CameraError('Separate microphone consent is required')
        return self.start_recording(token,sender,True)

    def start_recording(self, token, sender, audio):
        s=self.check(sender,token)
        if self.record:raise CameraError('Already recording')
        if not self.provider:raise CameraError('Start preview and verify a real frame first')
        self.provider.frame()
        self.validate_device(s['device'])
        self.provider.recording_plugins(audio)
        reason=self.power_reason(refresh=True)
        if reason:raise CameraError(reason)
        self.check(sender,token)
        self.record_settings=self.preferences.video_options()
        ref,p=self.library.allocate('.mp4')
        try:
            if audio:
                self.audio=AudioLease(self.bus)
                self.audio.start(True,'EtherCamera video: '+s['purpose'])
            self.check(sender,token)
            self.provider.stop();self.provider.start(s['device'],self.record_settings,recording=p,audio_fd=self.audio.fd if self.audio else None)
            self.record=(ref,p,s['device'],time.monotonic())
        except Exception:p.unlink(missing_ok=True);self.close('Recording start failed');raise
        self.event('recording-starting');self.changed()

    def finish_recording(self):
        record=self.record
        if not record:return None
        self.record=None
        if self.audio:self.audio.stop()
        try:ok=self.provider.stop() if self.provider else False
        finally:
            if self.audio:self.audio.close();self.audio=None
        ref,p,device,_=record
        if not ok or not getattr(self.provider,'frames',0):
            p.unlink(missing_ok=True);raise CameraError('Recording did not finalize; incomplete output discarded')
        # A completed mux is not a playback or hardware-encoder acceptance test.
        try:return self.library.commit(ref,'.mp4',dict(camera=device,width=self.record_settings['width'],height=self.record_settings['height'],kind='video'))
        except Exception:p.unlink(missing_ok=True);raise

    @dbus.service.method(NAME,in_signature='s',out_signature='s',sender_keyword='sender')
    @guarded
    def StopRecording(self, token, sender):
        self.check(sender,token)
        result=self.finish_recording()
        if result is None:raise CameraError('No recording active')
        # Hardware is released. Caller must release session or explicitly start preview again.
        self.provider=None
        if self.inhibitor is not None:os.close(self.inhibitor);self.inhibitor=None
        self.event('recording-saved');self.changed();return json.dumps(result)

    @dbus.service.method(NAME,in_signature='sb',out_signature='s',sender_keyword='sender')
    @guarded
    def Scan(self, token, continuous, sender):
        self.check(sender,token)
        if not self.provider:raise CameraError('Start preview first')
        data,_,_=self.provider.frame()
        # Worker keeps decoding off the service event loop.
        return self.submit(lambda:self.scanner.decode(data,bool(continuous)),sender)

    @dbus.service.method(NAME,in_signature='ss',out_signature='s',sender_keyword='sender')
    @guarded
    def ManualCode(self, format, text, sender):
        self.media_allowed(sender)
        return json.dumps(manual_code(str(format),str(text)))

    def submit(self, fn, sender):
        if any(v['state']=='running' for v in self.jobs.values()):raise CameraError('Processing busy')
        import uuid
        job=uuid.uuid4().hex
        # Jobs include scan payloads: retain at most 8 in memory, never diagnostic export.
        while len(self.jobs)>=8:
            old=next(iter(self.jobs));self.jobs.pop(old);self.job_owners.pop(old,None)
        self.jobs[job]={'state':'running'}
        self.job_owners[job]=sender
        def complete(future):
            try:self.jobs[job]=dict(state='done',result=future.result())
            except Exception as e:self.jobs[job]=dict(state='failed',error=str(e)[:300])
            self.changed();return False
        self.pool.submit(fn).add_done_callback(lambda f:GLib.idle_add(complete,f))
        return job

    @dbus.service.method(NAME,in_signature='s',out_signature='s',sender_keyword='sender')
    @guarded
    def GetJob(self, job, sender):
        self.own(sender)
        if not self.unlocked() or self.job_owners.get(str(job))!=sender:raise CameraError('Job is private to caller')
        return json.dumps(self.jobs[str(job)])

    @dbus.service.method(NAME,in_signature='ss',out_signature='s',sender_keyword='sender')
    @guarded
    def ProcessDocument(self, reference, document, sender):
        self.own(sender)
        if not self.unlocked():raise CameraError('Session locked')
        if len(document)>2048:raise CameraError('Options too large')
        opts=json.loads(str(document))
        if not isinstance(opts,dict) or set(opts)-{'corners','grayscale','rotation'}:raise CameraError('Invalid document options')
        p,meta=self.library.get(str(reference))
        if meta['suffix'] not in ('.jpg','.png'):raise CameraError('Document requires an image')
        def work():
            from documents import process
            data,details=process(p.read_bytes(),**opts)
            ref,target=self.library.allocate('.png')
            try:
                target.write_bytes(data)
                return self.library.commit(ref,'.png',dict(kind='document',width=details['width'],height=details['height']))
            except Exception:target.unlink(missing_ok=True);raise
        return self.submit(work,sender)

    @dbus.service.method(NAME,in_signature='as',out_signature='s',sender_keyword='sender')
    @guarded
    def ExportDocument(self, references, sender):
        self.own(sender)
        if not self.unlocked():raise CameraError('Session locked')
        if not 1<=len(references)<=20:raise CameraError('Use 1 to 20 pages')
        pages=[self.library.get(str(r))[0] for r in references]
        if any(p.suffix not in ('.jpg','.png') for p in pages):raise CameraError('PDF pages must be images')
        def work():
            from documents import export_pdf
            ref,p=self.library.allocate('.pdf')
            try:
                export_pdf([p.read_bytes() for p in pages],p)
                return self.library.commit(ref,'.pdf',dict(kind='document'))
            except Exception:p.unlink(missing_ok=True);raise
        return self.submit(work,sender)

    @dbus.service.method(NAME,in_signature='s',out_signature='s',sender_keyword='sender')
    @guarded
    def ListMedia(self, search, sender):
        self.own(sender)
        if not self.unlocked():raise CameraError('Session locked')
        return json.dumps(self.library.list(str(search)))

    def media_allowed(self, sender):
        self.own(sender)
        if not self.unlocked():raise CameraError('Unlock session to access camera media')

    @dbus.service.method(NAME,in_signature='su',out_signature='s',sender_keyword='sender',async_callbacks=('success','failure'))
    def ListMediaPage(self, document, offset, sender, success, failure):
        try:
            self.media_allowed(sender)
            if len(document)>512 or int(offset)>100000:raise CameraError('Media query too large')
            query=json.loads(str(document))
            if not isinstance(query,dict) or set(query)-{'search','kind','album'}:raise CameraError('Unknown media filter')
            if any(not isinstance(v,str) or len(v)>160 for v in query.values()):raise CameraError('Invalid media filter')
            offset=int(offset)
            def work():
                rows=self.library.list(limit=51,offset=offset,**query)
                return json.dumps(dict(items=rows[:50],nextOffset=offset+50 if len(rows)>50 else -1))
            self.media_work(work,sender,success,failure)
        except Exception as e:failure(dbus.exceptions.DBusException(str(e),name=NAME+'.Rejected'))

    def media_work(self, fn, sender, success, failure):
        if getattr(self,'pending_media',0)>=16:raise CameraError('Media processing busy')
        self.pending_media=getattr(self,'pending_media',0)+1
        def complete(future):
            self.pending_media-=1
            try:
                self.media_allowed(sender)
                result=future.result();success(result)
            except Exception as e:
                try:failure(dbus.exceptions.DBusException(str(e),name=NAME+'.Rejected'))
                except dbus.DBusException:pass
            return False
        self.pool.submit(fn).add_done_callback(lambda f:GLib.idle_add(complete,f))

    @dbus.service.method(NAME,in_signature='s',out_signature='h',sender_keyword='sender',async_callbacks=('success','failure'))
    def GetThumbnail(self, reference, sender, success, failure):
        try:
            self.media_allowed(sender)
            def deliver(data):
                fd=self.byte_fd(data,'ethercamera-thumbnail')
                try:success(dbus.types.UnixFd(fd))
                finally:os.close(fd)
            self.media_work(lambda:self.library.thumbnail(str(reference)),sender,deliver,failure)
        except Exception as e:failure(dbus.exceptions.DBusException(str(e),name=NAME+'.Rejected'))

    @staticmethod
    def byte_fd(data,label):
        import fcntl
        fd=os.memfd_create(label,os.MFD_CLOEXEC|os.MFD_ALLOW_SEALING)
        try:
            with os.fdopen(os.dup(fd),'wb') as stream:stream.write(data)
            os.lseek(fd,0,os.SEEK_SET)
            fcntl.fcntl(fd,fcntl.F_ADD_SEALS,fcntl.F_SEAL_SEAL|fcntl.F_SEAL_SHRINK|fcntl.F_SEAL_GROW|fcntl.F_SEAL_WRITE)
            return fd
        except Exception:os.close(fd);raise

    @dbus.service.method(NAME,in_signature='ss',out_signature='s',sender_keyword='sender')
    @guarded
    def SetAlbum(self, reference, album, sender):
        self.media_allowed(sender)
        return json.dumps(self.library.set_album(str(reference),str(album)))

    @dbus.service.method(NAME,in_signature='s',out_signature='s',sender_keyword='sender')
    @guarded
    def MediaInfo(self, reference, sender):
        self.media_allowed(sender)
        p,data=self.library.get(str(reference))
        return json.dumps(dict(metadata=data,url=p.as_uri()))

    @dbus.service.method(NAME,in_signature='s',out_signature='s',sender_keyword='sender',async_callbacks=('success','failure'))
    def ExportMedia(self, reference, sender, success, failure):
        try:
            self.media_allowed(sender)
            self.media_work(lambda:str(self.library.export(str(reference),Path.home()/'Documents/EtherCameraExports')),sender,success,failure)
        except Exception as e:failure(dbus.exceptions.DBusException(str(e),name=NAME+'.Rejected'))

    @dbus.service.method(NAME,in_signature='s',out_signature='h',sender_keyword='sender')
    @guarded
    def OpenMedia(self, reference, sender):
        self.own(sender)
        if not self.unlocked():raise CameraError('Session locked')
        p,_=self.library.get(str(reference))
        fd=os.open(p,os.O_RDONLY|os.O_NOFOLLOW)
        try:return dbus.types.UnixFd(fd)
        finally:os.close(fd)

    @dbus.service.method(NAME,in_signature='s',out_signature='',sender_keyword='sender')
    @guarded
    def DeleteMedia(self, reference, sender):
        self.own(sender)
        if not self.unlocked():raise CameraError('Session locked')
        self.library.delete(str(reference))

    @dbus.service.method(NAME,in_signature='s',out_signature='',sender_keyword='sender')
    @guarded
    def Release(self, token, sender):self.check(sender,token);self.close('Released')

    @dbus.service.method(NAME,in_signature='',out_signature='s',sender_keyword='sender')
    @guarded
    def DiagnosticReport(self,sender):
        self.own(sender)
        # Allowlist: no media, scan values, purpose, owner, job results or home directory.
        return json.dumps(dict(schemaVersion=1,devices=self.devices,internalCamera=self.snapshot()['internalCamera'],
            verified=self.verified,active=bool(self.sessions.session),hasError=bool(self.error),
            cameraUI='Native EtherCamera app; capture disabled until a supported source returns a real frame',microphone=False))

    def close(self, reason):
        self.geotag_requested=False
        if getattr(self,'location_token',None):
            try:self.location_api().StopUpdates(self.location_token,timeout=2)
            except dbus.DBusException:pass
            self.location_token=None
        try:
            if self.record:
                try:self.finish_recording()
                except CameraError as e:self.error=str(e)
            if self.provider:self.provider.stop()
        finally:
            if self.audio:self.audio.close();self.audio=None
            self.provider=None
            if self.inhibitor is not None:os.close(self.inhibitor);self.inhibitor=None
            self.sessions.release()
            if self.timer:GLib.source_remove(self.timer);self.timer=0
            self.event(reason);self.changed()

    def owner_changed(self,name,old,new):
        if self.sessions.session and (str(name)==self.sessions.session['owner'] and not new or str(name)=='com.etherneco.EtherLock1' and old):self.close('Owner or lock service exited')
        if str(name)=='com.etherneco.EtherLock1':self.changed()
        if self.audio and str(name)=='com.etherneco.EtherAudio1' and old and not new:
            self.error='Microphone service stopped';self.close('Microphone service stopped');self.notice(self.error)

    def hardware_changed(self,document):
        # Reuse EtherHardware's coalesced events, never add an idle scan timer.
        try:
            data=json.loads(str(document))
            signature=tuple(sorted((str(r['id']),str(r.get('title',''))) for r in data.get('components',[]) if r.get('category')=='camera'))
            if signature==self.hardware_camera_signature:return
            self.hardware_camera_signature=signature
        except (ValueError,KeyError,TypeError):return
        def complete(future):
            try:self.devices=future.result();self.changed()
            except Exception:self.error='Camera discovery refresh failed';self.changed()
            return False
        self.pool.submit(enumerate_devices).add_done_callback(lambda f:GLib.idle_add(complete,f))

    def lock_changed(self,document):
        try:locked=json.loads(str(document)).get('locked',True)
        except ValueError:locked=True
        if locked and self.sessions.session:self.close('Locked')

    def sleep(self,sleeping):
        if sleeping:self.close('Suspend requested')
        else:self.devices=enumerate_devices();self.changed()

    def power_changed(self,document):
        try:self.power_state=json.loads(str(document))
        except (ValueError,TypeError):self.power_state={}

    def power_owner_changed(self,name,old,new):
        if old:
            self.power_state={}
            if self.record:self.error='Power telemetry unavailable';self.close('Power telemetry unavailable')

    def power_reason(self,refresh=False):
        if refresh:
            try:
                api=dbus.Interface(self.system.get_object('com.etherneco.EtherPower1','/com/etherneco/EtherPower1',introspect=False),'com.etherneco.EtherPower1')
                self.power_changed(api.GetState(timeout=2))
            except dbus.DBusException:self.power_state={}
        return recording_guard(self.power_state)

    def tick(self):
        if not self.sessions.session:return False
        reason=''
        if time.monotonic()-self.sessions.session['started']>300:reason='Five-minute session limit'
        if self.provider:
            reason=reason or self.provider.error()
            if self.provider.frames:
                device=self.sessions.session['device']
                if not self.verified.get(device,{}).get('previewVerified'):
                    self.verified.setdefault(device,{})['previewVerified']=True;self.changed()
            if self.record and time.monotonic()-self.record[3]>60:reason='Software video duration limit'
            if self.record and self.audio and getattr(self.provider,'audioEnded',False):reason=reason or 'Microphone capture ended'
            if self.record:
                import shutil
                if shutil.disk_usage(self.library.root).free<128*1024*1024:reason='Storage low'
                reason=reason or self.power_reason()
        if reason:
            self.timer=0;self.error=reason;self.close(reason);self.notice(reason);return False
        return True

if __name__=='__main__':
    if os.getuid()==0:raise SystemExit('Run as the graphical session user')
    os.umask(0o077);DBusGMainLoop(set_as_default=True)
    service=Service();loop=GLib.MainLoop()
    import signal
    def stop(*args):service.close('Service stopping');loop.quit();return False
    GLib.unix_signal_add(GLib.PRIORITY_DEFAULT,signal.SIGTERM,stop)
    GLib.unix_signal_add(GLib.PRIORITY_DEFAULT,signal.SIGINT,stop)
    try:loop.run()
    finally:service.close('Service stopped');service.pool.shutdown(wait=True,cancel_futures=True)
