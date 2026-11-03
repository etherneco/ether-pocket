"""Physical host/service checks without opening a sensor or moving a motor."""
from pathlib import Path
import json,runpy,shlex,subprocess
ROOT=Path(__file__).resolve().parent.parent
SSH=runpy.run_path(str(ROOT/'scripts/deploy-ethermobile.py'))['SSH']
SOURCE=r'''
import hashlib,json,os,pathlib,platform,subprocess,sys,time
import dbus
assert os.getuid()==1000
bus=dbus.SessionBus()
api=dbus.Interface(bus.get_object('com.etherneco.EtherCamera1','/com/etherneco/EtherCamera1'),'com.etherneco.EtherCamera1')
state=json.loads(str(api.GetState()))
assert state['ready'] and not state['active'] and not state['recording']
assert any(d['id']=='spectra:rear-imx586' and d.get('supportedProvider') for d in state['devices'])
denied={}
for name,call in [('vendor-node',lambda:api.RequestSession('/dev/video0','Audit rejection test',True,'{}')),
                  ('codec-node',lambda:api.RequestSession('/dev/video33','Audit rejection test',True,'{}')),
                  ('no-consent',lambda:api.RequestSession('spectra:rear-imx586','Audit rejection test',False,'{}')),
                  ('invalid-token',lambda:api.CapturePhoto('not-a-session')),
                  ('unowned-job',lambda:api.GetJob('not-a-job'))]:
 try:call();raise AssertionError(name+' was not rejected')
 except dbus.DBusException as e:denied[name]=str(e)
report=json.loads(str(api.DiagnosticReport()))
assert not {'jobs','history','purpose','owner','lastError'}.intersection(report)
after=json.loads(str(api.GetState()));assert not after['active'] and after['verified']==state['verified']
introspection=str(dbus.Interface(bus.get_object('com.etherneco.EtherCamera1','/com/etherneco/EtherCamera1'),'org.freedesktop.DBus.Introspectable').Introspect())
assert 'GetFrame' in introspection and 'type="h"' in introspection
pid=int(subprocess.check_output(['systemctl','--user','show','ethercamera','-p','MainPID','--value'],text=True))
proc=pathlib.Path('/proc')/str(pid)
def sample():
 fields=(proc/'stat').read_text().split()
 return dict(ticks=int(fields[13])+int(fields[14]),rss=next(s for s in (proc/'status').read_text().splitlines() if s.startswith('VmRSS:')))
before=sample();time.sleep(10);after=sample()
open_camera_nodes=[str(p.resolve()) for p in (proc/'fd').iterdir() if str(p.resolve()).startswith(('/dev/video','/dev/v4l-subdev','/dev/media'))]
assert not open_camera_nodes
assert after['ticks']-before['ticks']<=5
def run(args):
 p=subprocess.run(args,capture_output=True,text=True,timeout=10)
 return dict(exit=p.returncode,stdout=p.stdout,stderr=p.stderr)
data=dict(state=state,denied=denied,report=report,fdContract=True,idle=dict(durationSeconds=10,before=before,after=after,openCameraNodes=open_camera_nodes),
 architecture=platform.machine(),packageVersion=run(['dpkg-query','-W','-f=${Version}','ethercamera']),
 binarySha256=hashlib.sha256(pathlib.Path('/usr/bin/ethercamera-media').read_bytes()).hexdigest(),
 captureBinarySha256=hashlib.sha256(pathlib.Path('/usr/bin/ethercamera-app').read_bytes()).hexdigest(),
 sourceHashes={f:hashlib.sha256(pathlib.Path('/usr/share/ethercamera',f).read_bytes()).hexdigest() for f in ['core.py','service.py','provider.py','spectra_provider.py','devices.py','audio.py','power_guard.py','documents.py','capture_client.py','cli.py']},
 lockState=json.loads(str(dbus.Interface(bus.get_object('com.etherneco.EtherLock1','/com/etherneco/EtherLock1'),'com.etherneco.EtherLock1').GetState())),
 services=run(['systemctl','is-active','ssh','NetworkManager','bluetooth','etherhardware','etherpower','etherpocket-audio','ethershare','etherpocket-usb-debug','etherpocket-usb-storage']),
 sessionServices=run(['systemctl','--user','is-active','ethercamera','etheraudio','etherlock','ethernotifications','pipewire','pipewire-pulse','wireplumber']),
 network=run(['nmcli','-t','-f','DEVICE,TYPE,STATE','device']),
 processes=run(['pgrep','-a','-u','1000','-x','ethershell']),
 scope='No sensor capture, motor operation, suspend, reboot, browser or microphone activation')
pids=subprocess.check_output(['pgrep','-u','1000','-x','ethershell'],text=True).split()
assert len(pids)==1
data['shellExecutable']=str((pathlib.Path('/proc')/pids[0]/'exe').resolve())
print(json.dumps(data,indent=2))
'''
if __name__=='__main__':
    cmd=['runuser','-u','mobian','--','env','XDG_RUNTIME_DIR=/run/user/1000','DBUS_SESSION_BUS_ADDRESS=unix:path=/run/user/1000/bus','python3','-c',SOURCE]
    p=subprocess.run(SSH+[' '.join(shlex.quote(a) for a in cmd)],capture_output=True,timeout=90)
    if p.returncode:raise RuntimeError(p.stderr.decode(errors='replace'))
    data=json.loads(p.stdout)
    (ROOT/'evidence/ethercamera-device-verification.json').write_text(json.dumps(data,indent=2)+'\n',encoding='utf-8')
    print(json.dumps({k:data[k] for k in ['denied','fdContract','services','sessionServices','network']},indent=2))
