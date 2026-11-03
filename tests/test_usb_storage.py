"""Ownership gates must fail closed before either side can write."""
import importlib.util
from pathlib import Path
import subprocess
import unittest
from unittest.mock import Mock, patch

spec = importlib.util.spec_from_file_location(
    'usb_storage', Path(__file__).resolve().parents[1] / 'scripts/etherpocket-usb-storage.py')
storage = importlib.util.module_from_spec(spec)
spec.loader.exec_module(storage)


class OwnershipTests(unittest.TestCase):
    def setUp(self):
        marker = patch.object(storage, 'HOME_SYNC_ENABLED', Mock(exists=Mock(return_value=False)))
        marker.start()
        self.addCleanup(marker.stop)

    def test_sync_failure_blocks_export(self):
        storage.HOME_SYNC_ENABLED.exists.return_value = True
        with patch.object(storage, 'backing', return_value=''), \
             patch.object(storage.os.path, 'ismount', return_value=True), \
             patch.object(storage, 'synchronize_home', side_effect=RuntimeError('sync failed')), \
             patch.object(storage, 'write') as write:
            with self.assertRaises(RuntimeError):
                storage.export_usb()
            write.assert_not_called()

    def test_busy_local_filesystem_blocks_export(self):
        with patch.object(storage.os.path, 'ismount', return_value=True), \
             patch.object(storage, 'run', side_effect=subprocess.CalledProcessError(32, 'umount')), \
             patch.object(storage, 'write') as write:
            with self.assertRaises(subprocess.CalledProcessError):
                storage.export_usb()
            write.assert_not_called()

    def test_host_ownership_blocks_local_mount_and_repair(self):
        with patch.object(storage, 'backing', return_value='/image'), \
             patch.object(storage.subprocess, 'run') as run:
            with self.assertRaises(RuntimeError):
                storage.mount_local()
            run.assert_not_called()

    def test_failed_fat_check_blocks_local_mount(self):
        with patch.object(storage, 'backing', return_value=''), \
             patch.object(storage.os.path, 'ismount', return_value=False), \
             patch.object(storage.subprocess, 'run', return_value=Mock(returncode=4, stdout='bad FAT', stderr='')), \
             patch.object(storage, 'run') as run:
            with self.assertRaises(RuntimeError):
                storage.mount_local()
            run.assert_not_called()

    def test_unmount_precedes_host_ownership(self):
        events = []
        with patch.object(storage.os.path, 'ismount', return_value=True), \
             patch.object(storage, 'backing', return_value=''), \
             patch.object(storage, 'run', side_effect=lambda *args: events.append(args[0])), \
             patch.object(storage, 'write', side_effect=lambda *args: events.append('export')):
            storage.export_usb()
        self.assertEqual(events, ['umount', 'export'])


if __name__ == '__main__':
    unittest.main()
