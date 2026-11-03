"""Supervise the native QMI helper without blocking D-Bus."""
import json
import os
import subprocess
import time
from gi.repository import GLib

class Gnss:
    def __init__(self,position,status,satellites):
        self.position=position;self.status=status;self.satellites=satellites
        self.process=None;self.active=False;self.stopping=False;self.ttff=None
        self.closed=lambda:None;self.buffer=b'';self.started=0;self.watch=0;self.terminal=False
    def start(self,interval=5):
        if self.process or self.stopping:return
        try:
            self.process=subprocess.Popen(['/usr/libexec/etherlocation-qmi','--private-json','--interval',str(max(5,min(300,int(interval))))],stdout=subprocess.PIPE,stderr=subprocess.DEVNULL,start_new_session=True)
            os.set_blocking(self.process.stdout.fileno(),False)
            self.active=True;self.buffer=b'';self.ttff=None;self.started=time.monotonic();self.terminal=False
            self.status('Initialising','')
            self.watch=GLib.io_add_watch(self.process.stdout.fileno(),GLib.IO_IN|GLib.IO_HUP|GLib.IO_ERR,self.read)
        except OSError:self.status('Unsupported','Native Qualcomm helper unavailable')
    def read(self,fd,condition):
        try:chunk=os.read(fd,65536)
        except BlockingIOError:return True
        if chunk:
            self.buffer+=chunk
            if len(self.buffer)>262144:self.stop();self.status('Error','GNSS helper message exceeds limit');return True
            while b'\n' in self.buffer:
                line,self.buffer=self.buffer.split(b'\n',1)
                try:
                    data=json.loads(line)
                    if data['event']=='position' and self.active:
                        if self.ttff is None:self.ttff=round(time.monotonic()-self.started,2)
                        self.position(data['position'])
                    elif data['event']=='satellites' and self.active:self.satellites(data['satellites'])
                    elif data['event']=='status' and self.active:
                        self.terminal=data['state'] in ('Error','Unsupported')
                        self.status(data['state'],data.get('error',''))
                except (ValueError,KeyError,TypeError):self.status('Error','Malformed GNSS helper report');self.stop()
            return True
        was_active=self.active;self.active=False;self.stopping=False
        self.process.stdout.close();self.process.wait(timeout=1);self.process=None;self.watch=0
        callback=self.closed;self.closed=lambda:None;callback()
        if was_active and not self.terminal:self.status('Error','GNSS helper exited unexpectedly')
        return False
    def stop(self,closed=None):
        if closed:self.closed=closed
        self.active=False
        if self.process and not self.stopping:self.stopping=True;self.process.terminate()
        elif not self.process:
            callback=self.closed;self.closed=lambda:None;callback()
