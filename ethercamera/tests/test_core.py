import io
import json
import os
from pathlib import Path
import sys
import tempfile
import unittest
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from core import CameraError, Library, Scanner, Sessions, options, role, manual_code, payload_details

class CoreTests(unittest.TestCase):
    def test_manual_code_checksum_and_provenance(self):
        code=manual_code('EAN-13','5901234123457')
        self.assertTrue(code['manual']);self.assertFalse(code['verifiedBySensor'])
        with self.assertRaises(CameraError):manual_code('EAN-13','5901234123456')
        with self.assertRaises(CameraError):manual_code('Code 39','lowercase')

    def test_wifi_contact_and_url_payloads_require_no_external_action(self):
        kind,data=payload_details(r'WIFI:T:WPA;S:Test\;SSID;P:secret\:value;H:true;;')
        self.assertEqual(kind,'wifi');self.assertEqual(data['ssid'],'Test;SSID')
        self.assertEqual(data['password'],'secret:value');self.assertTrue(data['hidden'])
        kind,data=payload_details('BEGIN:VCARD\nFN:Inventory Contact\nTEL:+44123456\nEND:VCARD')
        self.assertEqual(kind,'contact');self.assertEqual(data['FN'],['Inventory Contact'])
        self.assertEqual(payload_details('javascript:alert(1)')[0],'text')
        self.assertEqual(payload_details('https://example.invalid/')[0],'url')

    def test_actual_handset_nodes_are_never_camera_candidates(self):
        for driver,card,caps in [('msm_vidc_driver','msm_vidc_venc',69218304),('msm_vidc_driver','msm_vidc_vdec',69218304),('sde_rotator','sde_rotator',69238787),('cam_req_mgr','cam-req-mgr',0),('cam_sync','cam_sync',0)]:
            self.assertNotEqual(role(driver,card,caps),'capture-candidate')
        self.assertEqual(role('uvcvideo','USB camera',0x84000001),'capture-candidate')

    def test_lock_consent_busy_and_wrong_owner(self):
        sessions=Sessions()
        for consent,unlocked in [(False,True),(True,False),(False,False)]:
            with self.assertRaises(CameraError):sessions.acquire(':1.10','/dev/video8','Item photo',consent,unlocked)
        token=sessions.acquire(':1.10','/dev/video8','Item photo',True,True)
        with self.assertRaises(CameraError):sessions.check(':1.11',token)
        with self.assertRaises(CameraError):sessions.check(':1.10','wrong')
        with self.assertRaises(CameraError):sessions.acquire(':1.11','/dev/video8','Other',True,True)
        self.assertEqual(sessions.check(':1.10',token)['device'],'/dev/video8')
        sessions.release()
        with self.assertRaises(CameraError):sessions.check(':1.10',token)

    def test_capture_settings_reject_coercion_and_injection(self):
        for opt in [{'width':True},{'fps':1000},{'format':'RAW'},{'device':'/dev/video0'},{'width':'640 ! filesink'},[]]:
            with self.assertRaises(CameraError):options(opt)

    def test_private_library_lifecycle_and_metadata_allowlist(self):
        with tempfile.TemporaryDirectory() as tmp:
            lib=Library(Path(tmp)/'camera');ref,p=lib.allocate('.jpg');p.write_bytes(b'fixture')
            data=lib.commit(ref,'.jpg',dict(camera='test-fixture',width=20,height=10,gps=[1,2],latitude=1,kind='photo',album='Repair'))
            self.assertNotIn('gps',data);self.assertNotIn('latitude',data)
            self.assertEqual(lib.list('repair')[0]['reference'],ref)
            self.assertEqual(lib.list('other'),[])
            if os.name=='posix':self.assertEqual(p.stat().st_mode&0o777,0o600)
            lib.delete(ref);self.assertEqual(lib.list(),[])

    def test_library_rejects_traversal_empty_media_and_symlinks(self):
        with tempfile.TemporaryDirectory() as tmp:
            lib=Library(Path(tmp)/'camera')
            for ref in ['../secret','a'*33,'A'*32,'/etc/passwd']:
                with self.assertRaises(CameraError):lib.path(ref,'.jpg')
            ref,p=lib.allocate('.jpg')
            with self.assertRaises(CameraError):lib.commit(ref,'.jpg',{})
            if os.name=='posix':
                p.unlink();p.symlink_to(Path(tmp)/'secret')
                with self.assertRaises(CameraError):lib.path(ref,'.jpg')

    def test_documents_and_pdf_offline_fixtures(self):
        try:import cv2;import numpy as np;from PIL import Image
        except ImportError:self.skipTest('Optional OpenCV/Pillow unavailable')
        from documents import process,export_pdf
        img=np.zeros((600,800,3),dtype=np.uint8)
        cv2.fillConvexPoly(img,np.array([[130,70],[680,100],[710,530],[100,500]]),(255,255,255))
        _,data=cv2.imencode('.jpg',img)
        out,meta=process(data.tobytes(),rotation=90)
        self.assertTrue(meta['edgesDetected']);self.assertGreater(meta['width'],300)
        with self.assertRaises(ValueError):process(data.tobytes(),corners=[[0,0]]*4)
        with self.assertRaises(ValueError):process(data.tobytes(),corners=[[float('nan'),0]]*4)
        with tempfile.TemporaryDirectory() as tmp:
            target=Path(tmp)/'pages.pdf';export_pdf([out,out],target)
            self.assertTrue(target.read_bytes().startswith(b'%PDF'))

    def test_real_decoder_offline_fixtures_no_url_activation(self):
        try:import zxingcpp;from PIL import Image
        except ImportError:self.skipTest('Optional ZXing/Pillow unavailable')
        scanner=Scanner()
        for fmt,text in [(zxingcpp.BarcodeFormat.QRCode,'https://example.invalid/confirm'),(zxingcpp.BarcodeFormat.EAN13,'5901234123457'),(zxingcpp.BarcodeFormat.Code128,'REPAIR-012345')]:
            bitmap=zxingcpp.write_barcode(fmt,text,width=600,height=300)
            image=Image.fromarray(bitmap);stream=io.BytesIO();image.save(stream,'PNG')
            results=scanner.decode(stream.getvalue(),True)
            self.assertEqual(results[0]['text'],text);self.assertTrue(results[0]['requiresConfirmation'])
            self.assertEqual(scanner.decode(stream.getvalue(),True),[])
        stream=io.BytesIO();Image.new('RGB',(200,200),'white').save(stream,'PNG')
        self.assertEqual(scanner.decode(stream.getvalue()),[])

if __name__=='__main__':unittest.main()
