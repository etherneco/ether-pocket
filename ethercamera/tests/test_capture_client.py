"""Caller workflow tests with an explicitly offline API stub, never sensor proof."""
import json
from pathlib import Path
import sys
import unittest
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from capture_client import CaptureClient
from core import CameraError

class ClientTests(unittest.TestCase):
    def test_only_confirmed_media_references_leave_callers_review(self):
        class API:
            deleted=[];released=[];counter=0
            def RequestSession(self,*args):return 'OFFLINE-token'
            def CapturePhoto(self,token):
                self.counter+=1;return json.dumps(dict(reference='OFFLINE-'+str(self.counter),kind='fixture'))
            def DeleteMedia(self,ref):self.deleted.append(ref)
            def Release(self,token,**kwargs):self.released.append(token)
        api=API()
        with CaptureClient(api) as client:
            with self.assertRaises(CameraError):client.request('/dev/video8','Fixture',False)
            client.request('/dev/video8','Fixture',True)
            first=client.capture_photo();second=client.capture_photo()
            with self.assertRaises(CameraError):client.confirm_photo(first['reference'],False)
            accepted=client.confirm_photo(first['reference'],True)
            self.assertEqual(accepted,first)
            with self.assertRaises(CameraError):client.retake(first['reference'])
        self.assertEqual(api.deleted,[second['reference']]);self.assertEqual(api.released,['OFFLINE-token'])

    def test_cancel_does_not_bypass_lock_and_still_releases_session(self):
        class API:
            released=False
            def DeleteMedia(self,ref):raise CameraError('Locked')
            def Release(self,token,**kwargs):self.released=True
        api=API();client=CaptureClient(api);client.token='OFFLINE-token';client.pending={'OFFLINE-ref':{}}
        self.assertIsInstance(client.close(),CameraError);self.assertTrue(api.released)
