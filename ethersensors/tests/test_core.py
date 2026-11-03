"""Temporary sysfs fixtures only; these tests do not certify physical sensors."""
import math
from pathlib import Path
import sys
import tempfile
import unittest
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from core import Core,Rejected,rate
from providers import IIO,Discovery,finite

class Fixture(unittest.TestCase):
 def setUp(self):
  self.temp=tempfile.TemporaryDirectory();self.root=Path(self.temp.name)
  self.iio=self.root/'sys/bus/iio/devices';self.iio.mkdir(parents=True)
  self.now=100.;self.provider=IIO(self.iio);self.discovery=Discovery(self.provider,self.root)
 def tearDown(self):self.temp.cleanup()
 def device(self,attrs):
  p=self.iio/'iio:device0';p.mkdir(exist_ok=True)
  for name,value in attrs.items():(p/name).write_text(str(value),encoding='utf-8')
  return p
 def core(self):return Core(self.discovery,lambda:self.now)
 def stream(self):
  self.device({'name':'TEST FIXTURE ONLY','in_illuminance_raw':'12','in_illuminance_scale':'0.5','in_illuminance_offset':'2'})
  c=self.core();c.grant(':1',10,True);token=c.start(':1','iio:device0:ambient_light',2)
  return c,token

class DiscoveryTests(Fixture):
 def test_pmic_is_not_motion(self):
  self.device({'name':'PM8150','in_temp_die_temp_input':30000,'in_voltage_vph_pwr_raw':200})
  self.assertEqual(self.provider.discover(),[])
  self.assertFalse(any(r['measurementAvailable'] for r in self.discovery.scan()))
 def test_ssc_is_not_measurement(self):
  (self.root/'dev').mkdir();(self.root/'dev/sensors').touch()
  rows=self.discovery.scan();r=next(r for r in rows if r['type']=='accelerometer')
  self.assertEqual(r['status'],'Blocked');self.assertFalse(r['measurementAvailable'])
 def test_derived_not_physical(self):
  rows=self.discovery.scan()
  for row in rows:
   if row['id'].startswith('derived:'):self.assertFalse(row['physical']);self.assertFalse(row['measurementAvailable'])
 def test_input_candidate_not_near_far(self):
  p=self.root/'sys/class/input/event10/device';p.mkdir(parents=True);(p/'name').write_text('STM VL53L1 proximity sensor')
  r=next(r for r in self.discovery.scan() if r['type']=='proximity')
  self.assertEqual(r['status'],'Partially supported');self.assertFalse(r['measurementAvailable'])
 def test_vector_requires_mapping(self):
  self.device({'in_accel_x_raw':1,'in_accel_y_raw':2,'in_accel_z_raw':3,'in_accel_scale':1})
  row=self.provider.discover()[0];self.assertFalse(row['measurementAvailable'])
  with self.assertRaises(ValueError):self.provider.sample(row['id'])
 def test_missing_scale_fails_closed(self):
  self.device({'in_illuminance_raw':12});self.assertFalse(self.provider.discover()[0]['measurementAvailable'])
 def test_offset_scale_order_and_timestamp(self):
  c,t=self.stream();c.tick();sample=c.read(':1',t)
  self.assertEqual(sample['values'],[7.]);self.assertEqual(sample['units'],'lux')
  self.assertGreater(sample['timestampNs'],0);self.assertFalse(sample['simulated']);self.assertFalse(sample['physicalResponseVerified'])
 def test_pressure_si_conversion(self):
  self.device({'in_pressure_input':101.325});r=self.provider.discover()[0]
  self.assertAlmostEqual(self.provider.sample(r['id'])['values'][0],101325)
 def test_nan_and_infinite_rejected(self):
  for value in ('NaN','inf','-inf'):
   with self.assertRaises(ValueError):finite(value)
 def test_no_discovery_writes(self):
  p=self.device({'in_illuminance_raw':12,'in_illuminance_scale':1,'sampling_frequency':5})
  before={q.name:q.read_bytes() for q in p.iterdir()};self.discovery.scan();self.provider.sample('iio:device0:ambient_light')
  self.assertEqual(before,{q.name:q.read_bytes() for q in p.iterdir()})

class LifecycleTests(Fixture):
 def test_permission_required(self):
  c=self.core()
  with self.assertRaises(Rejected):c.start(':bad','unavailable:accelerometer')
 def test_unavailable_cannot_start(self):
  c=self.core();c.grant(':1')
  with self.assertRaises(Rejected):c.start(':1','unavailable:accelerometer')
 def test_owner_isolation(self):
  c,t=self.stream();c.tick()
  for fn in (lambda:c.read(':2',t),lambda:c.stop(':2',t),lambda:c.set_rate(':2',t,1)):
   with self.assertRaises(Rejected):fn()
  self.assertEqual(len(c.subscriptions),1)
 def test_background_explicit(self):
  c,t=self.stream();c.grant(':1',2,False)
  with self.assertRaises(Rejected):c.start(':1','iio:device0:ambient_light',2,True)
 def test_expiry_releases_cache(self):
  c,t=self.stream();c.tick();self.now+=301;c.tick()
  self.assertFalse(c.subscriptions);self.assertFalse(c.latest)
 def test_disconnect_releases_all(self):
  c,t=self.stream();c.tick();c.release(':1')
  self.assertFalse(c.grants);self.assertFalse(c.latest);self.assertFalse(c.subscriptions);self.assertFalse(c.due)
 def test_suspend_resume_requires_reauthorization(self):
  c,t=self.stream();c.tick();c.suspended=True;c.reset();c.suspended=False
  with self.assertRaises(Rejected):c.read(':1',t)
  self.assertFalse(c.latest)
 def test_saver_caps_polling(self):
  c,t=self.stream();c.saver=True;c.tick();self.assertEqual(c.effective_rate('iio:device0:ambient_light'),1)
  self.assertEqual(c.read(':1',t)['pollRateHz'],1)
  self.now+=.5
  with self.assertRaises(Rejected):c.read(':1',t)
 def test_stale_sample_not_returned(self):
  c,t=self.stream();c.tick();self.now+=3
  with self.assertRaises(Rejected):c.read(':1',t)
 def test_device_removal_invalidates(self):
  c,t=self.stream();c.tick();(self.iio/'iio:device0/in_illuminance_raw').unlink();self.now+=1;c.tick()
  self.assertNotIn('iio:device0:ambient_light',c.latest)
  with self.assertRaises(Rejected):c.read(':1',t)
 def test_nonfinite_measurement_invalidates(self):
  c,t=self.stream();c.tick();(self.iio/'iio:device0/in_illuminance_raw').write_text('nan');self.now+=1;c.tick()
  self.assertFalse(c.latest)
 def test_rate_bounds(self):
  for v in (True,0,-1,11,math.nan,math.inf,None,'garbage'):
   with self.assertRaises(Rejected):rate(v)
 def test_subscription_cap(self):
  c,t=self.stream()
  for n in range(7):c.start(':1','iio:device0:ambient_light')
  with self.assertRaises(Rejected):c.start(':1','iio:device0:ambient_light')
 def test_metadata_does_not_leak_samples(self):
  c,t=self.stream();c.tick();self.assertNotIn('latest',c.snapshot());self.assertFalse(c.snapshot()['history'])
 def test_motion_policy_cannot_be_enabled(self):
  c=self.core()
  for v in ({'rotationLock':False},{'autoRotate':True},{'motionControl':True},{'unknown':False},{'rotationLock':1}):
   with self.assertRaises(Rejected):c.configure(v)
  self.assertTrue(c.config['rotationLock'])

if __name__=='__main__':unittest.main()
