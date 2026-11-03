"""Run only write-disabled UI and isolated SMS tests on the ARM64 phone."""
from pathlib import Path
import io,json,runpy,tarfile
ROOT=Path(__file__).resolve().parent.parent
remote=runpy.run_path(str(ROOT/'scripts/check-etherphone-device.py'))['remote']
if __name__=='__main__':
    payload=io.BytesIO()
    with tarfile.open(fileobj=payload,mode='w:gz') as tar:
        for name in ['etherphone-ui-test-arm64','ethersms-phone-test-arm64']:
            tar.add(ROOT/'build'/name,arcname=name)
    source=r'''
import dbus,io,json,os,pathlib,subprocess,sys,tarfile,tempfile
folder=pathlib.Path(tempfile.mkdtemp(prefix='etherphone-ui-',dir='/var/tmp'))
with tarfile.open(fileobj=io.BytesIO(sys.stdin.buffer.read()),mode='r:gz') as tar:tar.extractall(folder,filter='data')
for p in [folder]+list(folder.rglob('*')):os.chown(p,1000,1000);p.chmod(0o700)
objects=dbus.Interface(dbus.SystemBus().get_object('org.freedesktop.ModemManager1','/org/freedesktop/ModemManager1'),'org.freedesktop.DBus.ObjectManager').GetManagedObjects(timeout=5)
status={'modem':bool(objects),'voice':any('org.freedesktop.ModemManager1.Modem.Voice' in i for i in objects.values())}
snapshot=folder/'snapshot.json';snapshot.write_text(json.dumps({'ready':True,'status':status,'contacts':[],'history':[],'calls':[],'config':{'hideCallerOnLock':True,'missedNotifications':True,'retentionDays':90},'ims':'Unavailable / unverified','volte':'Blocked','audio':{'operational':False,'error':'Qualcomm modem voice path unvalidated'},'emergencyWarning':'Emergency calling is unverified. Do not rely on EtherPocket as your sole emergency telephone. Keep a known-working phone available.'}));os.chown(snapshot,1000,1000)
user=['runuser','-u','mobian','--','env','QT_QPA_PLATFORM=offscreen','QT_QUICK_BACKEND=software','XDG_RUNTIME_DIR=/run/user/1000','LANG=C.UTF-8']
results={}
for name,size,desktop in [('narrow','360x900',False),('portrait','1080x2340',False),('landscape','1000x600',True),('external','1920x1080',True),('native-dpi','1080x2340',False)]:
 out=folder/name
 p=subprocess.run(user+(['QT_FONT_DPI=320'] if name=='native-dpi' else [])+[str(folder/'etherphone-ui-test-arm64'),'--output',str(out),'--size',size,'--snapshot',str(snapshot)]+(['--desktop'] if desktop else []),capture_output=True,text=True,timeout=20)
 results[name]={'exit':p.returncode,'out':p.stdout,'error':p.stderr}
p=subprocess.run(user+[str(folder/'ethersms-phone-test-arm64')],capture_output=True,text=True,timeout=60)
results['smsRegression']={'exit':p.returncode,'out':p.stdout,'error':p.stderr}
(folder/'results.json').write_text(json.dumps(results,indent=2))
with tarfile.open(fileobj=sys.stdout.buffer,mode='w|gz') as tar:
 for p in folder.iterdir():
  if p.is_dir() or p.suffix=='.json':tar.add(p,arcname=p.name)
'''
    data=remote(source,payload.getvalue(),timeout=100)
    out=ROOT/'evidence/etherphone-ui';out.mkdir(exist_ok=True)
    with tarfile.open(fileobj=io.BytesIO(data),mode='r:gz') as tar:tar.extractall(out,filter='data')
    results=json.loads((out/'results.json').read_text(encoding='utf-8'))
    print(json.dumps(results,indent=2));assert all(r['exit']==0 for r in results.values())
