"""Managed API negative tests; no hardware service is constructed or injected."""
import json,sys,tempfile,time,unittest
from pathlib import Path
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
try:
 import dbus
 import service
 from core import Permissions,History,Geofences,options
except ImportError:service=None

@unittest.skipIf(service is None,'Linux D-Bus/GI runtime required')
class ServiceTests(unittest.TestCase):
 def harness(self):
  s=object.__new__(service.Service)
  s.bus=object();s.policy=Permissions();s.config=dict(enabled=True,grid=10000)
  s.sleeping=False;s.unlocked=lambda:True
  s.live=dict(latitude=51.5,longitude=-.12,accuracy=5,timestamp=time.time(),kind='live',provider='qualcomm-loc',altitude=10,heading=45,speed=1)
  s.last=dict(s.live);s.gnss=type('Lifecycle',(),dict(active=True))()
  return s
 def grant(self,s,precision='approximate',background=False):
  t=s.policy.request(':1.2','app',{});s.policy.resolve(t,'allow-while-using',precision,background)
 def test_ungranted_api_rejects_precise_and_cached(self):
  s=self.harness()
  with patch.object(service,'caller',return_value=(10,'app')),patch.object(service,'foreground',return_value=True):
   for method in (s.GetLocation,s.GetLastKnownLocation):
    with self.assertRaises(dbus.DBusException):method('{"precision":"precise"}',':1.2')
 def test_privacy_transform_applies_to_every_read(self):
  s=self.harness();self.grant(s)
  with patch.object(service,'caller',return_value=(10,'app')),patch.object(service,'foreground',return_value=True):
   for method in (s.GetLocation,s.GetLastKnownLocation):
    p=json.loads(method('{"precision":"precise"}',':1.2'));self.assertEqual(p['precision'],'approximate');self.assertNotEqual(p['latitude'],s.live['latitude']);self.assertNotIn('altitude',p)
   token=s.policy.subscribe(':1.2','app',options({'precision':'precise'}));p=json.loads(s.ReadUpdate(token,':1.2'));self.assertEqual(p['precision'],'approximate')
   with self.assertRaises(dbus.DBusException):s.ReadUpdate(token,':1.3')
   with self.assertRaises(dbus.DBusException):s.ReadUpdate(token,':1.2')
 def test_lock_revoke_disable_and_expired_live_deny(self):
  s=self.harness();self.grant(s,'precise')
  with patch.object(service,'caller',return_value=(10,'app')),patch.object(service,'foreground',return_value=True):
   s.unlocked=lambda:False
   with self.assertRaises(dbus.DBusException):s.GetLocation('{}',':1.2')
   s.unlocked=lambda:True;s.config['enabled']=False
   with self.assertRaises(dbus.DBusException):s.GetLastKnownLocation('{}',':1.2')
   s.config['enabled']=True;s.live['timestamp']=time.time()-60
   with self.assertRaises(dbus.DBusException):s.GetLocation('{}',':1.2')
   s.policy.revoke('app')
   with self.assertRaises(dbus.DBusException):s.GetLastKnownLocation('{}',':1.2')
 def test_arbitrary_sender_cannot_manage_permissions(self):
  s=self.harness()
  with patch.object(service,'caller',return_value=(10,'app')):
   with self.assertRaises(dbus.DBusException):s.ResolvePermission('any','allow-while-using','precise',True,':1.2')
 def test_cached_not_reported_live_after_hardware_stop(self):
  s=self.harness();self.grant(s,'precise');s.gnss.active=False
  with patch.object(service,'caller',return_value=(10,'app')),patch.object(service,'foreground',return_value=True):
   with self.assertRaises(dbus.DBusException):s.GetLocation('{}',':1.2')
   p=json.loads(s.GetLastKnownLocation('{}',':1.2'));self.assertEqual(p['kind'],'last-known')
 def test_browser_origin_denied_without_installed_bridge(self):
  s=self.harness()
  with patch.object(service,'caller',return_value=(10,'app')):
   with self.assertRaises(dbus.DBusException):s.RequestPermission('{"origin":"https://example.com"}',':1.2')
 def test_suspend_pauses_authorised_background_session_and_resume_revalidates(self):
  s=self.harness();self.grant(s,'precise',True);s.config['accuracy']='balanced';s.saver=False;s.test_until=0;s.state='Idle'
  opts=options({'background':True});token=s.policy.subscribe(':1.2','app',opts)
  class Lifecycle:
   active=True;stopping=False;starts=0
   def stop(self):self.active=False
   def start(self,interval):self.active=True;self.starts+=1
  s.gnss=Lifecycle();s.sleeping=True;s.reconcile()
  self.assertIn(token,s.policy.subscriptions);self.assertFalse(s.gnss.active);self.assertIsNone(s.live)
  s.sleeping=False;s.unlocked=lambda:False
  with patch.object(service,'caller',return_value=(10,'app')),patch.object(service,'foreground',return_value=False):s.reconcile()
  self.assertIn(token,s.policy.subscriptions);self.assertTrue(s.gnss.active);self.assertEqual(s.gnss.starts,1)
 def test_fresh_network_outlives_stale_gnss_without_gnss_label(self):
  s=self.harness();self.grant(s,'precise');s.live['timestamp']=time.time()-60
  s.network_live=dict(s.last,provider='geoclue',accuracy=30)
  with patch.object(service,'caller',return_value=(10,'app')),patch.object(service,'foreground',return_value=True):
   p=json.loads(s.GetLocation('{"precision":"precise"}',':1.2'));self.assertEqual(p['provider'],'geoclue');self.assertEqual(p['fixType'] if 'fixType' in p else 'network','network')
 def test_ip_requires_consent_and_existing_permission_before_worker(self):
  s=self.harness();s.ip_busy=False;errors=[];replies=[]
  with patch.object(service,'caller',return_value=(10,'app')),patch.object(service,'foreground',return_value=True),patch.object(service.threading,'Thread') as worker:
   s.GetIpLocation('{"endpoint":"https://example.org/ip","consent":false}',':1.2',replies.append,errors.append)
   s.GetIpLocation('{"endpoint":"https://example.org/ip","consent":true}',':1.2',replies.append,errors.append)
   self.assertEqual(len(errors),2);self.assertEqual(replies,[]);worker.assert_not_called()
 def test_ip_completion_rechecks_revocation(self):
  s=self.harness();self.grant(s,'precise');s.ip_busy=False;errors=[];replies=[];queued=[]
  s.ip=type('Ip',(),{'lookup':lambda obj,*args:dict(latitude=51,longitude=0,provider='ip',kind='approximate-region',timestamp=time.time(),accuracy=None)})()
  class Thread:
   def __init__(self,target,daemon):self.target=target
   def start(self):self.target()
  with patch.object(service,'caller',return_value=(10,'app')),patch.object(service,'foreground',return_value=True),patch.object(service.threading,'Thread',Thread),patch.object(service.GLib,'idle_add',side_effect=lambda *args:queued.append(args)):
   s.GetIpLocation('{"endpoint":"https://example.org/ip","consent":true}',':1.2',replies.append,errors.append)
   s.policy.revoke('app');callback,*args=queued[0];callback(*args)
   self.assertEqual(replies,[]);self.assertEqual(len(errors),1);self.assertFalse(s.ip_busy)

if __name__=='__main__':unittest.main()
