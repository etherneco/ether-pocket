"""Real API denial/idle checks and software-rendered offline map acceptance."""
from pathlib import Path
import io,json,runpy,subprocess,tarfile
ROOT=Path(__file__).resolve().parent.parent
SSH=runpy.run_path(str(ROOT/'scripts/deploy-ethermobile.py'))['SSH']
SOURCE=r'''
import json,pathlib,subprocess,os,time,tarfile,sys
user=['runuser','-u','mobian','--','env','LANG=C.UTF-8','XDG_RUNTIME_DIR=/run/user/1000','DBUS_SESSION_BUS_ADDRESS=unix:path=/run/user/1000/bus']
folder=pathlib.Path('/var/tmp/etherlocation-device-acceptance');folder.mkdir(exist_ok=True);os.chown(folder,1000,1000)
code=r"""
import dbus,json,pathlib
b=dbus.SessionBus();api=dbus.Interface(b.get_object('com.etherneco.EtherLocation1','/com/etherneco/EtherLocation1'),'com.etherneco.EtherLocation1')
state=json.loads(str(api.GetState()));assert state['ready'] and not state['active'] and not state['config']['history']
results={'state':state,'negativeTests':{}}
for method,args in [('GetLocation',['{"precision":"precise"}']),('GetLastKnownLocation',['{}']),('StartUpdates',['{}']),('Configure',['{"enabled":true}']),('ResolvePermission',['unknown','allow-while-using','precise',True]),('GetManagement',[])]:
 try:getattr(api,method)(*args);raise AssertionError('Untrusted caller was allowed: '+method)
 except dbus.DBusException as e:assert e.get_dbus_name()=='com.etherneco.EtherLocation1.Rejected';results['negativeTests'][method]=True
assert not pathlib.Path.home().joinpath('.local/share/etherlocation/history.sqlite').exists()
results['historyNeverCreated']=True
print(json.dumps(results))
"""
p=subprocess.run(user+['python3','-c',code],capture_output=True,text=True,timeout=20);assert p.returncode==0,p.stderr
results=json.loads(p.stdout)
assert not pathlib.Path('/tmp/.X11-unix/X94').exists()
server=subprocess.Popen(['Xvfb',':94','-screen','0','420x780x24','-nolisten','tcp'],stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
try:
 time.sleep(.5)
 p=subprocess.run(user+['env','DISPLAY=:94','QT_QUICK_BACKEND=software','etherlocation-map','--smoke-test','--screenshot',str(folder/'offline-map.png')],capture_output=True,text=True,timeout=15)
 results['map']=dict(exit=p.returncode,stdout=p.stdout,stderr=p.stderr,screenshot=(folder/'offline-map.png').exists(),backend='software',networkTiles=False)
 assert p.returncode==0 and not p.stderr and results['map']['screenshot'],results['map']
finally:server.terminate();server.wait(timeout=5)
results['helperProcesses']=subprocess.run(['pgrep','-af','^/usr/libexec/etherlocation-qmi'],capture_output=True,text=True).stdout
assert not results['helperProcesses']
results['services']=subprocess.run(['systemctl','is-active','ssh','NetworkManager','etherpower','etherhardware','ModemManager'],capture_output=True,text=True).stdout.splitlines()
assert all(s=='active' for s in results['services'])
(folder/'result.json').write_text(json.dumps(results,indent=2))
with tarfile.open(fileobj=sys.stdout.buffer,mode='w|gz') as archive:
 for p in folder.iterdir():archive.add(p,arcname=p.name)
'''
if __name__=='__main__':
    p=subprocess.run(SSH+['python3 -'],input=SOURCE.encode(),capture_output=True,timeout=50)
    if p.returncode:raise RuntimeError(p.stderr.decode(errors='replace'))
    target=ROOT/'evidence/etherlocation-device';target.mkdir(exist_ok=True)
    with tarfile.open(fileobj=io.BytesIO(p.stdout),mode='r:gz') as archive:archive.extractall(target,filter='data')
    print((target/'result.json').read_text())
