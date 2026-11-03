import hashlib
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

SPEC = importlib.util.spec_from_file_location(
    'screenshot_sync', Path(__file__).resolve().parents[1] / 'scripts/windows-screenshot-sync.py')
sync = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(sync)
NAME = 'Screenshot-20261017-075831-585-e4dcc1e7.png'
DATA = b'\x89PNG\r\n\x1a\n' + b'test screenshot bytes'


class ScreenshotSyncTests(unittest.TestCase):
    def remote(self, command):
        if command.startswith('python3 '):
            return json.dumps([[NAME, len(DATA)]]).encode()
        return (hashlib.sha256(DATA).hexdigest() + '  screenshot.png\n').encode()

    def test_absent_usb_disk_does_not_contact_phone(self):
        with patch.object(sync, 'disk_identity', return_value=None), patch.object(sync, 'remote') as remote:
            sync.synchronize()
            remote.assert_not_called()

    def test_failed_transfer_leaves_no_partial_file_then_recovers(self):
        with tempfile.TemporaryDirectory() as directory:
            target = Path(directory)
            with patch.object(sync, 'DESTINATION', target), \
                    patch.object(sync, 'disk_identity', return_value=123), \
                    patch.object(sync, 'remote', side_effect=self.remote):
                def transfer(arguments):
                    Path(arguments[-1]).write_bytes(DATA[:9])
                with patch.object(sync, 'run', side_effect=transfer):
                    with self.assertRaisesRegex(RuntimeError, 'Incomplete'):
                        sync.synchronize()
                self.assertEqual(list(target.iterdir()), [])
                with patch.object(sync, 'run', side_effect=lambda args: Path(args[-1]).write_bytes(DATA)):
                    sync.synchronize()
                self.assertEqual((target / NAME).read_bytes(), DATA)

    def test_existing_host_file_is_preserved(self):
        with tempfile.TemporaryDirectory() as directory:
            target = Path(directory)
            (target / NAME).write_bytes(b'Windows edit')
            with patch.object(sync, 'DESTINATION', target), \
                    patch.object(sync, 'disk_identity', return_value=123), \
                    patch.object(sync, 'remote', side_effect=self.remote), \
                    patch.object(sync, 'run') as transfer:
                sync.synchronize()
                transfer.assert_not_called()
            self.assertEqual((target / NAME).read_bytes(), b'Windows edit')

    def test_drive_replacement_cancels_transfer(self):
        with patch.object(sync, 'disk_identity', side_effect=[123, 456]), \
                patch.object(sync, 'remote', side_effect=self.remote), \
                patch.object(sync, 'DESTINATION', Path('Z:/nonexistent-test-location')), \
                patch.object(sync, 'run') as transfer:
            sync.synchronize()
            transfer.assert_not_called()


if __name__ == '__main__':
    unittest.main()
