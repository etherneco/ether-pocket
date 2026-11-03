import json
from pathlib import Path
import sys
import tempfile
import time
import unittest
import xml.etree.ElementTree as ET

ROOT=Path(__file__).resolve().parents[2]
sys.path[:0]=[str(ROOT/'etherlocation'),str(ROOT/'ethermap')]
from core import Rejected
from domain import Tracks, choose, recordable


class TrackTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.path=Path(self.temp.name)/'tracks.sqlite';self.t=Tracks(self.path);self.now=time.time()
    def tearDown(self):self.temp.cleanup()
    def fix(self,delta=0,**extra):return dict(dict(latitude=51.5,longitude=-0.1+delta/100000,timestamp=self.now+delta,accuracy=5,provider='gpsd',kind='live',precision='precise'),**extra)
    def test_default_creates_no_history(self):
        self.assertEqual(self.t.list(),[]);self.assertFalse(self.path.exists())
        with self.assertRaises(Rejected):self.t.start()
        self.assertFalse(self.path.exists())
    def test_ip_manual_cached_approximate_rejected(self):
        self.t.start(True)
        for p in (self.fix(provider='ip'),self.fix(provider='manual'),self.fix(kind='last-known'),self.fix(precision='approximate'),self.fix(accuracy=101)):
            self.assertFalse(self.t.sample(p,self.now));self.assertFalse(recordable(p,self.now))
        self.assertEqual(self.t.points(self.t.active),[])
    def test_stale_future_and_invalid_rejected(self):
        for p in (self.fix(timestamp=self.now-31),self.fix(timestamp=self.now+1),self.fix(latitude=float('nan')),self.fix(accuracy=None)):
            self.assertFalse(recordable(p,self.now))
    def test_pause_and_signal_gaps_survive_gpx(self):
        id=self.t.start(True)
        self.t.sample(self.fix(),self.now)
        self.t.sample(self.fix(10),self.now+10)
        self.t.sample(self.fix(provider='ip'),self.now+11)
        self.t.sample(self.fix(20),self.now+20)
        self.t.pause();self.assertFalse(self.t.sample(self.fix(21),self.now+21));self.t.resume()
        self.t.sample(self.fix(30),self.now+30)
        before=self.t.summary(id)
        self.assertEqual([p['segment'] for p in self.t.points(id)],[0,0,1,2])
        self.assertGreater(before['distance'],0);self.assertEqual(before['duration'],10)
        exported=self.t.export(id);root=ET.fromstring(exported)
        self.assertEqual(len(root.findall('.//{http://www.topografix.com/GPX/1/1}trkseg')),3)
        imported=self.t.import_gpx(exported.encode())
        self.assertEqual(self.t.summary(imported),before)
        self.assertTrue(all(p['provider']=='imported' for p in self.t.points(imported)))
    def test_duplicate_and_reordered_reports_not_distance(self):
        id=self.t.start(True);self.t.sample(self.fix(),self.now)
        self.assertFalse(self.t.sample(self.fix(),self.now));self.assertFalse(self.t.sample(self.fix(timestamp=self.now-1),self.now))
        self.assertEqual(self.t.summary(id)['distance'],0)
    def test_long_gap_and_teleport_split_segments(self):
        id=self.t.start(True);self.t.sample(self.fix(),self.now)
        self.t.sample(self.fix(100),self.now+100)
        self.t.sample(self.fix(101,latitude=-50),self.now+101)
        self.assertEqual([r['segment'] for r in self.t.points(id)],[0,1,2]);self.assertEqual(self.t.summary(id)['distance'],0)
    def test_import_rejects_unsafe_input_without_writes(self):
        for data in (b'<!DOCTYPE gpx><gpx/>',b'<gpx/>',b'<gpx xmlns="http://www.topografix.com/GPX/1/1"><trk><trkseg><trkpt lat="nan" lon="0"/></trkseg></trk></gpx>'):
            with self.assertRaises((Rejected,ValueError)):self.t.import_gpx(data)
        self.assertFalse(self.path.exists())
    def test_rename_delete_and_saved_place_search(self):
        id=self.t.start(True);self.t.stop();self.t.rename(id,"Morning walk")
        self.assertEqual(self.t.list()[0]['name'],'Morning walk')
        self.t.save_place('Home',51.5,-.1);self.assertEqual(len(self.t.places('Hom')),1)
        self.t.delete_place(self.t.places()[0]['id']);self.assertEqual(self.t.places(),[])
        self.t.delete(id);self.assertEqual(self.t.list(),[])
    def test_stale_gps_cannot_beat_fresh_ip(self):
        old=self.fix(timestamp=self.now-60)
        ip=self.fix(provider='ip',accuracy=None,kind='approximate-region')
        self.assertEqual(choose([old,ip],self.now)['provider'],'ip')
        self.assertEqual(choose([old],self.now)['kind'],'last-known')
    def test_real_fresh_provider_precedes_ip(self):
        self.assertEqual(choose([self.fix(),self.fix(provider='ip',accuracy=None)],self.now)['provider'],'gpsd')
    def test_fresh_network_beats_unreliable_gnss(self):
        self.assertEqual(choose([self.fix(accuracy=500),self.fix(provider='geoclue',accuracy=50)],self.now)['provider'],'geoclue')
    def test_manual_is_not_live_or_recordable(self):
        p=self.fix(provider='manual',kind='manual')
        self.assertEqual(choose([p],self.now)['kind'],'manual');self.assertFalse(recordable(p,self.now))
