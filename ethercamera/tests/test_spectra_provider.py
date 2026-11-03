"""Policy and bounded transport checks; no native hardware opened by tests."""
import sys
from pathlib import Path
import unittest
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from spectra_provider import SpectraProvider,available,DEVICE
from core import CameraError

class SpectraTests(unittest.TestCase):
    def test_unprovisioned_board_never_starts_native_worker(self):
        provider=SpectraProvider()
        with patch('spectra_provider.available',return_value=False),patch('spectra_provider.subprocess.Popen',side_effect=AssertionError('No worker permitted')):
            with self.assertRaises(CameraError):provider.start(DEVICE,{})
        self.assertIsNone(provider.pipeline)

    def test_native_source_has_bounded_buffers_and_no_test_pattern(self):
        provider=SpectraProvider();text=provider.description({})
        self.assertIn('max-bytes=921600 leaky-type=downstream',text)
        self.assertIn('format=RGB,width=640,height=480',text)
        self.assertNotIn('v4l2src',text);self.assertNotIn('videotestsrc',text)
        pipeline=provider.Gst.parse_launch(text)
        pipeline.set_state(provider.Gst.State.NULL)
