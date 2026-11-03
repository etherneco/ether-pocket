"""Real private D-Bus/gallery acceptance; OFFLINE media, no sensor/microphone.
The locker fixture exists only on a disposable bus. Production backend/UI
run unchanged with private HOME and a private system-bus address.
"""
import argparse,json,os,secrets,subprocess,sys,tempfile,time
from pathlib import Path
LOCKER=r'''
import dbus,dbus.service,json
from dbus.mainloop.glib import DBusGMainLoop
from gi.repository import GLib
DBusGMainLoop(set_as_default=True)
class Lock(dbus.service.Object):
 name='com.etherneco.EtherLock1'
 def __init__(self):
  self.bus=dbus.SessionBus();self.owner=dbus.service.BusName(self.name,self.bus);super().__init__(self.bus,'/com/etherneco/EtherLock1');self.locked=False
 @dbus.service.method(name,in_signature='',out_signature='s')
 def GetState(self):return json.dumps(dict(ready=True,locked=self.locked,phase='locked' if self.locked else 'unlocked'))
 @dbus.service.signal(name,signature='s')
 def Changed(self,document):pass
 @dbus.service.method(name,in_signature='b',out_signature='')
 def FixtureLock(self,value):self.locked=bool(value);self.Changed(self.GetState())
lock=Lock();GLib.MainLoop().run()
'''

def worker(args):
    import dbus
    source=Path(args.source);sys.path.insert(0,str(source))
    from core import Library
    from PIL import Image,ImageDraw
    lib=Library(Path.home()/'Pictures/EtherCamera');references=[]
    for color in ['#163f72','#2a6d68','#6e4067']:
        ref,p=lib.allocate('.jpg');image=Image.new('RGB',(1280,720),color)
        ImageDraw.Draw(image).text((60,60),'OFFLINE GALLERY TEST - NOT A CAMERA FRAME',fill='white',font_size=35)
        image.save(p);lib.commit(ref,'.jpg',dict(kind='photo',width=1280,height=720,camera='OFFLINE-FIXTURE',album='Test album'));references.append(ref)
    ref,p=lib.allocate('.mp4')
    subprocess.run(['ffmpeg','-v','error','-f','lavfi','-i','testsrc2=size=320x240:rate=15','-f','lavfi','-i','sine=frequency=440:sample_rate=16000','-t','2','-c:v','libx264','-preset','ultrafast','-pix_fmt','yuv420p','-c:a','aac','-y',str(p)],check=True)
    lib.commit(ref,'.mp4',dict(kind='video',width=320,height=240,camera='OFFLINE-AV-FIXTURE'));references.append(ref)
    bus=dbus.SessionBus();os.environ['DBUS_SYSTEM_BUS_ADDRESS']=os.environ['DBUS_SESSION_BUS_ADDRESS']
    children=[];out=Path(args.output);results={}
    with (out/'backend.log').open('w') as log:
        try:
            children.append(subprocess.Popen([sys.executable,'-c',LOCKER],stdout=log,stderr=log))
            for _ in range(50):
                if bus.name_has_owner('com.etherneco.EtherLock1'):break
                time.sleep(.1)
            else:raise RuntimeError('Private locker unavailable')
            children.append(subprocess.Popen([sys.executable,str(source/'service.py')],stdout=log,stderr=log))
            for _ in range(50):
                if bus.name_has_owner('com.etherneco.EtherCamera1'):break
                if children[-1].poll() is not None:raise RuntimeError('Private backend exited')
                time.sleep(.1)
            else:raise RuntimeError('Private backend unavailable')
            api=dbus.Interface(bus.get_object('com.etherneco.EtherCamera1','/com/etherneco/EtherCamera1'),'com.etherneco.EtherCamera1')
            lock=dbus.Interface(bus.get_object('com.etherneco.EtherLock1','/com/etherneco/EtherLock1'),'com.etherneco.EtherLock1')
            page=json.loads(str(api.ListMediaPage('{}',dbus.UInt32(0))));assert len(page['items'])==4
            thumb=api.GetThumbnail(references[0]).take()
            try:assert os.read(thumb,2)==b'\xff\xd8'
            finally:os.close(thumb)
            api.SetAlbum(references[0],'Repair item 123')
            assert len(json.loads(str(api.ListMediaPage('{"album":"Repair item 123"}',dbus.UInt32(0))))['items'])==1
            exported=str(api.ExportMedia(references[0]));assert Path(exported).is_file()
            api.Configure('{"format":"PNG","cameraPolicy":"deny"}')
            assert json.loads(str(api.GetState()))['config']['cameraPolicy']=='deny'
            children[-1].terminate();children[-1].wait(timeout=5)
            children.append(subprocess.Popen([sys.executable,str(source/'service.py')],stdout=log,stderr=log))
            for _ in range(50):
                if bus.name_has_owner('com.etherneco.EtherCamera1'):break
                time.sleep(.1)
            api=dbus.Interface(bus.get_object('com.etherneco.EtherCamera1','/com/etherneco/EtherCamera1'),'com.etherneco.EtherCamera1')
            restarted=json.loads(str(api.GetState()))
            assert restarted['config']['cameraPolicy']=='deny' and restarted['config']['format']=='PNG'
            assert restarted['history'];results['restartPersistence']=True
            api.Configure('{"cameraPolicy":"ask-each-time"}');results['apiMedia']=True
            manual=json.loads(str(api.ManualCode('EAN-13','5901234123457')))
            assert manual['manual'] and not manual['verifiedBySensor']
            try:api.StartRecordingWithAudio('invalid',False);raise AssertionError('Microphone consent bypass')
            except dbus.DBusException:pass
            results['manualAndMicrophoneConsent']=True
            for view,size in [('library','360x900'),('wide','1000x600'),('photo','480x900'),('video','480x900'),('revoked','480x900')]:
                lock.FixtureLock(False);folder=out/view;folder.mkdir(exist_ok=True)
                env=dict(os.environ,ETHERCAMERA_MEDIA_QA_OUTPUT=str(folder),ETHERCAMERA_MEDIA_QA_SIZE=size,ETHERCAMERA_MEDIA_QA_VIEW=view,QT_MEDIA_BACKEND='ffmpeg',QT_LOGGING_RULES='qt.multimedia.ffmpeg.*=false')
                with (folder/'ui.log').open('w') as ui_log:
                    app=subprocess.Popen([args.binary],env=env,stdout=ui_log,stderr=ui_log)
                    if view=='revoked':time.sleep(1);lock.FixtureLock(True)
                    code=app.wait(timeout=20)
                assert code==0,(view,(folder/'ui.log').read_text())
                result=json.loads((folder/'result.json').read_text());assert result['rendered']
                if view=='revoked':assert result['private'] and result['items']==0 and not result['imageLoaded']
                else:assert not result['private'] and result['items']==4,result
                if view=='photo':assert result['imageLoaded'],result
                if view=='video':
                    assert result['videoPosition']>100 and result['videoFrames']>2,result
                    shot=Image.open(folder/'library.png').convert('RGB')
                    crop=shot.crop((50,200,shot.width-50,500))
                    assert sum(max(rgb)-min(rgb)>100 for rgb in crop.getdata())>1000,'Video test pattern is not visible'
                logs=(folder/'ui.log').read_text()
                assert not any(s in logs for s in ['qrc:/MediaLibrary.qml:', 'ReferenceError','TypeError','Media playback:']),logs
                results[view]=result
            lock.FixtureLock(True)
            for call in [lambda:api.ListMedia(''),lambda:api.MediaInfo(references[0]),lambda:api.GetThumbnail(references[0])]:
                try:call();raise AssertionError('Locked media allowed')
                except dbus.DBusException:pass
            results['lockDenial']=True;(out/'acceptance.json').write_text(json.dumps(results,indent=2)+'\n')
        finally:
            for child in reversed(children):
                child.terminate()
                try:child.wait(timeout=5)
                except subprocess.TimeoutExpired:child.kill();child.wait()
    print(json.dumps(results,indent=2))

def main():
    parser=argparse.ArgumentParser();parser.add_argument('--binary',required=True);parser.add_argument('--source',required=True);parser.add_argument('--output',required=True);parser.add_argument('--worker',action='store_true');args=parser.parse_args()
    if os.geteuid()==0:raise SystemExit('Run as an unprivileged test user')
    if args.worker:worker(args);return
    out=Path(args.output).absolute();out.mkdir(parents=True,exist_ok=True);args.output=str(out)
    if Path('/tmp/.X11-unix/X94').exists():raise RuntimeError('Private display :94 occupied')
    with tempfile.TemporaryDirectory(prefix='ethercamera-gallery-test-') as tmp:
        root=Path(tmp);auth=root/'Xauthority';auth.touch(mode=0o600)
        subprocess.run(['xauth','-f',str(auth),'add',':94','MIT-MAGIC-COOKIE-1',secrets.token_hex(16)],check=True)
        runtime=root/'runtime';runtime.mkdir(mode=0o700)
        env=dict(os.environ,HOME=str(root),XDG_RUNTIME_DIR=str(runtime),DISPLAY=':94',XAUTHORITY=str(auth),QT_QUICK_BACKEND='software',QT_QPA_PLATFORM='xcb',QT_ENABLE_HIGHDPI_SCALING='0',GIO_USE_VFS='local',GVFS_DISABLE_FUSE='1',LANG='C.UTF-8')
        env.pop('DBUS_SESSION_BUS_ADDRESS',None);env.pop('SESSION_MANAGER',None)
        with (out/'xserver.log').open('w') as log:
            server=subprocess.Popen(['Xvfb',':94','-screen','0','1280x1000x24','-dpi','264','-nolisten','tcp','-auth',str(auth)],env=env,stdout=log,stderr=log)
            try:
                for _ in range(50):
                    if Path('/tmp/.X11-unix/X94').exists():break
                    time.sleep(.1)
                subprocess.run(['dbus-run-session','--',sys.executable,str(Path(__file__).resolve()),'--binary',args.binary,'--source',args.source,'--output',args.output,'--worker'],env=env,check=True,timeout=120)
            finally:
                server.terminate()
                try:server.wait(timeout=3)
                except subprocess.TimeoutExpired:server.kill();server.wait()

if __name__=='__main__':main()
