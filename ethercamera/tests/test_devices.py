import tempfile
from pathlib import Path
import sys
import unittest
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from devices import enumerate_devices,parse_formats

class DeviceTests(unittest.TestCase):
    def test_native_formats_keep_rates_separate_per_resolution_and_format(self):
        modes=parse_formats("[0]: 'YUYV' (YUYV)\n Size: Discrete 640x480\n Interval: Discrete 0.033s (30.000 fps)\n Interval: Discrete 0.067s (15.000 fps)\n[1]: 'MJPG' (JPEG)\n Size: Discrete 1280x720\n Interval: Discrete 0.033s (30.000 fps)")
        self.assertEqual(len(modes),2)
        self.assertEqual(modes[0],dict(pixelFormat='YUYV',width=640,height=480,frameRates=[30.0,15.0]))
        self.assertEqual(modes[1]['frameRates'],[30.0])

    def test_disappearing_node_during_hotplug_does_not_crash_discovery(self):
        with tempfile.TemporaryDirectory() as tmp:
            base=Path(tmp);(base/'video8').mkdir()
            # sysfs directory was seen, but its name attribute vanished.
            with patch('devices.Path',return_value=base),patch('spectra_provider.available',return_value=False),patch('devices.os.open',side_effect=AssertionError('No stale device may be opened')):
                self.assertEqual(enumerate_devices(),[])
