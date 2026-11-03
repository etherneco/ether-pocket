import json
import os
from pathlib import Path
import sys
import unittest
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from core import CameraError
from audio import AudioLease

class AudioTests(unittest.TestCase):
    def test_no_consent_never_contacts_audio_owner(self):
        class Bus:
            def get_object(self,*args,**kwargs):raise AssertionError('No microphone request allowed')
        lease=AudioLease(Bus())
        with self.assertRaises(CameraError):lease.start(False,'No consent')
        self.assertIsNone(lease.fd);lease.close()

    @unittest.skipUnless(os.name=='posix','Linux D-Bus FDs required')
    def test_managed_audio_fd_and_owner_stop_cleanup(self):
        import dbus
        readfd,writefd=os.pipe();os.write(writefd,b'fixture audio');os.close(writefd)
        class API:
            stops=[];calls=[]
            def GetState(self,**kwargs):return json.dumps({'ready':True,'default-source':'fixture-source'})
            def StartCapture(self,*args,**kwargs):self.calls.append(args);return 'fixture-token',dbus.types.UnixFd(readfd)
            def StopCapture(self,token,**kwargs):self.stops.append(token)
        class Bus:
            def get_object(self,*args,**kwargs):return api
        api=API();lease=AudioLease(Bus())
        try:
            with patch('dbus.Interface',lambda obj,interface:obj):
                fd=lease.start(True,'Fixture consent');self.assertEqual(os.read(fd,100),b'fixture audio')
                self.assertIs(api.calls[0][2],True);self.assertEqual(int(api.calls[0][3]),60)
                lease.close();self.assertEqual(api.stops,['fixture-token'])
                with self.assertRaises(OSError):os.fstat(fd)
        finally:os.close(readfd)
