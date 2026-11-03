"""Real GStreamer error path with an absent node; never a physical-frame test."""
from pathlib import Path
import sys
import unittest
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from core import CameraError
from provider import UvcProvider

class ProviderTests(unittest.TestCase):
    def setUp(self):
        try:self.provider=UvcProvider()
        except (ImportError,ValueError):self.skipTest('GStreamer GI runtime unavailable')
        if not self.provider.Gst.ElementFactory.find('v4l2src'):self.skipTest('V4L2 plugin unavailable')

    def tearDown(self):
        if hasattr(self,'provider'):self.provider.stop()

    def test_absent_hardware_errors_without_manufacturing_frames(self):
        with self.assertRaises(CameraError):self.provider.start('/dev/video999999',{})
        self.assertIsNone(self.provider.pipeline)
        self.assertEqual(self.provider.frames,0)
        with self.assertRaises(CameraError):self.provider.frame()

    def test_pipeline_injection_cannot_select_another_source(self):
        with self.assertRaises(CameraError):self.provider.start('/dev/video8 ! videotestsrc',{})
        self.assertIsNone(self.provider.pipeline)

    def test_offline_video_and_audio_fixture_mux(self):
        # Production always uses v4l2src. Only this test replaces its source in
        # the generated description, with an explicitly labelled offline fixture.
        import json,math,os,struct,subprocess,tempfile,threading,time
        import shutil
        if not shutil.which('ffprobe'):self.skipTest('Optional offline ffprobe verification unavailable')
        try:self.provider.recording_plugins(True)
        except CameraError as e:self.skipTest(str(e))
        Gst=self.provider.Gst
        readfd,writefd=os.pipe()
        try:
            with tempfile.TemporaryDirectory(prefix='ethercamera-offline-av-') as tmp:
                output=Path(tmp)/'OFFLINE-FIXTURE.mp4'
                description=self.provider.description({},True,True).replace('v4l2src name=source','videotestsrc name=source is-live=true')
                pipeline=Gst.parse_launch(description)
                pipeline.get_by_name('mic').set_property('fd',readfd)
                pipeline.get_by_name('recordfile').set_property('location',str(output))
                pipeline.get_by_name('preview').connect('new-sample',self.provider.sample)
                self.provider.pipeline=pipeline;self.provider.recording=True
                self.provider.started=time.monotonic();self.provider.last_frame=self.provider.started
                pcm=b''.join(struct.pack('<h',int(1000*math.sin(2*math.pi*440*i/16000))) for i in range(16000))
                def feed():
                    try:
                        for pos in range(0,len(pcm),3200):os.write(writefd,pcm[pos:pos+3200]);time.sleep(.1)
                    finally:os.close(writefd)
                worker=threading.Thread(target=feed)
                self.assertNotEqual(pipeline.set_state(Gst.State.PLAYING),Gst.StateChangeReturn.FAILURE)
                worker.start();worker.join(timeout=4);self.assertFalse(worker.is_alive())
                self.assertGreater(self.provider.frames,2)
                self.assertTrue(self.provider.stop(),'Offline mux EOS finalization failed')
                result=subprocess.run(['ffprobe','-v','error','-show_streams','-of','json',str(output)],capture_output=True,text=True,check=True)
                streams=json.loads(result.stdout)['streams']
                self.assertEqual({s['codec_name'] for s in streams},{'h264','aac'})
                self.assertTrue(all(float(s['duration'])>.5 for s in streams))
                self.assertLess(abs(float(streams[0]['start_time'])-float(streams[1]['start_time'])),.25)
                packets=json.loads(subprocess.check_output(['ffprobe','-v','error','-select_streams','a','-show_packets','-of','json',str(output)],text=True))['packets']
                pts=[float(p['pts_time']) for p in packets]
                self.assertTrue(all(a<b for a,b in zip(pts,pts[1:])), 'AAC timestamps must increase even across pipe bursts')
        finally:os.close(readfd)

if __name__=='__main__':unittest.main()
