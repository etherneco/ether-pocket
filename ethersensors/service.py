#!/usr/bin/python3
"""Session-owned control API; samples are pulled only by authorized owners."""
import functools
import json
import signal
import time
import dbus
import dbus.service
from dbus.mainloop.glib import DBusGMainLoop
from gi.repository import GLib
from core import Core, Rejected, rate
from providers import Discovery
from identity import caller, foreground

NAME='com.etherneco.EtherSensors1';PATH='/com/etherneco/EtherSensors1'
def dump(value):return json.dumps(value,allow_nan=False,separators=(',',':'))
def document(value):
 if len(value)>8192:raise Rejected('Request too large')
 data=json.loads(str(value))
 if not isinstance(data,dict):raise Rejected('Expected object')
 return data
def guarded(fn):
 @functools.wraps(fn)
 def call(*a,**kw):
  try:return fn(*a,**kw)
  except (ValueError,OSError,KeyError,TypeError) as e:
   raise dbus.exceptions.DBusException(str(e)[:300],name=NAME+'.Rejected')
 return call

class Service(dbus.service.Object):
 def __init__(self):
  self.bus=dbus.SessionBus();self.system=dbus.SystemBus()
  self.name=dbus.service.BusName(NAME,self.bus,do_not_queue=True)
  super().__init__(self.bus,PATH)
  self.core=Core(Discovery());self.pending={};self.timer=0;self.last_status=None
  self.bus.add_signal_receiver(self.owner_changed,signal_name='NameOwnerChanged',dbus_interface='org.freedesktop.DBus',bus_name='org.freedesktop.DBus')
  self.bus.add_signal_receiver(self.lock_changed,signal_name='Changed',dbus_interface='com.etherneco.EtherLock1',bus_name='com.etherneco.EtherLock1')
  self.bus.add_signal_receiver(self.lock_owner,signal_name='NameOwnerChanged',dbus_interface='org.freedesktop.DBus',bus_name='org.freedesktop.DBus',arg0='com.etherneco.EtherLock1')
  self.system.add_signal_receiver(self.suspend,signal_name='PrepareForSleep',dbus_interface='org.freedesktop.login1.Manager',bus_name='org.freedesktop.login1')
  self.system.add_signal_receiver(self.power,signal_name='Changed',dbus_interface='com.etherneco.EtherPower1',bus_name='com.etherneco.EtherPower1')
  try:
   api=dbus.Interface(self.system.get_object('com.etherneco.EtherPower1','/com/etherneco/EtherPower1',introspect=False),'com.etherneco.EtherPower1')
   self.power(api.GetState(timeout=2))
  except dbus.DBusException:self.core.saver=True

 def unlocked(self):
  try:
   if not self.bus.name_has_owner('com.etherneco.EtherLock1'):return False
   api=dbus.Interface(self.bus.get_object('com.etherneco.EtherLock1','/com/etherneco/EtherLock1',introspect=False),'com.etherneco.EtherLock1')
   s=json.loads(str(api.GetState(timeout=1)))
   return s.get('ready') is True and s.get('locked') is False and s.get('phase')=='unlocked'
  except (dbus.DBusException,ValueError):return False

 def admin(self,sender):
  pid,app=caller(self.bus,sender)
  if app!='ethershell' or not self.unlocked():raise Rejected('Unlock and use the installed EtherShell Settings coordinator')

 def access(self,sender):
  pid,app=caller(self.bus,sender)
  if not self.unlocked():
   self.clear();raise Rejected('Sensor access unavailable while locked')
  grant=self.core.grants.get(sender,{})
  if not grant.get('background') and not foreground(app):
   self.core.release(sender);raise Rejected('Application no longer in foreground')
  return app

 def clear(self):
  self.pending.clear();self.core.reset();self.changed()

 @dbus.service.signal(NAME,signature='s')
 def Changed(self,state):pass
 def changed(self):
  status=dump(dict(self.core.snapshot(),pendingRequests=len(self.pending)))
  if status!=self.last_status:self.last_status=status;self.Changed(status)
 def ensure_timer(self):
  if not self.timer:self.timer=GLib.timeout_add(100,self.tick)
 def tick(self):
  now=time.monotonic()
  self.pending={k:v for k,v in self.pending.items() if now<v['expires']}
  if self.core.subscriptions:
   if not self.unlocked():self.clear()
   else:
    for owner in set(s['owner'] for s in self.core.subscriptions.values()):
     try:self.access(owner)
     except (Rejected,dbus.DBusException,OSError):self.core.release(owner)
    self.core.tick()
  self.changed()
  if not self.pending and not self.core.subscriptions:self.timer=0;return False
  return True
 def owner_changed(self,name,old,new):
  if str(name).startswith(':') and old and not new:
   self.core.release(str(name));self.pending.pop(str(name),None);self.changed()
 def lock_owner(self,name,old,new):
  if old:self.clear()
 def lock_changed(self,data):
  if not self.unlocked():self.clear()
 def suspend(self,sleeping):
  self.core.suspended=bool(sleeping);self.clear()
 def power(self,data):
  try:
   state=json.loads(str(data));profile=state.get('profile')
   self.core.saver=profile not in ('balanced','performance','original')
  except (ValueError,TypeError):self.core.saver=True

 @dbus.service.method(NAME,in_signature='',out_signature='s',sender_keyword='sender')
 @guarded
 def GetState(self,sender):caller(self.bus,sender);return dump(dict(self.core.snapshot(),pendingRequests=len(self.pending)))
 @dbus.service.method(NAME,in_signature='',out_signature='s',sender_keyword='sender')
 @guarded
 def ListSensors(self,sender):caller(self.bus,sender);return dump(list(self.core.rows.values()))
 @dbus.service.method(NAME,in_signature='',out_signature='s',sender_keyword='sender')
 @guarded
 def GetCapabilities(self,sender):
  caller(self.bus,sender)
  return dump(dict(apiVersion=1,capabilities={('sensors.'+r['type']):dict(status=r['status'],physical=r['physical'],verified=r['verified'],operational=False,reason=r['reason']) for r in self.core.rows.values()},
   maximumPollRate=10,hardwareRatesVerified=False,highFrequency=False,history=False,
   privacyBoundary='Managed API; same UID/X11 and direct kernel-device access are not isolated',calibration=False))
 @dbus.service.method(NAME,in_signature='s',out_signature='s',sender_keyword='sender')
 @guarded
 def GetSensorStatus(self,ident,sender):caller(self.bus,sender);return dump(self.core.rows[str(ident)])
 @dbus.service.method(NAME,in_signature='s',out_signature='s',sender_keyword='sender')
 @guarded
 def Configure(self,data,sender):self.admin(sender);self.core.configure(document(data));self.changed();return self.GetState(sender)
 @dbus.service.method(NAME,in_signature='s',out_signature='s',sender_keyword='sender')
 @guarded
 def RequestPermission(self,data,sender):
  pid,app=caller(self.bus,sender);opts=document(data)
  if set(opts)-{'rate','background'}:raise Rejected('Unknown permission option')
  hz=rate(opts.get('rate',2));bg=opts.get('background',False)
  if type(bg) is not bool:raise Rejected('background must be boolean')
  if not self.unlocked() or not foreground(app):raise Rejected('Unlock and focus the requesting application')
  if len(self.pending)>=32 and sender not in self.pending:raise Rejected('Request limit')
  self.pending[sender]=dict(owner=sender,app=app,rate=hz,background=bg,expires=time.monotonic()+60)
  self.ensure_timer();self.changed();return 'Review access in Settings → System → Sensors & Motion'
 @dbus.service.method(NAME,in_signature='',out_signature='s',sender_keyword='sender')
 @guarded
 def GetManagement(self,sender):
  self.admin(sender)
  return dump(dict(requests=list(self.pending.values()),grants=[dict(owner=k,**v) for k,v in self.core.grants.items() if time.monotonic()<v['expires']]))
 @dbus.service.method(NAME,in_signature='sb',out_signature='s',sender_keyword='sender')
 @guarded
 def ResolvePermission(self,owner,allow,sender):
  self.admin(sender);request=self.pending.pop(str(owner),None)
  if not request or time.monotonic()>=request['expires'] or not self.bus.name_has_owner(owner):raise Rejected('Request expired or client disconnected')
  if allow:self.core.grant(str(owner),request['rate'],request['background'])
  else:self.core.release(str(owner))
  self.changed();return self.GetManagement(sender)
 @dbus.service.method(NAME,in_signature='s',out_signature='',sender_keyword='sender')
 @guarded
 def RevokePermission(self,owner,sender):self.admin(sender);self.core.release(str(owner));self.changed()
 @dbus.service.method(NAME,in_signature='sdb',out_signature='s',sender_keyword='sender')
 @guarded
 def StartSubscription(self,ident,hz,background,sender):
  self.access(sender);token=self.core.start(str(sender),str(ident),hz,bool(background));self.ensure_timer();self.changed();return token
 @dbus.service.method(NAME,in_signature='s',out_signature='',sender_keyword='sender')
 @guarded
 def StopSubscription(self,token,sender):caller(self.bus,sender);self.core.stop(str(sender),str(token));self.changed()
 @dbus.service.method(NAME,in_signature='sd',out_signature='',sender_keyword='sender')
 @guarded
 def SetRequestedRate(self,token,hz,sender):self.access(sender);self.core.set_rate(str(sender),str(token),hz)
 @dbus.service.method(NAME,in_signature='s',out_signature='s',sender_keyword='sender')
 @guarded
 def ReadLatest(self,token,sender):self.access(sender);return dump(self.core.read(str(sender),str(token)))
 @dbus.service.method(NAME,in_signature='s',out_signature='s',sender_keyword='sender')
 @guarded
 def TestSensor(self,ident,sender):
  self.admin(sender)
  if not foreground('ethershell'):raise Rejected('Focus Settings to test a sensor')
  self.core.grant(str(sender),1,False)
  token=self.core.start(str(sender),str(ident),1,False)
  self.core.subscriptions[token]['expires']=time.monotonic()+30
  self.ensure_timer();self.changed();return token
 @dbus.service.method(NAME,in_signature='s',out_signature='s',sender_keyword='sender')
 @guarded
 def GetCalibrationStatus(self,ident,sender):
  caller(self.bus,sender);row=self.core.rows[str(ident)];return dump(dict(status=row['calibration'],supported=False,factoryDataTouched=False))
 @dbus.service.method(NAME,in_signature='s',out_signature='s',sender_keyword='sender')
 @guarded
 def RequestCalibration(self,ident,sender):self.admin(sender);raise Rejected('Calibration unavailable until real inputs and a validated workflow exist; factory data unchanged')
 @dbus.service.method(NAME,in_signature='',out_signature='s',sender_keyword='sender')
 @guarded
 def GetOrientation(self,sender):caller(self.bus,sender);return dump(dict(available=False,orientation=None,quaternion=None,absolute=False,reason='Real inputs not validated'))
 @dbus.service.method(NAME,in_signature='',out_signature='s',sender_keyword='sender')
 @guarded
 def GetMotionState(self,sender):caller(self.bus,sender);return dump(dict(available=False,angularVelocity=None,linearAcceleration=None,confidence=None,source='phone',headTracking=False))
 @dbus.service.method(NAME,in_signature='',out_signature='s',sender_keyword='sender')
 @guarded
 def ExportDiagnostics(self,sender):
  self.admin(sender)
  return dump(dict(schemaVersion=1,redacted=True,sensors=[{k:r.get(k) for k in ('type','physical','status','verified','units','calibration')} for r in self.core.rows.values()],fusion=self.core.snapshot()['fusion'],profile=self.core.snapshot()['profile']))

def main():
 DBusGMainLoop(set_as_default=True);service=Service();loop=GLib.MainLoop()
 def stop(*args):service.core.reset();loop.quit()
 signal.signal(signal.SIGTERM,stop);signal.signal(signal.SIGINT,stop)
 try:loop.run()
 finally:service.core.reset()
if __name__=='__main__':main()
