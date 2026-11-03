"""Offline lifecycle/FD contract tests. No hardware source is constructed."""
import os
from pathlib import Path
import sys
import time
import unittest
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
try:
    import dbus
    from service import Service
    from core import Sessions
except ImportError:
    Service=None

@unittest.skipIf(Service is None,'Linux D-Bus/GI runtime required')
class ServiceTests(unittest.TestCase):
    def harness(self):
        service=object.__new__(Service)
        service.sessions=Sessions();service.sessions.acquire(':1.10','/dev/video8','Fixture lifecycle',True,True)
        service.provider=None;service.record=None;service.inhibitor=None;service.timer=0;service.audio=None
        service.history=[];service.verified={};service.error='';service.frame_request=0
        service.changed=lambda:None
        return service

    def test_owner_exit_and_lock_service_loss_release_hardware(self):
        for name in [':1.10','com.etherneco.EtherLock1']:
            service=self.harness()
            class Provider:
                stopped=False
                def stop(self):self.stopped=True
            provider=Provider();service.provider=provider
            service.owner_changed(name,'old','')
            self.assertTrue(provider.stopped);self.assertIsNone(service.provider)
            self.assertIsNone(service.sessions.session)

    def test_unrelated_exit_does_not_close_session(self):
        service=self.harness();service.owner_changed(':1.11','old','')
        self.assertIsNotNone(service.sessions.session)

    def test_location_proxy_does_not_delegate_camera_grant_to_other_apps(self):
        service=self.harness();service.check=lambda sender,token:None
        service.bus=type('Bus',(),{'call_blocking':lambda *args,**kw:os.getpid()})()
        with self.assertRaises(dbus.DBusException):service.RequestPhotoLocation('fixture',':1.10')
        with self.assertRaises(dbus.DBusException):service.EnablePhotoLocation('fixture',True,':1.10')

    def test_permission_revocation_stops_capture_even_if_policy_storage_fails(self):
        import tempfile
        from core import Preferences
        class Provider:
            stopped=False
            def stop(self):self.stopped=True
        with tempfile.TemporaryDirectory() as tmp:
            service=self.harness();provider=Provider();service.provider=provider
            service.preferences=Preferences(Path(tmp)/'prefs.json')
            blocked=Path(tmp)/'not-a-directory';blocked.write_text('fixture')
            service.preferences.path=blocked/'prefs.json'
            service.own=lambda sender:None;service.unlocked=lambda:False
            with self.assertRaises(dbus.DBusException):service.Configure('{"cameraPolicy":"deny"}',':1.10')
            self.assertTrue(provider.stopped);self.assertIsNone(service.sessions.session)
            self.assertEqual(service.preferences.data['cameraPolicy'],'deny')

    def test_photo_output_removes_source_gps_exif_for_jpeg_and_png(self):
        import io,json,tempfile
        from PIL import Image
        from core import Library
        image=Image.new('RGB',(44,33),'navy');exif=Image.Exif()
        exif[34853]={1:'N',2:(51.0,30.0,0.0),3:'W',4:(0.0,7.0,0.0)}
        data=io.BytesIO();image.save(data,'JPEG',exif=exif)
        self.assertIn(34853,Image.open(io.BytesIO(data.getvalue())).getexif())
        class Provider:
            def frame(self):return data.getvalue(),44,33
        for format in ['JPEG','PNG']:
            with tempfile.TemporaryDirectory() as tmp:
                service=self.harness();service.library=Library(tmp);service.provider=Provider()
                service.check=lambda owner,token:{'device':'OFFLINE-EXIF-FIXTURE'}
                service.settings={'format':format}
                result=json.loads(service.CapturePhoto('fixture',':1.10'))
                path,meta=service.library.get(result['reference'])
                self.assertNotIn(34853,Image.open(path).getexif())
                self.assertEqual((meta['width'],meta['height']),(44,33))

    def test_lock_and_malformed_lock_signal_fail_closed(self):
        for document in ['{"locked":true}','malformed','{}']:
            service=self.harness();service.lock_changed(document)
            self.assertIsNone(service.sessions.session)

    def test_lease_expiry_releases_without_polling_again(self):
        service=self.harness();service.sessions.session['started']=time.monotonic()-301
        service.notice=lambda message:None
        self.assertFalse(service.tick());self.assertIsNone(service.sessions.session)

    @unittest.skipUnless(hasattr(os,'memfd_create'),'Linux memfd required')
    def test_preview_fd_is_readable_sealed_and_not_a_dbus_frame_array(self):
        import fcntl
        service=self.harness();service.check=lambda sender,token:None
        class Provider:
            def frame(self):return b'OFFLINE-JPEG-CONTRACT-FIXTURE',20,10
        service.provider=Provider()
        handle=service.GetFrame('fixture',':1.10');fd=handle.take()
        try:
            self.assertEqual(os.read(fd,100),b'OFFLINE-JPEG-CONTRACT-FIXTURE')
            seals=fcntl.fcntl(fd,fcntl.F_GET_SEALS)
            self.assertTrue(seals&fcntl.F_SEAL_WRITE)
            with self.assertRaises(OSError):os.write(fd,b'altered')
        finally:os.close(fd)

    def test_recording_finalization_failure_still_releases_device(self):
        service=self.harness()
        class Provider:
            stopped=False
            def stop(self):self.stopped=True;return False
        import tempfile
        with tempfile.TemporaryDirectory() as tmp:
            p=Path(tmp)/'incomplete.mp4';p.write_bytes(b'incomplete')
            provider=Provider();service.provider=provider;service.record=('ref',p,'/dev/video8',time.monotonic())
            service.close('Owner exited')
            self.assertFalse(p.exists());self.assertTrue(provider.stopped)
            self.assertIsNone(service.provider);self.assertIsNone(service.sessions.session)

if __name__=='__main__':unittest.main()
