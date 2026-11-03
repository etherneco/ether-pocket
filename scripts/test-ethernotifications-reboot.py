"""User-attended reboot acceptance; snapshots contain hashes, never message text."""
from pathlib import Path
import argparse,json,runpy,subprocess
ROOT=Path(__file__).resolve().parent.parent
remote=runpy.run_path(str(ROOT/'scripts/check-etherphone-device.py'))['remote']
SSH=runpy.run_path(str(ROOT/'scripts/deploy-ethermobile.py'))['SSH']
SOURCE=r'''
import hashlib,json,pathlib,socket,sqlite3,subprocess
P=pathlib.Path
assert P('/etc/etherpocket/disk-identity').read_text().strip()=='GM1920-548cb338-mobian-sda21'
u=['/usr/sbin/runuser','-u','mobian','--','env','XDG_RUNTIME_DIR=/run/user/1000','DBUS_SESSION_BUS_ADDRESS=unix:path=/run/user/1000/bus']
def run(args):return subprocess.check_output(args,text=True,timeout=20).strip()
def sha(path):return hashlib.sha256(P(path).read_bytes()).hexdigest()
phone=json.loads(run(u+['etherphone-control','state']));assert phone['ready'] and not phone['calls'],'An active call blocks reboot acceptance'
audio=json.loads(run(u+['etheraudio','state']));assert not audio.get('managedCaptures') and not audio.get('recording'),'An active recording blocks reboot acceptance'
marker=MARKER
if BEFORE:
 code="import dbus;b=dbus.SessionBus();a=dbus.Interface(b.get_object('org.freedesktop.Notifications','/org/freedesktop/Notifications'),'org.freedesktop.Notifications');print(int(a.Notify('Reboot acceptance',dbus.UInt32(0),'dialog-information','Reboot acceptance','Notification retained across the attended reboot',dbus.Array([],signature='s'),dbus.Dictionary({'x-ether-privacy':'public'},signature='sv'),dbus.Int32(0))))"
 marker=int(run(u+['python3','-c',code]))
db=P('/home/mobian/.local/state/ethernotifications/history.sqlite')
immutable=['id','appId','appName','title','body','timestamp','priority','category','group','thread','privacy','persistent','transient','eventId']
with sqlite3.connect('file:'+str(db)+'?mode=ro',uri=True) as store:
 records={}
 for ident,document in store.execute('SELECT id,document FROM records'):
  row=json.loads(document)
  records[str(ident)]=hashlib.sha256(json.dumps({k:row.get(k) for k in immutable},sort_keys=True).encode()).hexdigest()
 settings={k:hashlib.sha256(v.encode()).hexdigest() for k,v in store.execute('SELECT key,document FROM settings')}
assert str(marker) in records
pids=run(['pgrep','-u','1000','-x','ethershell']).split();assert len(pids)==1
proc=P('/proc')/pids[0];stage=(proc/'exe').resolve().parent.parent.parent
env=dict(x.split('=',1) for x in (proc/'environ').read_bytes().decode().split('\0') if '=' in x)
endpoint='/run/user/1000/ethershell-control-experience-'+env['DISPLAY'].replace(':','').replace('.','-')
with socket.socket(socket.AF_UNIX,socket.SOCK_STREAM) as client:
 client.settimeout(8);client.connect(endpoint);client.sendall(b'{"command":"notification-state"}\n');state=json.loads(client.recv(8192))
owner=json.loads(run(u+['python3','-c',"import dbus,json;b=dbus.SessionBus();o=b.get_name_owner('org.freedesktop.Notifications');print(json.dumps({'owner':o,'pid':int(b.call_blocking('org.freedesktop.DBus','/org/freedesktop/DBus','org.freedesktop.DBus','GetConnectionUnixProcessID','s',(o,)))}))"]))
service_pid=int(run(u+['systemctl','--user','show','ethernotifications','-p','MainPID','--value']));assert owner['pid']==service_pid and service_pid!=int(pids[0])
print(json.dumps({'boot':P('/proc/sys/kernel/random/boot_id').read_text().strip(),'markerId':marker,'records':records,'settings':settings,'stage':str(stage),'shellPID':int(pids[0]),'shellUID':proc.stat().st_uid,'shellBinary':sha(proc/'exe'),'launcher':sha('/home/mobian/.local/bin/ethershell2-start'),'preferences':sha('/home/mobian/.config/ethershell/preferences.json'),'notificationCode':{n:sha('/usr/share/ethernotifications/'+n) for n in ['core.py','service.py']},'unitEnabled':run(u+['systemctl','--user','is-enabled','ethernotifications']),'unitActive':run(u+['systemctl','--user','is-active','ethernotifications']),'automaticRestarts':run(u+['systemctl','--user','show','ethernotifications','-p','NRestarts','--value']),'notificationOwner':owner,'uiState':state,'services':{n:subprocess.run(['systemctl','is-active',n],capture_output=True,text=True).stdout.strip() for n in ['ssh','NetworkManager','ModemManager','etherpocket-modem','bluetooth','etherhardware','etherpower','ethershare','ethermobile-data','etherpocket-usb-debug','etherpocket-usb-storage']},'audioActive':{n:run(u+['systemctl','--user','is-active',n]) for n in ['pipewire','pipewire-pulse','wireplumber','etheraudio','etherphone']},'wifiHTTPS':run(['curl','--interface','wlan0','--max-time','15','-sS','-o','/dev/null','-w','%{http_code}','https://deb.debian.org']),'databaseMode':oct(db.stat().st_mode&0o777)},indent=2))
'''
if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('action',choices=['before','reboot','after']);action=parser.parse_args().action
    before_path=ROOT/'evidence/ethernotifications-reboot-before.json'
    if action=='reboot':
        before=json.loads(before_path.read_text(encoding='utf-8'));assert before['unitEnabled']=='enabled' and before['uiState']['ready']
        result=subprocess.run(SSH+['etherpower action restart'],capture_output=True,timeout=35)
        print(json.dumps({'exit':result.returncode,'out':result.stdout.decode(errors='replace'),'error':result.stderr.decode(errors='replace')}))
        assert result.returncode in (0,255,4294967295,-1)
    else:
        before=json.loads(before_path.read_text(encoding='utf-8')) if action=='after' else None
        source=SOURCE.replace('BEFORE',repr(action=='before')).replace('MARKER',repr(before['markerId'] if before else 0))
        data=json.loads(remote(source,timeout=65))
        (ROOT/('evidence/ethernotifications-reboot-'+action+'.json')).write_text(json.dumps(data,indent=2),encoding='utf-8')
        if before:
            checks={k:before[k]==data[k] for k in ['settings','stage','shellBinary','launcher','preferences','notificationCode','databaseMode']}
            checks.update(newBoot=before['boot']!=data['boot'],historyPreserved=all(data['records'].get(k)==v for k,v in before['records'].items()),markerPreserved=str(before['markerId']) in data['records'],independentOwner=data['notificationOwner']['pid']!=data['shellPID'],enabled=data['unitEnabled']=='enabled',active=data['unitActive']=='active',shellUser=data['shellUID']==1000,uiReady=data['uiState'].get('ready',False),noMarkerBannerReplay=data['uiState'].get('bannerId')!=before['markerId'],wifiHTTPS=data['wifiHTTPS']=='200',servicesRestored=all(data['services'][n]=='active' for n,v in before['services'].items() if v=='active'),audioRestored=all(v=='active' for v in data['audioActive'].values()),noCrashRestarts=data['automaticRestarts']=='0')
            (ROOT/'evidence/ethernotifications-reboot-comparison.json').write_text(json.dumps(checks,indent=2),encoding='utf-8')
            print(json.dumps(checks,indent=2));assert all(checks.values())
        else:print(json.dumps({k:v for k,v in data.items() if k not in ('records','settings')},indent=2))
