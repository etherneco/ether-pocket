"""Final read-only regression after installation and shell acceptance."""
from pathlib import Path
import hashlib,json,runpy
ROOT=Path(__file__).resolve().parent.parent
remote=runpy.run_path(str(ROOT/'scripts/check-etherphone-device.py'))['remote']
if __name__=='__main__':
    baseline=json.loads((ROOT/'evidence/etherphone-device-verification.json').read_text(encoding='utf-8'))
    installed=json.loads((ROOT/'evidence/etherphone-install.json').read_text(encoding='utf-8'))
    source=r'''
import dbus,hashlib,json,os,pathlib,subprocess,time
user=['runuser','-u','mobian','--','env','XDG_RUNTIME_DIR=/run/user/1000','DBUS_SESSION_BUS_ADDRESS=unix:path=/run/user/1000/bus']
def run(args):return subprocess.check_output(args,text=True,timeout=20).strip()
state=json.loads(run(user+['etherphone-control','state']));assert state['ready'] and not state['calls']
pid=int(run(user+['systemctl','--user','show','etherphone','-p','MainPID','--value']));assert pid==BASELINE['processBaseline']['pid'],'Unexpected controller restart'
elapsed=time.time()-BASELINE['processBaseline']['timestamp'];assert elapsed>=60
old=BASELINE['processBaseline']['stat'].split();new=pathlib.Path('/proc',str(pid),'stat').read_text().split()
delta=sum(int(new[i])-int(old[i]) for i in [13,14]);hz=os.sysconf('SC_CLK_TCK')
services={u:run(['systemctl','is-active',u]) for u in ['NetworkManager','ModemManager','ssh','bluetooth','etherhardware','etherpower','ethershare','etherpocket-modem']}
assert services==INSTALLED['after']['services']
audio={u:run(user+['systemctl','--user','show',u,'-p','MainPID','--value']) for u in ['pipewire','pipewire-pulse','wireplumber','etheraudio']};assert audio==BASELINE['audioPids']
hashes={n:hashlib.sha256(pathlib.Path('/usr/share/etherphone',n).read_bytes()).hexdigest() for n in BASELINE['coreHashes']};assert hashes==BASELINE['coreHashes']
units={u:run(user+['systemctl','--user','is-enabled',u]) for u in ['etherphone','etheraudio']}
wifi=run(['curl','--interface','wlan0','--max-time','15','-sS','-o','/dev/null','-w','%{http_code}','https://deb.debian.org']);assert wifi=='200'
assert pathlib.Path('/proc/sys/kernel/random/boot_id').read_text().strip()==INSTALLED['after']['boot']
print(json.dumps({'services':services,'audioPids':audio,'coreHashes':hashes,'units':units,'wifiHTTPS':wifi,
 'phonePID':pid,'automaticRestarts':run(user+['systemctl','--user','show','etherphone','-p','NRestarts','--value']),
 'idleSample':{'elapsedSeconds':elapsed,'cpuPercentOfOneCore':100*delta/hz/elapsed,'rssKiB':int(run(['ps','-p',str(pid),'-o','rss=']))},
 'ready':state['ready'],'cellularStatus':state['status'],'ims':state['ims'],'volte':state['volte'],'audio':state['audio'],
 'realCallVerified':state['realCallVerified'],'calls':len(state['calls']),'historyCount':len(state['history']),
 'sourceUnchanged':True,'audioServersUnchanged':True,'bootUnchanged':True},indent=2))
'''.replace('BASELINE',repr(baseline)).replace('INSTALLED',repr(installed))
    result=json.loads(remote(source,timeout=50))
    for name,digest in baseline['coreHashes'].items():assert hashlib.sha256((ROOT/'etherphone'/name).read_bytes()).hexdigest()==digest
    result['packageHashes']={name:hashlib.sha256((ROOT/'build'/name).read_bytes()).hexdigest() for name in ['etherphone_0.1.0_arm64.deb','ethersms-phone_0.1.0_arm64.deb','ethershell-phone_2.1.0_arm64.deb']}
    for name,digest in installed['packages'].items():assert result['packageHashes'][name]==digest
    result['shell']=json.loads((ROOT/'evidence/etherphone-shell-deployment.json').read_text(encoding='utf-8'))
    (ROOT/'evidence/etherphone-final-regression.json').write_text(json.dumps(result,indent=2)+'\n',encoding='utf-8')
    print(json.dumps(result,indent=2))
