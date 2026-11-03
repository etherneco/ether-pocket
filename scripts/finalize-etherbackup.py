"""Read-only live regression and screenshot capture after checked shell activation."""
from pathlib import Path
import json,runpy,subprocess
ROOT=Path(__file__).resolve().parent.parent
remote=runpy.run_path(str(ROOT/'scripts/verify-etherupdate-device.py'))['remote']
if __name__=='__main__':
 source=r'''
import dbus,json,pathlib,socket,subprocess,time
assert pathlib.Path('/etc/etherpocket/disk-identity').read_text().strip()=='GM1920-548cb338-mobian-sda21'
def run(args):
 p=subprocess.run(args,capture_output=True,text=True,timeout=15)
 return dict(exit=p.returncode,stdout=p.stdout,stderr=p.stderr[:1000])
pid=subprocess.check_output(['pgrep','-u','1000','-x','ethershell'],text=True).strip()
proc=pathlib.Path('/proc')/pid;env=dict(x.split('=',1) for x in (proc/'environ').read_bytes().decode().split('\0') if '=' in x)
endpoint='/run/user/1000/ethershell-control-experience-'+env['DISPLAY'].replace(':','').replace('.','-')
def request(data):
 with socket.socket(socket.AF_UNIX,socket.SOCK_STREAM) as c:
  c.settimeout(10);c.connect(endpoint);c.sendall(json.dumps(data).encode()+b'\n');return c.recv(32768).decode().strip()
assert request(dict(command='settings-page',route='location'))=='ok'
assert json.loads(request(dict(command='settings-state')))['route']=='location'
assert request(dict(command='settings-page',route='backup'))=='ok';time.sleep(1)
assert json.loads(request(dict(command='settings-state')))['route']=='backup'
assert request(dict(command='settings-screenshot'))=='ok'
code="""import dbus,json
b=dbus.SessionBus();out={}
for c in ('EtherLock','EtherCamera','EtherPhone','EtherLocation','EtherSensors','EtherNotifications'):
 try:
  n='com.etherneco.'+c+'1';d=json.loads(str(dbus.Interface(b.get_object(n,'/com/etherneco/'+c+'1'),n).GetState(timeout=3)))
  out[c]={k:d.get(k) for k in ('ready','locked','recording','busy','activeSubscriptions')}
 except dbus.DBusException as e:out[c]={'error':e.get_dbus_name()}
print(json.dumps(out))
"""
user=['runuser','-u','mobian','--','env','XDG_RUNTIME_DIR=/run/user/1000','DBUS_SESSION_BUS_ADDRESS=unix:path=/run/user/1000/bus']
health=run(user+['python3','-c',code]);assert health['exit']==0
backup=json.loads(subprocess.check_output(['etherbackup','status'],text=True))
services=run(['systemctl','is-active','ssh','NetworkManager','ModemManager','etherhardware','etherpower','etherpocket-modem','bluetooth','etherbackup','etherupdate','polkit']);assert services['exit']==0
print(json.dumps(dict(kernel=pathlib.Path('/proc/sys/kernel/osrelease').read_text().strip(),shell=str((proc/'exe').resolve()),
 shellRoute='backup',locationRouteVerified=True,health=json.loads(health['stdout']),services=services,
 backupStatus=backup,usb=json.loads(subprocess.check_output(['etherbackup','usb-devices'],text=True)),
 helperInstalled='commission-usb' in subprocess.check_output(['etherbackup','--help'],text=True),
 screenshot='/home/mobian/.config/ethershell/validation/settings2-screen.png',
 updateReady=json.loads(subprocess.check_output(['etherupdate','state'],text=True)).get('ready'),
 wifi=run(['nmcli','-t','-f','DEVICE,STATE','device']),
 note='No real-data repository or recovery password configured. No Android/boot/firmware writes.')))
'''
 result=json.loads(remote(source,timeout=90))
 output=ROOT/'evidence/etherbackup-live';output.mkdir(exist_ok=True)
 (output/'regression.json').write_text(json.dumps(result,indent=2)+'\n',encoding='utf-8')
 ssh=runpy.run_path(str(ROOT/'scripts/deploy-ethermobile.py'))['SSH']
 subprocess.run(['scp',*ssh[1:-1],ssh[-1]+':'+result['screenshot'],str(output/'backup-live.png')],capture_output=True,check=True,timeout=30)
 print(json.dumps({k:v for k,v in result.items() if k not in ('backupStatus','health')},indent=2))
