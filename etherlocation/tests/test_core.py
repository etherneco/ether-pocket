import json,math,os,sys,tempfile,time,unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from core import *

def fix(now=1000,**kw):return position(dict(latitude=51.5,longitude=-.12,accuracy=5,timestamp=now,provider='qualcomm-loc',altitude=40,speed=2,heading=60,**kw),now)

class PositionTests(unittest.TestCase):
    def test_invalid_fix_rejected(self):
        for key,value in [('latitude',91),('longitude',float('nan')),('accuracy',0),('timestamp',2000),('latitude',True)]:
            p=fix();p[key]=value
            with self.assertRaises(Rejected):position(p,1000)
    def test_no_fabricated_or_stale_fix(self):
        self.assertIsNone(select([],now=1000));self.assertIsNone(select([fix()],now=1100))
        p=fix();p['kind']='manual';self.assertIsNone(select([p],now=1000))
    def test_gnss_preferred_without_averaging(self):
        g=fix();network=dict(g,provider='geoclue',latitude=10,accuracy=1)
        self.assertEqual(select([network,g],now=1000),g)
        self.assertEqual(select([network,g],False,now=1000),network)
    def test_approximate_cache_strips_precision(self):
        p=fix();out=disclose(p,'approximate',10000,now=1001,cached=True)
        self.assertNotEqual(out['latitude'],p['latitude']);self.assertGreater(out['accuracy'],10000)
        self.assertEqual(out['kind'],'last-known');self.assertEqual(out['age'],1)
        for key in ('altitude','speed','heading','verticalAccuracy'):self.assertNotIn(key,out)
        self.assertIn('altitude',p)
    def test_approximation_bounds_and_uncertainty(self):
        for lat in (-90,-89.9,0,89.9,90):
            for lon in (-180,-.1,0,179.99,180):
                p=dict(fix(),latitude=lat,longitude=lon)
                a=disclose(p,now=1000)
                self.assertLessEqual(distance(p,a),a['accuracy']);self.assertLessEqual(abs(a['latitude']),90);self.assertLessEqual(abs(a['longitude']),180)

class PermissionTests(unittest.TestCase):
    def setUp(self):self.p=Permissions();self.opts=options({})
    def grant(self,policy='allow-while-using',precision='precise',background=False):
        token=self.p.request(':1.2','app',self.opts);self.p.resolve(token,policy,precision,background)
    def test_default_deny(self):
        with self.assertRaises(Rejected):self.p.check(':1.2','app',self.opts,True,False)
    def test_foreground_lock_and_background(self):
        self.grant()
        for foreground,locked in [(False,False),(True,True)]:
            with self.assertRaises(Rejected):self.p.check(':1.2','app',self.opts,foreground,locked)
        self.assertEqual(self.p.check(':1.2','app',self.opts,True,False),'approximate')
        self.grant(background=True)
        self.assertEqual(self.p.check(':1.2','app',options({'background':True}),False,True),'approximate')
    def test_cannot_escalate_precision(self):
        self.grant(precision='approximate')
        self.assertEqual(self.p.check(':1.2','app',options({'precision':'precise'}),True,False),'approximate')
    def test_owner_subscription_and_revoke(self):
        self.grant();t=self.p.subscribe(':1.2','app',self.opts)
        with self.assertRaises(Rejected):self.p.stop(':1.3',t)
        self.p.revoke('app');self.assertEqual(self.p.subscriptions,{})
        with self.assertRaises(Rejected):self.p.check(':1.2','app',self.opts,True,False)
    def test_disconnect_releases_everything(self):
        self.grant('ask-every-time');self.p.subscribe(':1.2','app',self.opts)
        self.p.request(':1.2','app',self.opts);self.p.disconnect(':1.2')
        self.assertFalse(self.p.grants);self.assertFalse(self.p.requests);self.assertFalse(self.p.subscriptions)
    def test_ask_every_time_owner_and_expiry(self):
        self.grant('ask-every-time')
        with self.assertRaises(Rejected):self.p.check(':1.3','app',self.opts,True,False)
        self.p.grants[('app','')]['expires']=time.monotonic()-1
        with self.assertRaises(Rejected):self.p.check(':1.2','app',self.opts,True,False)
    def test_limits_expiration_and_invalid_options(self):
        for data in ({'interval':1},{'timeout':9999},{'maxAge':True},{'background':'yes'},{'origin':'http://x'},{'origin':'https://x/path'},{'app':'trusted'}):
            with self.assertRaises(Rejected):options(data)
        t=self.p.subscribe(':1.2','app',self.opts,now=0);self.p.expire(now=61);self.assertFalse(self.p.subscriptions)
        self.p.subscribe(':1.2','app',self.opts);self.p.subscribe(':1.2','app',self.opts)
        with self.assertRaises(Rejected):self.p.subscribe(':1.2','app',self.opts)
    def test_origin_grant_separation(self):
        self.grant()
        with self.assertRaises(Rejected):self.p.check(':1.2','app',options({'origin':'https://example.com'}),True,False)

class HistoryTests(unittest.TestCase):
    def setUp(self):self.temp=tempfile.TemporaryDirectory();self.h=History(Path(self.temp.name)/'history.sqlite')
    def tearDown(self):self.temp.cleanup()
    def test_default_never_records_or_creates_database(self):
        self.h.record(fix(),1000);self.assertFalse(self.h.path.exists())
    def test_history_exports_delete_and_disabled(self):
        now=time.time();self.h.enabled=True;self.h.record(fix(now),now)
        self.assertEqual(len(self.h.entries()),1)
        if os.name=='posix':self.assertEqual(os.stat(self.h.path).st_mode&0o777,0o600)
        self.assertIn('trkpt',self.h.export('GPX'));self.assertEqual(len(json.loads(self.h.export('GeoJSON'))['features']),1)
        self.h.enabled=False;self.h.record(fix(now+20),now+20);self.assertEqual(len(self.h.entries()),1)
        self.h.delete([self.h.entries()[0]['id']]);self.assertEqual(self.h.entries(),[])
        self.h.enabled=True;self.h.record(fix(now+40),now+40);self.h.delete();self.assertEqual(self.h.entries(),[])
    def test_retention_and_manual_not_recorded(self):
        self.h.enabled=True;self.h.retention=1;now=time.time();p=fix(now);p['kind']='manual';self.h.record(p,now);self.assertFalse(self.h.path.exists())
        with self.h.db() as db:db.execute('INSERT INTO fixes(timestamp,document) VALUES(?,?)',(now-2*86400,json.dumps(fix(now-2*86400))))
        self.assertFalse(self.h.entries())

class FenceTests(unittest.TestCase):
    def setUp(self):self.f=Geofences();self.f.put('test',dict(latitude=0,longitude=0,radius=200,dwell=20))
    def sample(self,t,lon=0,accuracy=5,kind='live'):
        return self.f.evaluate(dict(latitude=0,longitude=lon,accuracy=accuracy,timestamp=t,kind=kind),t)
    def test_initial_presence_silent_entry_exit_dwell_once(self):
        self.assertEqual(self.sample(1000,.01),[]);self.assertEqual(self.sample(1011,.01),[])
        self.assertEqual(self.sample(1020),[]);self.assertEqual(self.sample(1031),[dict(zone='test',event='entry')])
        self.assertEqual(self.sample(1052),[dict(zone='test',event='dwell')]);self.assertEqual(self.sample(1060),[])
        self.assertEqual(self.sample(1065,.01),[]);self.assertEqual(self.sample(1076,.01),[dict(zone='test',event='exit')])
    def test_bad_accuracy_stale_manual_and_duplicate_cannot_transition(self):
        self.sample(1000,.01);self.sample(1011,.01)
        self.assertFalse(self.sample(1020,accuracy=1000));self.assertFalse(self.sample(1020,kind='manual'))
        p=dict(latitude=0,longitude=0,accuracy=5,timestamp=1000,kind='live');self.assertFalse(self.f.evaluate(p,1100))
        self.sample(1020);self.assertFalse(self.sample(1020));self.assertFalse(self.sample(1020));self.assertFalse(self.sample(1040,.0017))
    def test_signal_gap_does_not_satisfy_dwell(self):
        self.sample(1000,.01);self.sample(1011,.01);self.sample(1020)
        self.assertFalse(self.sample(1100));self.assertEqual(self.sample(1111),[dict(zone='test',event='entry')])

if __name__=='__main__':unittest.main()
