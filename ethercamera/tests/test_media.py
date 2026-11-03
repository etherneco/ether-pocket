import io
import os
from pathlib import Path
import sys
import tempfile
import unittest
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from core import CameraError,Library,Preferences,UsageHistory

class MediaTests(unittest.TestCase):
    def test_bounded_persisted_history_omits_sensitive_context(self):
        with tempfile.TemporaryDirectory() as tmp:
            path=Path(tmp)/'usage.json';history=UsageHistory(path)
            history.add('Capture error /home/private/photo.jpg QR-SECRET')
            self.assertNotIn('QR-SECRET',path.read_text())
            for _ in range(102):history.add('photo-saved')
            self.assertEqual(len(UsageHistory(path).entries),100)
            self.assertEqual(set(UsageHistory(path).entries[0]),{'event','timestamp'})

    def test_preferences_persist_validate_and_fail_closed(self):
        with tempfile.TemporaryDirectory() as tmp:
            path=Path(tmp)/'prefs.json';prefs=Preferences(path)
            prefs.update(dict(format='PNG',cameraPolicy='deny',width=1280,height=720))
            restored=Preferences(path)
            self.assertEqual(restored.data['cameraPolicy'],'deny')
            self.assertEqual(restored.capture_options({'fps':10}),dict(width=1280,height=720,fps=10,format='PNG'))
            self.assertEqual(restored.video_options(),dict(width=640,height=480,fps=15,format='JPEG'))
            for update in [{'cameraPolicy':'always-grant'},{'gps':True},{'videoAudio':'true'},{'width':False}]:
                with self.assertRaises(CameraError):restored.update(update)
            path.write_text('{broken',encoding='utf-8')
            self.assertEqual(Preferences(path).data['cameraPolicy'],'deny')
            self.assertTrue(Preferences(path).error)

    def test_thumbnail_album_search_export_and_delete_cache(self):
        from PIL import Image
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);lib=Library(root/'media');ref,p=lib.allocate('.jpg')
            Image.new('RGB',(1600,900),'navy').save(p)
            lib.commit(ref,'.jpg',dict(kind='photo',width=1600,height=900))
            data=lib.thumbnail(ref)
            image=Image.open(io.BytesIO(data));self.assertLessEqual(max(image.size),320)
            self.assertEqual(data,lib.thumbnail(ref))
            lib.set_album(ref,'Repair 42')
            self.assertEqual(lib.list(album='Repair 42')[0]['reference'],ref)
            self.assertEqual(lib.list(kind='video'),[])
            exported=lib.export(ref,root/'exports');self.assertEqual(exported.read_bytes(),p.read_bytes())
            with self.assertRaises(FileExistsError):lib.export(ref,root/'exports')
            with self.assertRaises(CameraError):lib.set_album(ref,'bad\nlabel')
            lib.delete(ref);self.assertFalse((root/'media/.thumbnails'/(ref+'.jpg')).exists())
            self.assertTrue(exported.exists())

    def test_recent_media_paging_does_not_sort_by_uuid(self):
        with tempfile.TemporaryDirectory() as tmp:
            lib=Library(tmp)
            for i in range(65):
                ref,p=lib.allocate('.png');p.write_bytes(b'offline-fixture')
                lib.commit(ref,'.png',dict(kind='photo'))
            first=lib.list(limit=50);second=lib.list(limit=50,offset=50)
            self.assertEqual(len(first),50);self.assertEqual(len(second),15)
            self.assertFalse({r['reference'] for r in first}&{r['reference'] for r in second})
            self.assertGreaterEqual(first[-1]['timestamp'],second[0]['timestamp'])

    @unittest.skipUnless(os.name=='posix','Linux symlinks required')
    def test_thumbnail_and_export_symlink_rejection(self):
        from PIL import Image
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);lib=Library(root/'media');ref,p=lib.allocate('.png')
            Image.new('RGB',(100,100),'red').save(p);lib.commit(ref,'.png',{})
            (lib.root/'.thumbnails').symlink_to(root,target_is_directory=True)
            with self.assertRaises(CameraError):lib.thumbnail(ref)
            (root/'exports').symlink_to(lib.root,target_is_directory=True)
            with self.assertRaises(CameraError):lib.export(ref,root/'exports')
