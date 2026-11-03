"""Exercise installed ARM64 maps and private API denials without activating GNSS."""
from pathlib import Path
import io,json,runpy,subprocess,tarfile
ROOT=Path(__file__).resolve().parents[1]
SSH=runpy.run_path(str(ROOT/'scripts/deploy-ethermobile.py'))['SSH']
SOURCE=r'''
import json,os,pathlib,subprocess,sys,tarfile
assert pathlib.Path('/etc/etherpocket/disk-identity').read_text().strip()=='GM1920-548cb338-mobian-sda21'
user=['runuser','-u','mobian','--','env','LANG=C.UTF-8','XDG_RUNTIME_DIR=/run/user/1000','DBUS_SESSION_BUS_ADDRESS=unix:path=/run/user/1000/bus']
folder=pathlib.Path('/var/tmp/ethermap-device-acceptance');folder.mkdir(exist_ok=True);os.chown(folder,1000,1000)
code=r"""
import dbus,json,pathlib
b=dbus.SessionBus();api=dbus.Interface(b.get_object('com.etherneco.EtherLocation1','/com/etherneco/EtherLocation1'),'com.etherneco.EtherLocation1')
before=json.loads(str(api.GetState()));assert before['ready'] and not before['active']
denied={}
for name,args in [('GetLocation',['{"precision":"precise"}']),('GetLastKnownLocation',['{}']),('StartUpdates',['{}']),('Configure',['{"enabled":true}']),('ResolvePermission',['invalid','allow-while-using','precise',True]),('GetIpLocation',['{"endpoint":"https://example.invalid/ip","consent":false}']),('GetIpLocation',['{"endpoint":"https://example.invalid/ip","consent":true}'])]:
 try:getattr(api,name)(*args,timeout=5);raise AssertionError('Untrusted access: '+name)
 except dbus.DBusException as e:
  assert e.get_dbus_name()=='com.etherneco.EtherLocation1.Rejected'
  denied[name+':'+str(args[-1])]=True
print(json.dumps(dict(state=before,negativeTests=denied,historyFileExists=(pathlib.Path.home()/'.local/share/etherlocation/history.sqlite').exists())))
"""
p=subprocess.run(user+['python3','-c',code],capture_output=True,text=True,timeout=25);assert p.returncode==0,p.stderr
result=json.loads(p.stdout);result['views']={}
for name,size,extra in [('narrow','360x780',[]),('portrait','420x820',[]),('landscape','900x540',[]),('settings','360x780',['--settings'])]:
 out=folder/(name+'.png')
 p=subprocess.run(user+['xvfb-run','-a','-s','-screen 0 '+size+'x24','env','QT_QPA_PLATFORM=xcb','QT_QUICK_BACKEND=software','QT_SCALE_FACTOR=1','ethermap','--size',size,'--smoke-test','--expect-offline','--screenshot',str(out)]+extra,capture_output=True,text=True,timeout=25)
 result['views'][name]=dict(exit=p.returncode,stdout=p.stdout,stderr=p.stderr,screenshot=out.exists())
 assert p.returncode==0 and not p.stderr and out.exists(),result['views'][name]
result['stateAfter']=json.loads(subprocess.check_output(user+['etherlocation','state'],text=True))
assert result['stateAfter']['config']==result['state']['config'] and not result['stateAfter']['active']
result['helperProcesses']=subprocess.run(['pgrep','-af','^/usr/libexec/etherlocation-qmi'],capture_output=True,text=True).stdout
assert not result['helperProcesses']
result['packages']=subprocess.check_output(['dpkg-query','-W','ethermap','etherlocation'],text=True)
result['services']=subprocess.run(['systemctl','is-active','ssh','NetworkManager','etherhardware','etherpower','ModemManager'],capture_output=True,text=True).stdout.splitlines()
assert all(s=='active' for s in result['services'])
(folder/'result.json').write_text(json.dumps(result,indent=2)+'\n')
with tarfile.open(fileobj=sys.stdout.buffer,mode='w|gz') as tar:
 for path in folder.iterdir():tar.add(path,arcname=path.name)
'''
if __name__=='__main__':
 p=subprocess.run(SSH+['python3 -'],input=SOURCE.encode(),capture_output=True,timeout=140)
 if p.returncode:raise RuntimeError(p.stderr.decode(errors='replace')[-5000:])
 target=ROOT/'evidence/ethermap-device';target.mkdir(exist_ok=True)
 with tarfile.open(fileobj=io.BytesIO(p.stdout),mode='r:gz') as tar:tar.extractall(target,filter='data')
 result=json.loads((target/'result.json').read_text())
 print(json.dumps(dict(views={k:v['exit'] for k,v in result['views'].items()},apiDenials=len(result['negativeTests']),packages=result['packages'],services=result['services'],gnssActive=result['stateAfter']['active']),indent=2))
