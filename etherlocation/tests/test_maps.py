import io,json,sqlite3,sys,tempfile,unittest,hashlib,threading
from unittest.mock import patch
from pathlib import Path
from contextlib import contextmanager
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from core import Rejected
from maps import Maps,inspect,NoRedirect
PNG=bytes.fromhex('89504e470d0a1a0a')+b'TEST ONLY: validation fixture, never an actual map'
@contextmanager
def database(path):
    db=sqlite3.connect(path)
    try:
        with db:yield db
    finally:db.close()
class MapTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.root=Path(self.temp.name);self.maps=Maps(self.root/'maps');self.source=self.root/'fixture.mbtiles'
        with database(self.source) as db:
            db.execute('CREATE TABLE metadata(name,value)');db.executemany('INSERT INTO metadata VALUES(?,?)',[('format','png'),('attribution','TEST ONLY')])
            db.execute('CREATE TABLE tiles(zoom_level,tile_column,tile_row,tile_data)');db.execute('INSERT INTO tiles VALUES(0,0,0,?)',(PNG,))
    def tearDown(self):self.temp.cleanup()
    def test_import_requires_license_and_deletion_is_bounded(self):
        with self.assertRaises(Rejected):self.maps.import_file(self.source)
        row=self.maps.import_file(self.source,True);self.assertTrue(self.maps.regions()[0]['available'])
        with self.assertRaises(Rejected):self.maps.delete('../fixture')
        self.maps.delete(row['id']);self.assertFalse(self.maps.regions());self.assertTrue(self.source.exists())
    def test_vector_and_missing_attribution_rejected(self):
        with database(self.source) as db:db.execute("UPDATE metadata SET value='pbf' WHERE name='format'")
        with self.assertRaises(Rejected):inspect(self.source)
        with database(self.source) as db:db.execute("UPDATE metadata SET value='png' WHERE name='format'");db.execute("DELETE FROM metadata WHERE name='attribution'")
        with self.assertRaises(Rejected):inspect(self.source)
    def test_network_denied_before_request(self):
        for url,license in [('https://example.com/map',False),('http://example.com/map',True),('https://tile.openstreetmap.org/x',True),('https://a.tile.openstreetmap.org/x',True)]:
            with self.assertRaises(Rejected):self.maps.download(url,'0'*64,license)
        with self.assertRaises(Rejected):self.maps.download('https://example.com/map','bad',True)
        with self.assertRaises(Rejected):NoRedirect().redirect_request(None,None,None,None,None,None)
    def test_real_world_dataset_when_available(self):
        path=Path(__file__).resolve().parents[2]/'build/etherlocation-world-overview.mbtiles'
        if not path.exists():self.skipTest('Optional overview dataset not built')
        row=inspect(path);self.assertEqual(row['minZoom'],0);self.assertEqual(row['maxZoom'],3);self.assertIn('Natural Earth',row['attribution'])
    def test_download_hash_pause_and_valid_range_resume(self):
        data=self.source.read_bytes();digest=hashlib.sha256(data).hexdigest();url='https://licensed.example/offline.mbtiles';seen=[]
        class Response(io.BytesIO):pass
        def open(request,timeout):
            start=int(request.headers.get('Range','bytes=0-').split('=')[1].split('-')[0]);seen.append(start)
            r=Response(data[start:]);r.status=206 if start else 200;r.headers={'Content-Length':str(len(data)-start),'Content-Range':f'bytes {start}-{len(data)-1}/{len(data)}'};return r
        transport=type('Transport',(),{'open':staticmethod(open)})()
        # Real SQLite fixture, fake transport only; no test coordinates are sent.
        with patch('maps.urllib.request.build_opener',return_value=transport):
            key=hashlib.sha256((url+digest).encode()).hexdigest()[:32];(self.maps.root/(key+'.part')).write_bytes(data[:100])
            row=self.maps.download(url,digest,True);self.assertEqual(row['state'],'complete');self.assertEqual(seen,[100]);self.assertTrue(self.maps.regions()[0]['available'])
    def test_checksum_mismatch_does_not_install(self):
        data=self.source.read_bytes()
        class Response(io.BytesIO):pass
        r=Response(data);r.status=200;r.headers={'Content-Length':str(len(data))}
        transport=type('Transport',(),{'open':lambda *a,**k:r})()
        with patch('maps.urllib.request.build_opener',return_value=transport):
            with self.assertRaises(Rejected):self.maps.download('https://licensed.example/offline','0'*64,True)
        self.assertFalse(self.maps.regions());self.assertFalse(list(self.maps.root.glob('*.part')))
if __name__=='__main__':unittest.main()
