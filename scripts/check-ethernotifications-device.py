"""Isolated ARM64 acceptance: private bus/store, fake audio, offscreen QML."""
from pathlib import Path
import io
import json
import runpy
import tarfile
ROOT=Path(__file__).resolve().parent.parent
remote=runpy.run_path(str(ROOT/'scripts/check-etherphone-device.py'))['remote']

if __name__=='__main__':
    payload=io.BytesIO()
    with tarfile.open(fileobj=payload,mode='w:gz') as tar:
        for p in (ROOT/'ethernotifications').rglob('*'):
            if p.is_file() and '__pycache__' not in p.parts:
                tar.add(p,arcname='ethernotifications/'+p.relative_to(ROOT/'ethernotifications').as_posix())
        tar.add(ROOT/'build/ethernotifications-ui-test',arcname='ethernotifications-ui-test')
        tar.add(ROOT/'build/ethernotifications-client-test',arcname='ethernotifications-client-test')
    source=r'''
import hashlib,io,json,os,pathlib,subprocess,sys,tarfile,tempfile
assert pathlib.Path('/etc/etherpocket/disk-identity').read_text().strip()=='GM1920-548cb338-mobian-sda21'
folder=pathlib.Path(tempfile.mkdtemp(prefix='ethernotifications-qa-',dir='/var/tmp'))
with tarfile.open(fileobj=io.BytesIO(sys.stdin.buffer.read()),mode='r:gz') as tar:tar.extractall(folder,filter='data')
(folder/'ethernotifications-ui-test').chmod(0o755)
(folder/'ethernotifications-client-test').chmod(0o755)
runtime=folder/'runtime';runtime.mkdir(mode=0o700)
for p in [folder]+list(folder.rglob('*')):os.chown(p,1000,1000)
user=['runuser','-u','mobian','--','env','XDG_RUNTIME_DIR='+str(runtime),'QT_QPA_PLATFORM=offscreen','DBUS_SYSTEM_BUS_ADDRESS=unix:path=/nonexistent/notification-qa']
results={}
for name,args in [('core',['python3','-m','unittest','discover','-s',str(folder/'ethernotifications/tests'),'-p','test_*.py','-v']),('protocol',['dbus-run-session','--','python3',str(folder/'ethernotifications/tests/service_fixture.py')]),('qt-client',['dbus-run-session','--','python3',str(folder/'ethernotifications/tests/service_fixture.py'),'--qt-client',str(folder),str(folder/'ethernotifications-client-test')])]:
 p=subprocess.run(user+args,capture_output=True,text=True,timeout=60);results[name]={'exit':p.returncode,'out':p.stdout,'error':p.stderr}
for view,w,h,scale,dpi in [('narrow',360,900,1,96),('landscape',1000,600,1,96),('external',1920,1080,1,96),('native',1440,3120,3.13,320)]:
 for mode in ['center','settings','banner']:
  name=view+'-'+mode;target=folder/(name+'.png')
  p=subprocess.run(user+['QT_FONT_DPI='+str(dpi),'dbus-run-session','--',str(folder/'ethernotifications-ui-test'),str(w),str(h),str(target),mode,str(scale)],capture_output=True,text=True,timeout=15)
  results[name]={'exit':p.returncode,'out':p.stdout,'error':p.stderr}
(folder/'acceptance.json').write_text(json.dumps({'stage':str(folder),'sourceHashes':{n:hashlib.sha256((folder/'ethernotifications'/n).read_bytes()).hexdigest() for n in ['core.py','service.py','notificationclient.cpp','notificationclient.h','NotificationCenter.qml','NotificationSettings.qml','NotificationBanner.qml']},'tests':results},indent=2))
with tarfile.open(fileobj=sys.stdout.buffer,mode='w|gz') as tar:
 for p in folder.iterdir():
  if p.name=='acceptance.json' or p.suffix in ('.png','.json'):tar.add(p,arcname=p.name)
'''
    archive=remote(source,payload.getvalue(),timeout=160)
    out=ROOT/'evidence/ethernotifications-device';out.mkdir(exist_ok=True)
    with tarfile.open(fileobj=io.BytesIO(archive),mode='r:gz') as tar:tar.extractall(out,filter='data')
    result=json.loads((out/'acceptance.json').read_text(encoding='utf-8'))
    print(json.dumps(result,indent=2));assert all(t['exit']==0 for t in result['tests'].values())
