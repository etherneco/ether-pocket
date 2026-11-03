"""Capture UI acceptance on a private bus/display with OFFLINE-labelled JPEG.
Only this harness substitutes the sensor and sleep inhibitor. No production
source selector or mock mode is installed. No camera or microphone is opened.
"""
import argparse,json,os,runpy,secrets,subprocess,sys,tempfile,time
from pathlib import Path

POWER=r'''
import dbus,dbus.service,json,datetime
from dbus.mainloop.glib import DBusGMainLoop
from gi.repository import GLib
DBusGMainLoop(set_as_default=True)
class Power(dbus.service.Object):
 name='com.etherneco.EtherPower1'
 def __init__(self):
  self.owner=dbus.service.BusName(self.name,dbus.SessionBus());super().__init__(self.owner,'/com/etherneco/EtherPower1')
 @dbus.service.method(name,in_signature='',out_signature='s')
 def GetState(self):return json.dumps(dict(ready=True,timestamp=datetime.datetime.now(datetime.timezone.utc).isoformat(),capacity=75.,cpuTemperatureC=40.,gpuTemperatureC=35.,batteryTemperatureC=30.))
power=Power();GLib.MainLoop().run()
'''

BACKEND=r'''
import sys,os,time,json,datetime,dbus,dbus.service
from dbus.mainloop.glib import DBusGMainLoop
from gi.repository import GLib
DBusGMainLoop(set_as_default=True)
import service
from provider import UvcProvider
class Offline(UvcProvider):
 def start(self,device,settings,recording=None,audio_fd=None):
  assert device=='/dev/video999998' and audio_fd is None
  if os.environ['SCENARIO']=='start-failure':raise service.CameraError('OFFLINE start failure: sensor source unavailable')
  Gst=self.Gst
  description=self.description(settings,bool(recording)).replace('v4l2src name=source','videotestsrc name=source is-live=true ! video/x-raw,width=640,height=480 ! gdkpixbufoverlay location='+os.environ['FIXTURE_IMAGE'])
  print('OFFLINE pipeline:',description,flush=True)
  self.pipeline=Gst.parse_launch(description);self.recording=bool(recording);self.frames=0;self.latest=None;self.started=self.last_frame=time.monotonic()
  if recording:self.pipeline.get_by_name('recordfile').set_property('location',str(recording))
  self.pipeline.get_by_name('preview').connect('new-sample',self.sample)
  assert self.pipeline.set_state(Gst.State.PLAYING)!=Gst.StateChangeReturn.FAILURE
service.UvcProvider=Offline
device=dict(id='/dev/video999998',name='OFFLINE TEST — NOT A CAMERA',driver='uvcvideo',supportedProvider=True)
present=True
service.enumerate_devices=lambda:[]
if os.environ['SCENARIO'] not in ('blocked','wide'):
 service.enumerate_devices=lambda:[device] if present else []
service.Service.acquire_inhibitor=lambda self:None
service.Service.notice=lambda self,message:None
original_close=service.Service.close
def traced_close(self,reason):
 print('OFFLINE backend close:',reason,flush=True);return original_close(self,reason)
service.Service.close=traced_close
camera=service.Service()
class Fixture(dbus.service.Object):
 name='org.ethercamera.OfflineFixture'
 def __init__(self):
  self.bus=dbus.SessionBus();self.owner=dbus.service.BusName(self.name,self.bus);super().__init__(self.bus,'/fixture')
 @dbus.service.method(name,in_signature='',out_signature='')
 def Lock(self):
  api=dbus.Interface(self.bus.get_object('com.etherneco.EtherLock1','/com/etherneco/EtherLock1'),'com.etherneco.EtherLock1');api.FixtureLock(True)
 @dbus.service.method(name,in_signature='',out_signature='')
 def Disconnect(self):
  global present
  present=False;camera.devices=[];camera.error='Offline source disconnected';camera.close('Disconnected')
 @dbus.service.method(name,in_signature='',out_signature='')
 def StopBackend(self):GLib.timeout_add(100,lambda:os._exit(0))
 @dbus.service.method(name,in_signature='',out_signature='')
 def Deny(self):camera.Configure('{"cameraPolicy":"deny"}',self.bus.get_unique_name())
fixture=Fixture();GLib.MainLoop().run()
'''

def worker(args):
 import dbus
 from PIL import Image,ImageDraw
 out=Path(args.output);bus=dbus.SessionBus();results={}
 locker=runpy.run_path(str(Path(__file__).with_name('test-ethercamera-media.py')))['LOCKER']
 os.environ['DBUS_SYSTEM_BUS_ADDRESS']=os.environ['DBUS_SESSION_BUS_ADDRESS']
 for scenario in ['blocked','wide','capture','revoked','disconnected','owner-loss','background','denied','start-failure']:
  folder=out/scenario;folder.mkdir(exist_ok=True);children=[]
  with tempfile.TemporaryDirectory(prefix='ethercamera-offline-capture-') as tmp,(folder/'backend.log').open('w') as log:
   home=Path(tmp);image=Image.new('RGB',(640,480),'#173a51')
   draw=ImageDraw.Draw(image);draw.rectangle((30,120,610,360),fill='#284c63');draw.text((50,160),'OFFLINE TEST\nNOT A CAMERA FRAME',fill='white',font_size=30)
   fixture=home/'offline.jpg';image.save(fixture)
   env=dict(os.environ,HOME=tmp,PYTHONPATH=args.source,SCENARIO=scenario,FIXTURE_IMAGE=str(fixture))
   try:
    children.append(subprocess.Popen([sys.executable,'-c',POWER],env=env,stdout=log,stderr=log))
    children.append(subprocess.Popen([sys.executable,'-c',locker],env=env,stdout=log,stderr=log))
    for _ in range(60):
     if bus.name_has_owner('com.etherneco.EtherLock1') and bus.name_has_owner('com.etherneco.EtherPower1'):break
     time.sleep(.05)
    children.append(subprocess.Popen([sys.executable,'-c',BACKEND],env=env,stdout=log,stderr=log))
    for _ in range(100):
     if bus.name_has_owner('org.ethercamera.OfflineFixture'):break
     if children[-1].poll() is not None:raise RuntimeError((folder/'backend.log').read_text())
     time.sleep(.05)
    else:raise RuntimeError('Private backend failed to start')
    with (folder/'ui.log').open('w') as ui:
     app=subprocess.run([args.binary,scenario,str(folder)],env=env,stdout=ui,stderr=ui,timeout=80)
    if app.returncode:raise RuntimeError(scenario+': '+(folder/'result.json').read_text()+'\n'+(folder/'ui.log').read_text())
    result=json.loads((folder/'result.json').read_text());assert result['error']=='',result
    if scenario=='capture':
     assert result['photoReference']!=result['videoReference']
     media=home/'Pictures/EtherCamera'
     photo=Image.open(media/(result['photoReference']+'.jpg'));assert photo.size==(640,480)
     video=media/(result['videoReference']+'.mp4');assert video.stat().st_size>1000
     probe=json.loads(subprocess.check_output(['ffprobe','-v','error','-show_streams','-of','json',str(video)]))
     assert len(probe['streams'])==1 and probe['streams'][0]['codec_name']=='h264'
     assert float(probe['streams'][0]['duration'])>.5
     result['photoPixelsVerified']=True;result['videoH264Verified']=True
    if scenario!='owner-loss':
     api=dbus.Interface(bus.get_object('com.etherneco.EtherCamera1','/com/etherneco/EtherCamera1'),'com.etherneco.EtherCamera1')
     state=json.loads(str(api.GetState()));assert not state['active'] and not state['busy'],state
    assert not any(s in (folder/'ui.log').read_text() for s in ['qrc:/Capture.qml:', 'ReferenceError','TypeError'])
    results[scenario]=result
   finally:
    for child in reversed(children):
     if child.poll() is None:child.terminate()
     try:child.wait(timeout=5)
     except subprocess.TimeoutExpired:child.kill();child.wait()
    for _ in range(50):
     if not bus.name_has_owner('com.etherneco.EtherCamera1') and not bus.name_has_owner('com.etherneco.EtherLock1'):break
     time.sleep(.05)
 (out/'acceptance.json').write_text(json.dumps(results,indent=2)+'\n');print(json.dumps(results,indent=2))

def main():
 p=argparse.ArgumentParser();p.add_argument('--binary',required=True);p.add_argument('--source',required=True);p.add_argument('--output',required=True);p.add_argument('--worker',action='store_true');args=p.parse_args()
 if os.geteuid()==0:raise SystemExit('Run as unprivileged user')
 if args.worker:worker(args);return
 out=Path(args.output).absolute();out.mkdir(parents=True,exist_ok=True)
 if Path('/tmp/.X11-unix/X95').exists():raise RuntimeError('Private display :95 occupied')
 with tempfile.TemporaryDirectory(prefix='ethercamera-capture-display-') as tmp:
  root=Path(tmp);auth=root/'Xauthority';auth.touch(mode=0o600)
  subprocess.run(['xauth','-f',str(auth),'add',':95','MIT-MAGIC-COOKIE-1',secrets.token_hex(16)],check=True)
  runtime=root/'runtime';runtime.mkdir(mode=0o700)
  env=dict(os.environ,DISPLAY=':95',XAUTHORITY=str(auth),XDG_RUNTIME_DIR=str(runtime),QT_QPA_PLATFORM='xcb',QT_ENABLE_HIGHDPI_SCALING='0',LANG='C.UTF-8')
  env.pop('DBUS_SESSION_BUS_ADDRESS',None);env.pop('SESSION_MANAGER',None)
  with (out/'xserver.log').open('w') as log:
   server=subprocess.Popen(['Xvfb',':95','-screen','0','1280x1000x24','-dpi','264','-nolisten','tcp','-auth',str(auth)],env=env,stdout=log,stderr=log)
   try:
    for _ in range(50):
     if Path('/tmp/.X11-unix/X95').exists():break
     time.sleep(.1)
    subprocess.run(['dbus-run-session','--',sys.executable,str(Path(__file__).resolve()),'--binary',args.binary,'--source',args.source,'--output',str(out),'--worker'],env=env,check=True,timeout=300)
   finally:
    server.terminate()
    try:server.wait(timeout=5)
    except subprocess.TimeoutExpired:server.kill();server.wait()
if __name__=='__main__':main()
