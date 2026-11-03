import importlib.util
from pathlib import Path
import tempfile
import unittest

spec = importlib.util.spec_from_file_location(
    'home_sync', Path(__file__).resolve().parents[1] / 'scripts/etherpocket-usb-home-sync.py')
sync = importlib.util.module_from_spec(spec)
spec.loader.exec_module(sync)


class HomeSyncTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.home, self.disk = self.root / 'home', self.root / 'disk'
        self.home.mkdir()
        self.disk.mkdir()
        self.state = self.root / 'state/state.json'

    def run_sync(self):
        sync.synchronize(self.home, self.disk, self.state)

    def test_home_initial_export_and_usb_import(self):
        (self.home / 'Documents').mkdir()
        (self.home / 'Documents/file.txt').write_text('phone')
        self.run_sync()
        self.assertEqual((self.disk / 'Documents/file.txt').read_text(), 'phone')
        (self.disk / 'Documents/file.txt').write_text('computer')
        self.run_sync()
        self.assertEqual((self.home / 'Documents/file.txt').read_text(), 'computer')
        self.assertEqual(next((self.state.parent / 'backups').rglob('file.txt')).read_text(), 'phone')

    def test_conflict_preserves_both_versions(self):
        (self.home / 'file.txt').write_text('initial')
        self.run_sync()
        (self.home / 'file.txt').write_text('phone')
        (self.disk / 'file.txt').write_text('computer')
        self.run_sync()
        self.assertEqual((self.home / 'file.txt').read_text(), 'phone')
        conflicts = list(self.home.glob('file.txt.usb-conflict-*'))
        self.assertEqual(len(conflicts), 1)
        self.assertEqual(conflicts[0].read_text(), 'computer')
        self.assertEqual((self.disk / conflicts[0].name).read_text(), 'computer')

    def test_usb_deletion_keeps_recoverable_backup(self):
        (self.home / 'file.txt').write_text('important')
        self.run_sync()
        (self.disk / 'file.txt').unlink()
        self.run_sync()
        self.assertFalse((self.home / 'file.txt').exists())
        self.assertEqual(next((self.state.parent / 'backups').rglob('file.txt')).read_text(), 'important')

    def test_phone_change_survives_usb_deletion(self):
        (self.home / 'file.txt').write_text('initial')
        self.run_sync()
        (self.disk / 'file.txt').unlink()
        (self.home / 'file.txt').write_text('changed')
        self.run_sync()
        self.assertEqual((self.disk / 'file.txt').read_text(), 'changed')

    def test_hidden_configuration_is_not_exported(self):
        (self.home / '.config').mkdir()
        (self.home / '.config/secret').write_text('private')
        (self.home / 'Documents').mkdir()
        self.run_sync()
        self.assertFalse((self.disk / '.config').exists())
        self.assertTrue((self.disk / 'Documents').is_dir())

    def test_reserved_name_blocks_export(self):
        if __import__('os').name == 'nt':
            self.skipTest('Windows cannot create a Linux filename containing colon')
        (self.home / 'unsafe:name').write_text('data')
        with self.assertRaises(RuntimeError):
            self.run_sync()
        self.assertFalse(self.state.exists())

    def test_symlink_path_cannot_be_overwritten(self):
        (self.disk / 'file.txt').write_text('computer')
        target = self.root / 'outside.txt'
        target.write_text('untouched')
        try:
            (self.home / 'file.txt').symlink_to(target)
        except OSError:
            self.skipTest('Symlinks unavailable')
        with self.assertRaises(RuntimeError):
            self.run_sync()
        self.assertEqual(target.read_text(), 'untouched')


if __name__ == '__main__':
    unittest.main()
