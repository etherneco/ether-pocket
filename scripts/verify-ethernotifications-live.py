"""Live delivery/restart regression; no suspend, reboot, calls, SMS or radio writes."""
from pathlib import Path
import json,runpy
ROOT=Path(__file__).resolve().parent.parent
remote=runpy.run_path(str(ROOT/'scripts/check-etherphone-device.py'))['remote']
if __name__=='__main__':
    source=r'''
import hashlib,json,os,pathlib,socket,sqlite3,subprocess,time
user=['/usr/sbin/runuser','-u','mobian','--','env','XDG_RUNTIME_DIR=/run/user/1000','DBUS_SESSION_BUS_ADDRESS=unix:path=/run/user/1000/bus']
def run(args):return subprocess.check_output(args,text=True,timeout=20).strip()
pid=run(['pgrep','-u','1000','-x','ethershell']);proc=pathlib.Path('/proc')/pid
env=dict(x.split('=',1) for x in (proc/'environ').read_bytes().decode().split('\0') if '=' in x)
stage=(proc/'exe').resolve().parent.parent.parent
endpoint='/run/user/1000/ethershell-control-experience-'+env['DISPLAY'].replace(':','').replace('.','-')
def request(data):
 with socket.socket(socket.AF_UNIX,socket.SOCK_STREAM) as c:
  c.settimeout(6);c.connect(endpoint);c.sendall(json.dumps(data).encode()+b'\n');return c.recv(8192).decode().strip()
def state():return json.loads(request({'command':'notification-state'}))
def ready():
 for _ in range(100):
  try:
   s=state()
   if s.get('ready') and not s.get('locked'):return s
  except (OSError,ValueError):pass
  time.sleep(.1)
 raise RuntimeError('Notification UI did not reconnect/unlock under current session policy')
def daemon_pid():return int(run(user+['systemctl','--user','show','ethernotifications','-p','MainPID','--value']))
def shell(action):
 cmd=['/usr/sbin/runuser','-u','mobian','--','/usr/bin/python3',str(stage/'usr/share/ethershell/current_session.py'),action]
 if action=='stop':subprocess.run(cmd,env=env,check=True,capture_output=True,timeout=20)
 else:
  with open('/var/tmp/ethernotifications-live-restart.log','ab') as log:subprocess.Popen(cmd,env=env,stdin=subprocess.DEVNULL,stdout=log,stderr=log,start_new_session=True)
before=ready();first=daemon_pid()
code="import dbus; b=dbus.SessionBus(); a=dbus.Interface(b.get_object('org.freedesktop.Notifications','/org/freedesktop/Notifications'),'org.freedesktop.Notifications');print(int(a.Notify('Acceptance test',dbus.UInt32(0),'dialog-information','EtherNotifications acceptance','Local delivery and persistence check',dbus.Array([],signature='s'),dbus.Dictionary({'x-ether-privacy':'public'},signature='sv'),dbus.Int32(60000))))"
ident=int(run(user+['python3','-c',code]));time.sleep(.8)
delivered=state();assert delivered['cards']>before['cards'] and delivered['bannerId']==ident,delivered
path=pathlib.Path('/home/mobian/.local/state/ethernotifications/history.sqlite')
def persisted():
 with sqlite3.connect('file:'+str(path)+'?mode=ro',uri=True) as db:
  row=db.execute('SELECT document FROM records WHERE id=?',(ident,)).fetchone()
  return bool(row and json.loads(row[0])['title']=='EtherNotifications acceptance')
assert persisted()
shell('stop');assert daemon_pid()==first
shell('start');after_shell=ready();assert daemon_pid()==first and persisted()
subprocess.run(user+['systemctl','--user','restart','ethernotifications'],check=True)
after_service=ready();second=daemon_pid();assert second!=first and persisted()
assert not after_service.get('bannerId'),'Do not replay banners after service restart'
denied=subprocess.run(user+['gdbus','call','--session','--dest','com.etherneco.EtherNotifications1','--object-path','/com/etherneco/EtherNotifications1','--method','com.etherneco.EtherNotifications1.GetState'],capture_output=True,text=True)
assert denied.returncode!=0
request({'command':'power-display','action':'off'});time.sleep(.5)
assert persisted()
request({'command':'power-display','action':'on'});ready()
request({'page':'notices'})
services={n:run(['systemctl','is-active',n]) for n in ['ssh','NetworkManager','ModemManager','etherpocket-modem','bluetooth','etherhardware','etherpower','ethershare']}
audio={n:run(user+['systemctl','--user','show',n,'-p','MainPID','--value']) for n in ['pipewire','pipewire-pulse','wireplumber']}
wifi=run(['curl','--interface','wlan0','--max-time','15','-sS','-o','/dev/null','-w','%{http_code}','https://deb.debian.org']);assert wifi=='200'
stat=(pathlib.Path('/proc')/str(second)/'stat').read_text()
report={'notificationId':ident,'before':before,'delivered':delivered,'afterShellRestart':after_shell,'afterServiceRestart':after_service,'persistentAcrossShellRestart':True,'persistentAcrossDaemonRestart':True,'noBannerReplay':True,'ordinaryClientContentDenied':True,'screenOffRecovery':True,'realSuspendResume':'not tested','reboot':'not tested','haptics':'not verified','physicalAudibility':'not verified','services':services,'audioServers':audio,'wifiHTTPS':wifi,'boot':pathlib.Path('/proc/sys/kernel/random/boot_id').read_text().strip(),'statePermissions':oct(path.stat().st_mode&0o777),'sourceHashes':{n:hashlib.sha256(pathlib.Path('/usr/share/ethernotifications',n).read_bytes()).hexdigest() for n in ['core.py','service.py']},'baseline':{'pid':second,'timestamp':time.time(),'stat':stat}}
print(json.dumps(report,indent=2))
'''
    result=json.loads(remote(source,timeout=90))
    installed=json.loads((ROOT/'evidence/ethernotifications-install.json').read_text(encoding='utf-8'))
    assert result['services']==installed['before']['services']
    assert result['audioServers']==installed['before']['audioServers']
    assert result['boot']==installed['before']['boot']
    (ROOT/'evidence/ethernotifications-live-verification.json').write_text(json.dumps(result,indent=2),encoding='utf-8')
    print(json.dumps({k:v for k,v in result.items() if k!='baseline'},indent=2))
