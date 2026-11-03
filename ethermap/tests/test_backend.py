import contextlib
import io
import json
from pathlib import Path
import sys
import tempfile
import time
import unittest
ROOT=Path(__file__).resolve().parents[2]
sys.path[:0]=[str(ROOT/'etherlocation'),str(ROOT/'ethermap')]
from backend import Application
from domain import Tracks
from maps import Maps


class SnapshotTests(unittest.TestCase):
    def harness(self,root):
        app=object.__new__(Application)
        app.tracks=Tracks(root/'tracks.sqlite');app.maps=Maps(root/'maps')
        app.fix=app.ip=app.last=None
        app.manual=dict(latitude=51,longitude=0,kind='manual',provider='manual',timestamp=time.time())
        app.settings={};app.mode='Off';app.message='';app.location={};app.locked=False;app.interval=10;app.started=0
        app.view=[];app.results=[];app.route={};app.busy=False;app.progress={}
        return app
    def test_manual_point_never_serialized_as_device_position(self):
        with tempfile.TemporaryDirectory() as directory:
            app=self.harness(Path(directory));output=io.StringIO()
            with contextlib.redirect_stdout(output):app.emit()
            s=json.loads(output.getvalue());self.assertIsNone(s['position']);self.assertEqual(s['manual']['kind'],'manual')
            self.assertEqual(s['trail'],[]);self.assertFalse(s['recording']);self.assertFalse(app.tracks.path.exists())
    def test_locked_snapshot_does_not_expose_locations(self):
        with tempfile.TemporaryDirectory() as directory:
            app=self.harness(Path(directory));app.locked=True;app.last=dict(app.manual,provider='gpsd',kind='last-known',accuracy=5)
            app.view=[app.manual];app.results=[app.manual];app.route={'line':[app.manual]}
            output=io.StringIO()
            with contextlib.redirect_stdout(output):app.emit()
            s=json.loads(output.getvalue())
            for field in ('position','manual'):self.assertIsNone(s[field])
            for field in ('trail','results','tracks','places'):self.assertEqual(s[field],[])
            self.assertEqual(s['route'],{})
