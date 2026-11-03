"""Rear IMX586 provider using the matching native downstream Spectra worker."""
import os
from pathlib import Path
import subprocess
import threading
from core import CameraError
from provider import UvcProvider

DEVICE='spectra:rear-imx586'
WORKER='/usr/libexec/ethercamera/ethercamera-spectra-capture'
PLAN='/usr/share/ethercamera/spectra/rear-plan.json'

def available():
    try:
        if os.uname().release!='4.14.117-perf' or os.uname().machine!='aarch64':return False
        if Path('/proc/device-tree/model').read_bytes().rstrip(b'\0')!=b'SDX50M MTP 18827 15':return False
        for name in (WORKER,PLAN):
            p=Path(name);s=p.stat()
            if p.is_symlink() or s.st_uid!=0 or s.st_mode&0o022:return False
        return True
    except OSError:return False

def device():
    return dict(id=DEVICE,name='OnePlus — tylna kamera IMX586',driver='ethercamera-spectra',
        role='capture-candidate',supportedProvider=True,connected=True,busy=None,operational=None,
        previewVerified=False,stillVerified=False,videoVerified=False,
        modes=[dict(pixelFormat='RGB',width=640,height=480,frameRates=[15])],pixelFormats=['RGB'],
        focusControls=[],exposureControls=[],flashAvailable=False,
        limitations='Fixed sensor exposure/focus; software RGB conversion; rear main only')

class SpectraProvider(UvcProvider):
    def __init__(self):
        super().__init__();self.worker=None;self.reader=None;self.stopping=False;self.worker_error=''

    def description(self,settings,recording=False,audio=False):
        text=super().description(settings,recording,audio)
        return text.replace('v4l2src name=source ! decodebin',
            'appsrc name=source is-live=true do-timestamp=true format=time block=false max-bytes=921600 leaky-type=downstream caps="video/x-raw,format=RGB,width=640,height=480,framerate=15/1"')

    def start(self,device,settings,recording=None,audio_fd=None):
        if device!=DEVICE or not available():raise CameraError('Native rear camera driver unavailable')
        # Base class validates UVC names; native identity is checked separately.
        super().start('/dev/video0',settings,recording,audio_fd)
        self.stopping=False;self.worker_error=''
        try:
            self.worker=subprocess.Popen([WORKER,PLAN,'--rgb-stream'],stdout=subprocess.PIPE,
                stderr=subprocess.DEVNULL,close_fds=True)
            self.reader=threading.Thread(target=self.read_frames,daemon=True);self.reader.start()
        except Exception:self.stop();raise

    def read_frames(self):
        worker=self.worker;pipeline=self.pipeline;size=640*480*3
        try:
            while not self.stopping:
                data=bytearray()
                while len(data)<size:
                    chunk=worker.stdout.read(size-len(data))
                    if not chunk:
                        if not self.stopping:self.worker_error='Native rear camera stream ended'
                        return
                    data.extend(chunk)
                if self.stopping:return
                buffer=self.Gst.Buffer.new_allocate(None,size,None);buffer.fill(0,bytes(data))
                if pipeline.get_by_name('source').emit('push-buffer',buffer)!=self.Gst.FlowReturn.OK:
                    if not self.stopping:self.worker_error='Native preview pipeline stopped'
                    return
        except (OSError,ValueError) as e:
            if not self.stopping:self.worker_error=str(e)[:200]

    def error(self):return self.worker_error or super().error()

    def stop(self):
        self.stopping=True;worker=self.worker
        if worker and worker.poll() is None:
            worker.terminate()
            try:worker.wait(timeout=6)
            except subprocess.TimeoutExpired:worker.kill();worker.wait(timeout=2)
        if worker and worker.stdout:worker.stdout.close()
        if self.reader:self.reader.join(timeout=1)
        self.worker=None;self.reader=None
        return super().stop()
