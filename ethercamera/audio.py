"""Explicit, per-recording microphone lease from the existing EtherAudio owner."""
import json
import os
from core import CameraError

class AudioLease:
    def __init__(self,bus):self.bus=bus;self.api=None;self.token=None;self.fd=None
    def start(self, consent, purpose):
        if consent is not True:raise CameraError('Separate microphone consent is required')
        if self.fd is not None:raise CameraError('Microphone lease already active')
        import dbus
        self.api=dbus.Interface(self.bus.get_object('com.etherneco.EtherAudio1','/com/etherneco/EtherAudio1',introspect=False),'com.etherneco.EtherAudio1')
        state=json.loads(str(self.api.GetState(timeout=3)))
        if not state.get('ready'):raise CameraError('EtherAudio unavailable')
        source=state.get('default-source','')
        if not source:raise CameraError('No microphone source selected in EtherAudio')
        token,handle=self.api.StartCapture(source,purpose[:200],True,dbus.UInt32(60),timeout=5)
        self.token=str(token)
        try:self.fd=handle.take()
        except Exception:self.stop();raise
        return self.fd

    def stop(self):
        # EOF is delivered before MP4 EOS so the mux can finish its audio track.
        if self.token is not None:
            try:self.api.StopCapture(self.token,timeout=3)
            except Exception:pass
            self.token=None

    def close(self):
        self.stop()
        if self.fd is not None:os.close(self.fd);self.fd=None
