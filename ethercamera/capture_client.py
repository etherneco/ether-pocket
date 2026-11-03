"""Reusable caller-owned capture client; inventory associations stay in the caller.

Keep this object/connection alive while the user reviews provisional captures.
Call confirm_photo(..., True) before associating a reference in the caller.
"""
import json
from core import CameraError

class CaptureClient:
    def __init__(self, api=None):
        if api is None:
            import dbus
            self.bus=dbus.SessionBus(private=True)
            api=dbus.Interface(self.bus.get_object('com.etherneco.EtherCamera1','/com/etherneco/EtherCamera1'),'com.etherneco.EtherCamera1')
        else:self.bus=None
        self.api=api;self.token=None;self.pending={}

    def request(self,device,purpose,consent=False,settings=None):
        if consent is not True:raise CameraError('Capture requires explicit user confirmation')
        if self.token:raise CameraError('Client already owns a session')
        self.token=str(self.api.RequestSession(device,purpose,True,json.dumps(settings or {})))
        return self.token

    def preview(self):
        if not self.token:raise CameraError('Request a session first')
        self.api.StartPreview(self.token)

    def frame_fd(self):
        if not self.token:raise CameraError('Request a session first')
        return self.api.GetFrame(self.token).take()

    def capture_photo(self):
        if not self.token:raise CameraError('Request a session first')
        data=json.loads(str(self.api.CapturePhoto(self.token)))
        self.pending[data['reference']]=data
        return dict(data)

    def confirm_photo(self,reference,accepted=False):
        if reference not in self.pending:raise CameraError('Reference was not captured by this request')
        if accepted is not True:raise CameraError('Photo requires explicit acceptance')
        return self.pending.pop(reference)

    def retake(self,reference):
        if reference not in self.pending:raise CameraError('Only an unconfirmed capture may be retaken')
        self.api.DeleteMedia(reference);self.pending.pop(reference)

    def scan(self,continuous=False):
        if not self.token:raise CameraError('Request a session first')
        return str(self.api.Scan(self.token,bool(continuous)))

    def job(self,reference):return json.loads(str(self.api.GetJob(reference)))

    def manual_code(self,format,text):return json.loads(str(self.api.ManualCode(format,text)))

    def record(self,microphone_consent=False):
        if not self.token:raise CameraError('Request a session first')
        if microphone_consent is True:self.api.StartRecordingWithAudio(self.token,True)
        elif microphone_consent is False:self.api.StartRecording(self.token)
        else:raise CameraError('Microphone consent must be boolean')

    def stop_recording(self):return json.loads(str(self.api.StopRecording(self.token,timeout=15)))

    def close(self):
        first_error=None
        for ref in list(self.pending):
            try:self.retake(ref)
            except Exception as e:first_error=first_error or e
        if self.token:
            try:self.api.Release(self.token,timeout=15)
            except Exception as e:first_error=first_error or e
            self.token=None
        if self.bus:self.bus.close();self.bus=None
        # On lock/service failure deletion may be denied. Existing media is
        # retained privately rather than bypassing permission checks to erase it.
        return first_error

    def __enter__(self):return self
    def __exit__(self,*unused):self.close()
