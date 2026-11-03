"""Refresh the existing shell application catalog by restarting only its UI,
then show the installed app. Keep Xorg, XFWM, applications and device owners.
"""
from pathlib import Path
import json,runpy,shlex,subprocess
ROOT=Path(__file__).resolve().parent.parent
SSH=runpy.run_path(str(ROOT/'scripts/deploy-ethermobile.py'))['SSH']
SOURCE=r'''
import json,os,pathlib,subprocess,time,socket
user=['runuser','-u','mobian','--','env','XDG_RUNTIME_DIR=/run/user/1000','DBUS_SESSION_BUS_ADDRESS=unix:path=/run/user/1000/bus']
assert pathlib.Path('/usr/share/applications/ethercamera-app.desktop').is_file()
pids=subprocess.check_output(['pgrep','-u','1000','-x','ethershell'],text=True).split();assert len(pids)==1
process=pathlib.Path('/proc')/pids[0];binary=str((process/'exe').resolve())
assert binary==EXPECTED+'/usr/bin/ethershell'
env=dict(s.split('=',1) for s in (process/'environ').read_bytes().decode().split('\0') if '=' in s)
owners=['Xorg','xfwm4','pipewire','wireplumber']
def keep():
 return {name:subprocess.run(['pgrep','-x',name],capture_output=True,text=True).stdout.strip() for name in owners}
before=keep()
launcher='/home/mobian/.local/bin/ethershell2-start'
subprocess.run(['/usr/sbin/runuser','-u','mobian','--',launcher,'stop'],env=env,check=True,capture_output=True,timeout=20)
with open('/var/tmp/ethercamera-shell-catalog-refresh.log','ab') as log:
 subprocess.Popen(['/usr/sbin/runuser','-u','mobian','--',launcher,'start'],env=env,stdin=subprocess.DEVNULL,stdout=log,stderr=log,start_new_session=True)
for _ in range(60):
 found=subprocess.run(['pgrep','-u','1000','-x','ethershell'],capture_output=True,text=True).stdout.split()
 if len(found)==1 and found!=pids:break
 time.sleep(.1)
else:raise RuntimeError('Shell UI did not restart')
time.sleep(2)
assert keep()==before
assert str((pathlib.Path('/proc')/found[0]/'exe').resolve())==binary
out=pathlib.Path('/var/tmp/ethercamera-app-live');out.mkdir(exist_ok=True);os.chown(out,1000,1000)
cmd=user+['env','DISPLAY='+env['DISPLAY'],'XAUTHORITY='+env.get('XAUTHORITY','/home/mobian/.Xauthority'),'QT_ENABLE_HIGHDPI_SCALING=0','/usr/bin/ethercamera-app','--screenshot',str(out/'app.png')]
shot=subprocess.run(cmd,capture_output=True,text=True,timeout=20);assert shot.returncode==0,shot.stderr
(out/'app.log').write_text(shot.stdout+shot.stderr)
result=json.loads((out/'app.png.json').read_text());assert result['rendered'] and not result['active'] and not result['hasFrame'] and not result['private'] and result['devices']==0
launch=user+['systemd-run','--user','--collect','--unit=ethercamera-ui','/usr/bin/env','DISPLAY='+env['DISPLAY'],'XAUTHORITY='+env.get('XAUTHORITY','/home/mobian/.Xauthority'),'QT_ENABLE_HIGHDPI_SCALING=0','XDG_RUNTIME_DIR=/run/user/1000','DBUS_SESSION_BUS_ADDRESS=unix:path=/run/user/1000/bus','/usr/bin/ethercamera-app']
active=subprocess.run(user+['systemctl','--user','is-active','ethercamera-ui'],capture_output=True,text=True).stdout.strip()
if active!='active':subprocess.run(launch,check=True,capture_output=True)
time.sleep(1)
status=subprocess.check_output(user+['systemctl','--user','is-active','ethercamera-ui'],text=True).strip();assert status=='active'
print(json.dumps(dict(catalogRefreshed=True,previousShellPid=pids[0],shellPid=found[0],shellExecutable=binary,preservedOwners=before,application=status,screenshot=result)))
'''
if __name__=='__main__':
 stage=json.loads((ROOT/'evidence/ethercamera-shell-stage.json').read_text())['stage']
 p=subprocess.run(SSH+['python3 -c '+shlex.quote(SOURCE.replace('EXPECTED',repr(stage)))],capture_output=True,text=True,timeout=70)
 if p.returncode:raise RuntimeError(p.stderr)
 result=json.loads(p.stdout)
 (ROOT/'evidence/ethercamera-app-deployment.json').write_text(json.dumps(result,indent=2)+'\n',encoding='utf-8')
 for source,target in [('app.png','ethercamera-app-live.png'),('app.png.json','ethercamera-app-live.png.json'),('app.log','ethercamera-app-live.log')]:
  data=subprocess.check_output(SSH+['cat /var/tmp/ethercamera-app-live/'+source]);(ROOT/'evidence'/target).write_bytes(data)
 print(json.dumps(result,indent=2))
