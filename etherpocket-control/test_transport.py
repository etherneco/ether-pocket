import io
from pathlib import Path
import tempfile
import unittest
from transport import frames, map_pointer, ssh_command


class TransportTests(unittest.TestCase):
    def test_pointer_letterboxing_and_edges(self):
        self.assertIsNone(map_pointer(9, 20, (10, 20, 100, 200), (1440, 3120)))
        self.assertEqual(map_pointer(60, 120, (10, 20, 100, 200), (1440, 3120)), (720, 1560))
        self.assertEqual(map_pointer(109, 219, (10, 20, 100, 200), (1440, 3120)), (1425, 3104))

    def test_jpeg_stream_multiple_frames_and_split_markers(self):
        class Chunked:
            def __init__(self): self.parts = iter([b'\xff', b'\xd8abc\xff', b'\xd9\xff\xd8def\xff\xd9', b''])
            def read(self, count): return next(self.parts)
        self.assertEqual(list(frames(Chunked())), [b'\xff\xd8abc\xff\xd9', b'\xff\xd8def\xff\xd9'])

    def test_truncated_frame_fails(self):
        with self.assertRaises(ValueError): list(frames(io.BytesIO(b'\xff\xd8unfinished')))

    def test_ssh_rejects_options_and_requires_verified_host(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder)/'key'; path.write_text('test')
            with self.assertRaises(ValueError): ssh_command('-oProxyCommand=bad', path, path)
            command = ssh_command('10.77.0.2', path, path)
            self.assertIn('StrictHostKeyChecking=yes', command)
            self.assertIn('BatchMode=yes', command)


if __name__ == '__main__': unittest.main()
