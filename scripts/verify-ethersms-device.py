"""Capture real application state and record non-content deployment checks."""
from pathlib import Path
import hashlib,json,runpy,shlex,subprocess
ROOT=Path(__file__).resolve().parent.parent
SSH=runpy.run_path(str(ROOT/'scripts/deploy-ethermobile.py'))['SSH']
source=r'''
import os,pathlib,subprocess,json,sqlite3,stat,time
pids=subprocess.check_output(['pgrep','-u','1000','-x','ethershell'],text=True).split();assert len(pids)==1
proc=pathlib.Path('/proc')/pids[0]
env=dict(x.split('=',1) for x in (proc/'environ').read_bytes().decode().split('\0') if '=' in x)
env.update(HOME='/home/mobian',XDG_RUNTIME_DIR='/run/user/1000',DBUS_SESSION_BUS_ADDRESS='unix:path=/run/user/1000/bus',LANG='C.UTF-8')
folder=pathlib.Path('/home/mobian/ethersms-validation');folder.mkdir(exist_ok=True);folder.chmod(0o700);os.chown(folder,1000,1000)
def user(args,timeout=30):return subprocess.run(['/usr/sbin/runuser','-u','mobian','--']+args,env=env,capture_output=True,text=True,timeout=timeout)
out={}
for label,args in [('pocket',[]),('desktop',['--desktop'])]:
 capture_env=dict(env)
 if label=='desktop':env.update(QT_QPA_PLATFORM='offscreen',QT_SCALE_FACTOR='1',QT_FONT_DPI='96',QT_QUICK_BACKEND='software')
 r=user(['/usr/bin/ethersms','--capture',str(folder/(label+'.png'))]+args);env.clear();env.update(capture_env);out[label]={'exit':r.returncode,'diagnostics':r.stderr};assert r.returncode==0 and not r.stderr
if subprocess.run(['pgrep','-u','1000','-x','ethersms'],capture_output=True).returncode!=0:
 log=os.open(str(folder/'application.log'),os.O_CREAT|os.O_WRONLY|os.O_APPEND,0o600);os.chown(folder/'application.log',1000,1000)
 subprocess.Popen(['/usr/sbin/runuser','-u','mobian','--','/usr/bin/ethersms'],env=env,stdin=subprocess.DEVNULL,stdout=log,stderr=log,start_new_session=True);os.close(log)
 time.sleep(2)
r=user(['busctl','--user','call','org.etherneco.EtherSMS','/org/etherneco/EtherSMS','org.etherneco.EtherSMS','GetUnread']);out['unread_service']={'exit':r.returncode,'result':r.stdout.strip()};assert r.returncode==0
r=user(['busctl','--user','call','org.freedesktop.Notifications','/org/freedesktop/Notifications','org.freedesktop.Notifications','GetCapabilities']);out['notifications']={'exit':r.returncode,'capabilities':r.stdout.strip()}
r=user(['ping','-c','2','1.1.1.1']);out['cellular_ping']={'exit':r.returncode,'output':r.stdout,'errors':r.stderr}
out['services']=subprocess.run(['systemctl','is-active','NetworkManager','ssh','bluetooth','etherpocket-modem','ModemManager','ethermobile-data'],capture_output=True,text=True).stdout.splitlines()
out['radios']=subprocess.run(['nmcli','radio'],capture_output=True,text=True).stdout
path=pathlib.Path('/home/mobian/.local/share/Etherneco/EtherSMS/messages.sqlite');st=path.stat()
with sqlite3.connect('file:'+str(path)+'?mode=ro',uri=True) as db:
 out['database']={'mode':oct(stat.S_IMODE(st.st_mode)),'owner':st.st_uid,'schema':db.execute('PRAGMA user_version').fetchone()[0],'integrity':db.execute('PRAGMA integrity_check').fetchone()[0],'message_count':db.execute('SELECT COUNT(*) FROM messages').fetchone()[0]}
out['package_versions']=subprocess.run(['dpkg-query','-W','ethersms','ethersms-speech-engine','espeak-ng','libqt6sql6-sqlite'],capture_output=True,text=True).stdout
print(json.dumps(out,indent=2))
'''
if __name__=='__main__':
 r=subprocess.run(SSH+['python3 -c '+shlex.quote(source)],capture_output=True,timeout=100,check=True);data=json.loads(r.stdout)
 data['package_sha256']={name:hashlib.sha256((ROOT/'build'/name).read_bytes()).hexdigest() for name in ['ethersms_0.1.0_arm64.deb','ethershell-sms_2.1.0_arm64.deb','ethersms-speech-engine_1.9.5~dev-1_arm64.deb']}
 (ROOT/'evidence/ethersms-device-final.json').write_text(json.dumps(data,indent=2)+'\n');print(json.dumps(data,indent=2))
 for source,name in [('/home/mobian/ethersms-validation/pocket.png','ethersms-device-pocket.png'),('/home/mobian/ethersms-validation/desktop.png','ethersms-device-desktop.png'),('/home/mobian/.config/ethershell/validation/settings2-screen.png','ethersms-device-settings.png')]:
  command=['scp',*SSH[1:-1],SSH[-1]+':'+source,str(ROOT/'evidence'/name)]
  subprocess.run(command,check=True,capture_output=True,timeout=30)
