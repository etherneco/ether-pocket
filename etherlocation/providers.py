"""Optional local gpsd receiver and explicitly enabled GeoClue adapters.

Never installs/starts either daemon, scans Wi-Fi, or chooses an online endpoint.
"""
import datetime
import json
import socket
import time
from core import position,Rejected

class Gpsd:
    """Existing, explicitly selected loopback gpsd receiver; no daemon startup."""
    def __init__(self,callback,status,satellites):
        self.callback=callback;self.status=status;self.satellites=satellites
        self.active=False;self.stopping=False;self.ttff=None;self.socket=None;self.watch=0;self.buffer=b''
    def start(self,interval=5):
        from gi.repository import GLib
        if self.active:return
        self.active=True;self.started=time.monotonic();self.status('Initialising','');self.buffer=b''
        self.socket=socket.socket();self.socket.setblocking(False);self.socket.connect_ex(('127.0.0.1',2947))
        self.watch=GLib.io_add_watch(self.socket.fileno(),GLib.IO_OUT|GLib.IO_ERR,self.connected)
    def connected(self,fd,condition):
        from gi.repository import GLib
        self.watch=0
        try:
            if self.socket.getsockopt(socket.SOL_SOCKET,socket.SO_ERROR):raise OSError('No local gpsd receiver')
            self.socket.sendall(b'?WATCH={"enable":true,"json":true};\n')
            self.watch=GLib.io_add_watch(fd,GLib.IO_IN|GLib.IO_HUP|GLib.IO_ERR,self.read);self.status('Searching','')
        except OSError as e:self.stop();self.status('Error',str(e))
        return False
    def read(self,fd,condition):
        try:
            chunk=self.socket.recv(65536)
            if not chunk:raise OSError('Local gpsd disconnected')
            self.buffer+=chunk
            if len(self.buffer)>131072:raise OSError('gpsd message limit exceeded')
            while b'\n' in self.buffer:
                row,self.buffer=self.buffer.split(b'\n',1)
                try:
                    data=json.loads(row)
                    if data.get('class')=='TPV':
                        p=gpsd_report(row)
                        if self.ttff is None:self.ttff=time.monotonic()-self.started
                        self.callback(p)
                    elif data.get('class')=='SKY':
                        names={0:'GPS',2:'Galileo',3:'BeiDou',6:'GLONASS'}
                        self.satellites([dict(id=s.get('svid',s.get('PRN')),constellation=names.get(s.get('gnssid'),'unknown'),signal=s.get('ss'),used=s.get('used')) for s in data.get('satellites',[])[:256]])
                except (ValueError,KeyError,TypeError):self.status('Fix lost','gpsd has no valid current fix')
            return True
        except BlockingIOError:return True
        except (OSError,ValueError):
            self.watch=0;self.stop();self.status('Error','Local gpsd receiver unavailable');return False
    def stop(self,closed=None):
        from gi.repository import GLib
        self.active=False
        if self.watch:GLib.source_remove(self.watch);self.watch=0
        if self.socket:self.socket.close();self.socket=None
        if closed:closed()

def gpsd_report(document):
    if len(document)>65536:raise Rejected('gpsd report too large')
    row=json.loads(document)
    if row.get('class')!='TPV' or row.get('mode',0)<2:raise Rejected('No gpsd fix')
    stamp=datetime.datetime.fromisoformat(row['time'].replace('Z','+00:00'))
    if stamp.tzinfo is None:raise Rejected('Receiver timestamp must include timezone')
    p=dict(latitude=row['lat'],longitude=row['lon'],accuracy=max(row['epx'],row['epy']),timestamp=stamp.timestamp(),provider='gpsd',fixType='3D' if row['mode']==3 else '2D')
    for src,dst in [('altMSL','altitude'),('epv','verticalAccuracy'),('speed','speed'),('track','heading')]:
        if src in row:p[dst]=row[src]
    return position(p)

class GeoClue:
    """Explicit opt-in required: an existing GeoClue deployment may use a network."""
    def __init__(self,bus,online_authorized=False,callback=None,status=None,satellites=None):
        if not online_authorized:raise Rejected('GeoClue may upload observations; separate online authorization required')
        self.bus=bus;self.client=None;self.active=False;self.stopping=False;self.ttff=None
        self.callback=callback;self.status=status;self.match=None
    def start(self,interval=30):
        import dbus
        manager=dbus.Interface(self.bus.get_object('org.freedesktop.GeoClue2','/org/freedesktop/GeoClue2/Manager'),'org.freedesktop.GeoClue2.Manager')
        self.client=manager.GetClient(timeout=3)
        obj=self.bus.get_object('org.freedesktop.GeoClue2',self.client)
        props=dbus.Interface(obj,'org.freedesktop.DBus.Properties')
        props.Set('org.freedesktop.GeoClue2.Client','DesktopId','etherlocation-map')
        props.Set('org.freedesktop.GeoClue2.Client','RequestedAccuracyLevel',dbus.UInt32(4))
        self.match=self.bus.add_signal_receiver(self.updated,signal_name='LocationUpdated',dbus_interface='org.freedesktop.GeoClue2.Client',bus_name='org.freedesktop.GeoClue2',path=self.client)
        dbus.Interface(obj,'org.freedesktop.GeoClue2.Client').Start(timeout=3)
        self.active=True;self.started=time.monotonic();self.status('Searching','')
    def updated(self,old,new):
        if not self.active:return
        import dbus
        try:
            row=dbus.Interface(self.bus.get_object('org.freedesktop.GeoClue2',new),'org.freedesktop.DBus.Properties').GetAll('org.freedesktop.GeoClue2.Location',timeout=2)
            stamp=row['Timestamp'];p=position(dict(latitude=float(row['Latitude']),longitude=float(row['Longitude']),accuracy=float(row['Accuracy']),timestamp=int(stamp[0])+int(stamp[1])/1e6,provider='geoclue',fixType='network'))
            if self.ttff is None:self.ttff=time.monotonic()-self.started
            self.callback(p)
        except (dbus.DBusException,ValueError,KeyError):self.status('Fix lost','GeoClue location unavailable')
    def stop(self,closed=None):
        self.active=False
        if self.match:self.match.remove();self.match=None
        if self.client:
            import dbus
            manager=dbus.Interface(self.bus.get_object('org.freedesktop.GeoClue2','/org/freedesktop/GeoClue2/Manager'),'org.freedesktop.GeoClue2.Manager')
            manager.DeleteClient(self.client,timeout=3);self.client=None
        if closed:closed()
