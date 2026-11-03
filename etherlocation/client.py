"""Stable private-connection client; keep alive for owner-bound subscriptions."""
import json
class Client:
    def __init__(self):
        import dbus
        self.bus=dbus.SessionBus(private=True)
        self.api=dbus.Interface(self.bus.get_object('com.etherneco.EtherLocation1','/com/etherneco/EtherLocation1'),'com.etherneco.EtherLocation1')
        self.token=None
    def request_permission(self,**options):return str(self.api.RequestPermission(json.dumps(options)))
    def start(self,**options):self.token=str(self.api.StartUpdates(json.dumps(options)));return self.token
    def read(self):return json.loads(str(self.api.ReadUpdate(self.token)))
    def location(self,last_known=False,**options):return json.loads(str((self.api.GetLastKnownLocation if last_known else self.api.GetLocation)(json.dumps(options))))
    def stop(self):
        if self.token:self.api.StopUpdates(self.token);self.token=None
    def close(self):
        try:self.stop()
        finally:self.bus.close()
    def __enter__(self):return self
    def __exit__(self,*args):self.close()
if __name__=='__main__':
    import sys
    if sys.argv[1:]==['maps']:
        import os
        os.execv('/usr/bin/etherlocation-map',['etherlocation-map'])
    with Client() as client:
        if sys.argv[1:]==['capabilities']:print(client.api.GetCapabilities())
        else:print(client.api.GetState())
