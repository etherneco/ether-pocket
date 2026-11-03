import io,sys,time,unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from location_metadata import gps_exif
try:from PIL import Image
except ImportError:Image=None
@unittest.skipIf(Image is None,'Pillow required')
class LocationMetadataTests(unittest.TestCase):
    def test_gps_roundtrip_and_accuracy(self):
        # OFFLINE TEST DATA, never injected into the device location service.
        now=time.time();p=dict(latitude=-12.5,longitude=34.25,accuracy=15000,timestamp=now,kind='live',precision='approximate')
        exif=gps_exif(p);out=io.BytesIO();Image.new('RGB',(16,16)).save(out,'JPEG',exif=exif)
        gps=Image.open(io.BytesIO(out.getvalue())).getexif().get_ifd(34853)
        self.assertEqual(gps[1],'S');self.assertEqual(gps[3],'E');self.assertEqual(float(gps[31]),15000);self.assertNotIn(6,gps)
    def test_cached_manual_stale_or_invalid_rejected(self):
        p=dict(latitude=0,longitude=0,accuracy=5,timestamp=1000,kind='live')
        with self.assertRaises(ValueError):gps_exif(p,2000)
        for kind in ('manual','last-known'):
            with self.assertRaises(ValueError):gps_exif(dict(p,kind=kind),1000)
        with self.assertRaises(ValueError):gps_exif(dict(p,longitude=float('nan')),1000)
