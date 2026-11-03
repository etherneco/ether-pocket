"""Read-only final source, ownership, persistence, resource and regression evidence."""
from pathlib import Path
import hashlib,json,runpy
ROOT=Path(__file__).resolve().parent.parent
remote=runpy.run_path(str(ROOT/'scripts/check-etherphone-device.py'))['remote']
if __name__=='__main__':
    live=json.loads((ROOT/'evidence/ethernotifications-live-verification.json').read_text(encoding='utf-8'))
    source=r'''
import hashlib,json,os,pathlib,sqlite3,subprocess,time
u=['/usr/sbin/runuser','-u','mobian','--','env','XDG_RUNTIME_DIR=/run/user/1000','DBUS_SESSION_BUS_ADDRESS=unix:path=/run/user/1000/bus']
def run(args):return subprocess.check_output(args,text=True,timeout=20).strip()
pid=int(run(u+['systemctl','--user','show','ethernotifications','-p','MainPID','--value']));assert pid==BASELINE['pid']
elapsed=time.time()-BASELINE['timestamp'];assert elapsed>=60
old=BASELINE['stat'].split();new=pathlib.Path('/proc',str(pid),'stat').read_text().split()
delta=sum(int(new[i])-int(old[i]) for i in [13,14]);hz=os.sysconf('SC_CLK_TCK')
metadata=run(u+['python3','-c',"import dbus,json;b=dbus.SessionBus();o=b.get_name_owner('org.freedesktop.Notifications');print(json.dumps({'owner':o,'pid':int(b.call_blocking('org.freedesktop.DBus','/org/freedesktop/DBus','org.freedesktop.DBus','GetConnectionUnixProcessID','s',(o,)))}))"])
owner=json.loads(metadata);assert owner['pid']==pid
db=pathlib.Path('/home/mobian/.local/state/ethernotifications/history.sqlite')
with sqlite3.connect('file:'+str(db)+'?mode=ro',uri=True) as store:count=store.execute('SELECT count(*) FROM records').fetchone()[0]
assert count<=2000 and db.stat().st_mode&0o777==0o600
phone=json.loads(run(u+['etherphone-control','state']));assert phone['ready'] and not phone['calls']
wifi=run(['curl','--interface','wlan0','--max-time','15','-sS','-o','/dev/null','-w','%{http_code}','https://deb.debian.org']);assert wifi=='200'
services={n:run(['systemctl','is-active',n]) for n in ['ssh','NetworkManager','ModemManager','etherpocket-modem','bluetooth','etherhardware','etherpower','ethershare']}
audio={n:run(u+['systemctl','--user','show',n,'-p','MainPID','--value']) for n in ['pipewire','pipewire-pulse','wireplumber']}
hashes={name:hashlib.sha256(pathlib.Path('/usr/share/ethernotifications',name).read_bytes()).hexdigest() for name in ['core.py','service.py']}
print(json.dumps({'owner':owner,'notificationServiceEnabled':run(u+['systemctl','--user','is-enabled','ethernotifications']),'automaticRestarts':run(u+['systemctl','--user','show','ethernotifications','-p','NRestarts','--value']),'idleSample':{'elapsedSeconds':elapsed,'cpuPercentOfOneCore':100*delta/hz/elapsed,'rssKiB':int(run(['ps','-p',str(pid),'-o','rss=']))},'databaseRows':count,'databaseBytes':db.stat().st_size,'databasePermissions':'0600','services':services,'audioServers':audio,'wifiHTTPS':wifi,'boot':pathlib.Path('/proc/sys/kernel/random/boot_id').read_text().strip(),'phoneReady':True,'realCallsVerified':phone.get('realCallVerified',False),'sourceHashes':hashes},indent=2))
'''.replace('BASELINE',repr(live['baseline']))
    result=json.loads(remote(source,timeout=45))
    assert result['services']==live['services'] and result['audioServers']==live['audioServers'] and result['boot']==live['boot']
    for name,digest in result['sourceHashes'].items():assert hashlib.sha256((ROOT/'ethernotifications'/name).read_bytes()).hexdigest()==digest
    result['packages']={name:hashlib.sha256((ROOT/'build'/name).read_bytes()).hexdigest() for name in ['ethernotifications_0.1.0_arm64.deb','ethershell-notifications_2.1.0_arm64.deb','etheraudio-notifications_0.1.0_arm64.deb','etherphone-notifications_0.1.0_arm64.deb','ethersms-notifications_0.1.0_arm64.deb']}
    (ROOT/'evidence/ethernotifications-final-regression.json').write_text(json.dumps(result,indent=2),encoding='utf-8')
    print(json.dumps(result,indent=2))
