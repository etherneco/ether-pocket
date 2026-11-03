import io
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch
ROOT=Path(__file__).resolve().parents[2]
sys.path[:0]=[str(ROOT/'etherlocation'),str(ROOT/'ethermap')]
from core import Rejected
from ip_provider import IpProvider,disclose_ip
from network import Providers


class NetworkTests(unittest.TestCase):
    def setUp(self):self.temp=tempfile.TemporaryDirectory();self.root=Path(self.temp.name)
    def tearDown(self):self.temp.cleanup()
    def test_ip_consent_before_any_network_or_cache(self):
        with patch('urllib.request.build_opener') as request:
            with self.assertRaises(Rejected):IpProvider(self.root/'ip.json').lookup('https://example.org/ip')
            request.assert_not_called();self.assertFalse((self.root/'ip.json').exists())
    def test_approximate_ip_permission_preserves_unknown_accuracy(self):
        row=dict(latitude=51.5,longitude=-.1,accuracy=None,provider='ip',kind='approximate-region',timestamp=1000)
        out=disclose_ip(row,'approximate',10000)
        self.assertNotEqual(out['latitude'],row['latitude']);self.assertIsNone(out['accuracy']);self.assertEqual(out['kind'],'approximate-region')
    def test_ip_unknown_accuracy_stays_unknown_and_cache_persists(self):
        with patch('urllib.request.build_opener') as opener:
            opener.return_value.open.return_value=io.BytesIO(json.dumps(dict(latitude=51,longitude=0,city='London')).encode())
            p=IpProvider(self.root/'ip.json').lookup('https://example.org/ip',True,now=10000)
            self.assertIsNone(p['accuracy']);self.assertEqual(p['provider'],'ip')
            p=IpProvider(self.root/'ip.json').lookup('https://example.org/ip',True,now=10010)
            self.assertTrue(p['cached']);self.assertEqual(opener.call_count,1)
    def test_ip_failure_is_rate_limited_across_restart(self):
        with patch('urllib.request.build_opener') as opener:
            opener.return_value.open.side_effect=OSError('offline')
            with self.assertRaises(OSError):IpProvider(self.root/'ip.json').lookup('https://example.org/ip',True,now=10000)
            with self.assertRaises(Rejected):IpProvider(self.root/'ip.json').lookup('https://example.org/ip',True,now=10001)
            self.assertEqual(opener.call_count,1)
    def test_unsafe_endpoints_rejected(self):
        for url in ('http://example.org/ip','https://user:secret@example.org/ip','https://example.org/ip#fragment'):
            with self.assertRaises(Rejected):IpProvider(self.root/'ip.json').lookup(url,True)
    def test_offline_cached_ip_retains_timestamp_and_is_stale(self):
        with patch('urllib.request.build_opener') as opener:
            opener.return_value.open.return_value=io.BytesIO(b'{"latitude":51,"longitude":0}')
            provider=IpProvider(self.root/'ip.json');provider.lookup('https://example.org/ip',True,now=10000)
            opener.return_value.open.side_effect=OSError('offline')
            p=provider.lookup('https://example.org/ip',True,now=14000)
            self.assertTrue(p['stale']);self.assertEqual(p['timestamp'],10000);self.assertEqual(p['age'],4000)
    def test_search_explicit_consent_and_cache(self):
        provider=Providers(self.root/'search')
        with self.assertRaises(Rejected):provider.search('London','https://example.org/search',False)
        with patch.object(provider,'request',return_value=[dict(lat='51',lon='0',display_name='London')]) as request:
            a=provider.search('London','https://example.org/search',True)
            b=provider.search('London','https://example.org/search',True)
            self.assertEqual(a,b);self.assertEqual(request.call_count,1)
    def test_routing_preserves_real_service_geometry(self):
        provider=Providers(self.root)
        response=dict(code='Ok',routes=[dict(distance=200,duration=60,geometry=dict(coordinates=[[0,51],[.001,51.001]]),legs=[dict(steps=[dict(distance=200,name='Road',maneuver=dict(type='turn',modifier='left'))])])])
        with patch.object(provider,'request',return_value=response) as req:
            p=provider.route(dict(latitude=51,longitude=0),dict(latitude=51.001,longitude=.001),'https://example.org/route/v1/driving',True)
            self.assertEqual(p['line'][1]['longitude'],.001);self.assertFalse(p['traffic']);self.assertFalse(p['offline'])
            self.assertIn('turn left',p['steps'][0]['text']);self.assertIn('geometries=geojson',req.call_args[0][0])
    def test_routing_no_route_does_not_draw_direct_line(self):
        provider=Providers(self.root)
        with patch.object(provider,'request',return_value={'code':'NoRoute'}):
            with self.assertRaises(Rejected):provider.route(dict(latitude=51,longitude=0),dict(latitude=52,longitude=0),'https://example.org/route/v1/driving',True)
