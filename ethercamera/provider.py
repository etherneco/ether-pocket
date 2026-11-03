"""Bounded external UVC GStreamer provider. No test source or vendor motor access."""
import threading
import time
from core import CameraError, options

class UvcProvider:
    def __init__(self):
        import gi
        gi.require_version('Gst','1.0')
        from gi.repository import Gst
        Gst.init(None);self.Gst=Gst
        self.pipeline=None;self.latest=None;self.lock=threading.Lock()
        self.frames=0;self.last_frame=0;self.started=0;self.recording=False
        self.audioEnded=False

    def recording_plugins(self,audio=False):
        required=['x264enc','h264parse','mp4mux']
        if audio:required+=['fdsrc','rawaudioparse','audioconvert','audioresample','voaacenc','aacparse']
        missing=[name for name in required if not self.Gst.ElementFactory.find(name)]
        if missing:raise CameraError('Recording plugins unavailable: '+', '.join(missing))

    def description(self, settings, recording=False, audio=False):
        s=options(settings);Gst=self.Gst
        # Single decoded preview buffer. Leaky queue prevents consumers blocking the sensor.
        text=('v4l2src name=source ! decodebin ! videoconvert ! videoscale ! videorate ! '
              f'video/x-raw,width={s["width"]},height={s["height"]},framerate={s["fps"]}/1 ! tee name=t '
              't. ! queue leaky=downstream max-size-buffers=1 ! jpegenc ! '
              'appsink name=preview emit-signals=true max-buffers=1 drop=true sync=false')
        if recording:
            if s['width']>640 or s['height']>480 or s['fps']>15:
                raise CameraError('Software video limited to 640x480 at 15 fps pending thermal acceptance')
            self.recording_plugins(audio)
            text+=' t. ! queue max-size-buffers=3 ! videoconvert ! video/x-raw,format=I420 ! x264enc tune=zerolatency speed-preset=ultrafast ! h264parse ! mp4mux name=mux ! filesink name=recordfile'
            if audio:
                # Timestamp PCM by sample count. Pipe reads may arrive in bursts;
                # wall-clock timestamps on each read create overlapping AAC PTS.
                text+=' fdsrc name=mic blocksize=4096 do-timestamp=false ! rawaudioparse format=pcm pcm-format=s16le sample-rate=16000 num-channels=1 ! queue ! audioconvert ! audioresample ! voaacenc ! aacparse ! queue ! mux.'
        return text

    def start(self, device, settings, recording=None, audio_fd=None):
        import re
        if not re.fullmatch(r'/dev/video[0-9]+',device):raise CameraError('Invalid node')
        if self.pipeline:raise CameraError('Provider already running')
        text=self.description(settings,bool(recording),audio_fd is not None);Gst=self.Gst
        pipeline=Gst.parse_launch(text)
        if pipeline.get_by_name('source').find_property('device'):
            pipeline.get_by_name('source').set_property('device',device)
        if recording:pipeline.get_by_name('recordfile').set_property('location',str(recording))
        self.audioEnded=False
        if audio_fd is not None:
            mic=pipeline.get_by_name('mic');mic.set_property('fd',audio_fd)
            def audio_event(pad,info):
                event=info.get_event()
                if event and event.type==Gst.EventType.EOS:self.audioEnded=True
                return Gst.PadProbeReturn.OK
            mic.get_static_pad('src').add_probe(Gst.PadProbeType.EVENT_DOWNSTREAM,audio_event)
        pipeline.get_by_name('preview').connect('new-sample',self.sample)
        self.pipeline=pipeline;self.recording=bool(recording)
        self.latest=None;self.frames=0;self.started=time.monotonic();self.last_frame=self.started
        if pipeline.set_state(Gst.State.PLAYING)==Gst.StateChangeReturn.FAILURE:
            self.stop();raise CameraError('Camera pipeline failed to start')

    def sample(self, sink):
        Gst=self.Gst
        sample=sink.emit('pull-sample')
        if sample is None:return Gst.FlowReturn.ERROR
        buf=sample.get_buffer()
        if buf.get_size()>16*1024*1024:return Gst.FlowReturn.ERROR
        data=buf.extract_dup(0,buf.get_size())
        caps=sample.get_caps().get_structure(0)
        with self.lock:
            self.latest=(data,caps.get_value('width'),caps.get_value('height'))
            self.frames+=1;self.last_frame=time.monotonic()
        return Gst.FlowReturn.OK

    def frame(self):
        with self.lock:
            if not self.latest or time.monotonic()-self.last_frame>2:raise CameraError('No fresh physical camera frame')
            return self.latest

    def error(self):
        if not self.pipeline:return ''
        msg=self.pipeline.get_bus().pop_filtered(self.Gst.MessageType.ERROR|self.Gst.MessageType.EOS)
        if msg:
            if msg.type==self.Gst.MessageType.ERROR:return msg.parse_error()[0].message[:400]
            return 'Camera stream ended'
        if time.monotonic()-self.last_frame>8:return 'Camera frame timeout or disconnected'
        return ''

    def stop(self):
        pipeline=self.pipeline
        if not pipeline:return True
        ok=True
        try:
            if self.recording:
                pipeline.send_event(self.Gst.Event.new_eos())
                msg=pipeline.get_bus().timed_pop_filtered(5*self.Gst.SECOND,self.Gst.MessageType.EOS|self.Gst.MessageType.ERROR)
                ok=bool(msg and msg.type==self.Gst.MessageType.EOS)
        finally:
            pipeline.set_state(self.Gst.State.NULL)
            pipeline.get_state(2*self.Gst.SECOND)
            self.pipeline=None;self.latest=None;self.recording=False
        return ok
