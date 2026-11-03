"""Real unprivileged bus rejections and installed policy checks, no data restore."""
from pathlib import Path
import json,runpy
ROOT=Path(__file__).resolve().parent.parent
remote=runpy.run_path(str(ROOT/'scripts/verify-etherupdate-device.py'))['remote']
if __name__=='__main__':
 source=r'''
import json,pathlib,subprocess
assert pathlib.Path('/etc/etherpocket/disk-identity').read_text().strip()=='GM1920-548cb338-mobian-sda21'
code="""import dbus,json
b=dbus.SystemBus();n='com.etherneco.EtherBackup1';api=dbus.Interface(b.get_object(n,'/com/etherneco/EtherBackup1'),n);results={}
for method,args in [('Inspect',[]),('Backup',['personal','absent']),('Verify',['absent','sample']),('Preview',['absent','']),('Restore',['absent','',True]),('Protect',['absent']),('RecoveryInfo',['absent']),('ReportEvent',['backup-completed'])]:
 try:getattr(api,method)(*args,timeout=10);results[method]={'denied':False}
 except dbus.DBusException as e:results[method]={'denied':True,'error':e.get_dbus_name()}
public=json.loads(str(api.GetState(timeout=3)));results['public']={'noPrivateData':not any(k in public for k in ('history','destinations','manifest','passwordFile','password','files'))}
print(json.dumps(results))
"""
p=subprocess.run(['runuser','-u','nobody','--','python3','-c',code],capture_output=True,text=True,timeout=100,check=True)
data=json.loads(p.stdout);assert all(row.get('denied',row.get('noPrivateData')) for row in data.values())
state=json.loads(subprocess.check_output(['etherbackup','status'],text=True));assert not state['history'] and not state['destinations']
print(json.dumps(dict(checks=data,productionBackup=False,publicState=state['status'],rootPolicyMode=oct(pathlib.Path('/etc/etherbackup/policy.json').stat().st_mode&0o777))))
'''
 result=json.loads(remote(source,timeout=120))
 (ROOT/'evidence/etherbackup-authorization.json').write_text(json.dumps(result,indent=2)+'\n',encoding='utf-8');print(json.dumps(result,indent=2))
