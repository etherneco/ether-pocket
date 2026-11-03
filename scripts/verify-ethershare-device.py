"""Read actual service state, permissions, sensors and native app renders."""
from pathlib import Path
import json,runpy,subprocess,shlex
ROOT=Path(__file__).resolve().parent.parent
SSH=runpy.run_path(str(ROOT/'scripts/deploy-ethermobile.py'))['SSH']
SOURCE=r'''
import dbus,json,os,pathlib,subprocess,time
assert pathlib.Path('/etc/etherpocket/disk-identity').read_text().strip()=='GM1920-548cb338-mobian-sda21'
api=dbus.Interface(dbus.SystemBus().get_object('com.etherneco.EtherShare1','/com/etherneco/EtherShare1'),'com.etherneco.EtherShare1')
api.Stop('all',timeout=60)
api.Configure(json.dumps({'upstream':'epcell0','autostart':False,'timeoutMinutes':0}),timeout=20)
def sample():
 pid=subprocess.check_output(['systemctl','show','ethershare','-p','MainPID','--value'],text=True).strip()
 def ticks():
  fields=pathlib.Path('/proc',pid,'stat').read_text().split();return int(fields[13])+int(fields[14])
 sensors=[];start=time.monotonic();before=ticks()
 for _ in range(10):
  rows={}
  for p in pathlib.Path('/sys/class/power_supply').glob('*'):
   if (p/'type').exists() and (p/'type').read_text().strip()=='Battery':
    rows[p.name]={k:(p/k).read_text().strip() for k in ['status','voltage_now','current_now','capacity'] if (p/k).exists()}
  sensors.append(rows);time.sleep(1)
 return {'seconds':round(time.monotonic()-start,2),'controller_cpu_percent_one_core':round((ticks()-before)/os.sysconf('SC_CLK_TCK')/(time.monotonic()-start)*100,3),'sensors':sensors,'meaning':'Battery sensor values while USB-powered; NOT total device input power'}
result={}
try:
 result['idle']=sample()
 api.Start('usb','usb0',False,timeout=60);result['lte_usb']=sample();api.Stop('usb',timeout=30)
 api.StartConcurrentHotspot('wlan0',timeout=60);result['lte_hotspot']=sample();api.Stop('hotspot',timeout=30)
finally:
 api.Stop('all',timeout=60);api.Configure(json.dumps({'upstream':'auto','timeoutMinutes':0}),timeout=20)
folder=pathlib.Path('/var/tmp/ethershare-captures');folder.mkdir(exist_ok=True);os.chown(folder,1000,1000)
renders={}
for name,args in [('phone',[]),('desktop',['--desktop'])]:
 p=subprocess.run(['/usr/sbin/runuser','-u','mobian','--','env','QT_QPA_PLATFORM=offscreen','QT_QUICK_BACKEND=software','QT_QUICK_CONTROLS_STYLE=Basic','QT_SCALE_FACTOR=1','/usr/bin/ethershare']+args+['--capture',str(folder/(name+'.png'))],capture_output=True,text=True,timeout=15)
 renders[name]={'exit':p.returncode,'stderr':p.stderr}
code="import dbus;api=dbus.Interface(dbus.SystemBus().get_object('com.etherneco.EtherShare1','/com/etherneco/EtherShare1'),'com.etherneco.EtherShare1');api.Configure('{}',timeout=10)"
p=subprocess.run(['/usr/sbin/runuser','-u','nobody','--','python3','-c',code],capture_output=True,text=True,timeout=15)
result['unauthorized_mutation_denied']=p.returncode!=0
result['renders']=renders
result['config_permissions']=oct(pathlib.Path('/var/lib/ethershare/config.json').stat().st_mode&0o777)
result['services']=subprocess.run(['systemctl','is-active','NetworkManager','ModemManager','ethermobile-data','bluetooth','ssh','etherpocket-usb-debug','etherpocket-usb-storage','ethershare'],capture_output=True,text=True).stdout.splitlines()
result['sharing_off']=not json.loads(api.GetState())['active']
result['forward_restored']=pathlib.Path('/proc/sys/net/ipv4/ip_forward').read_text().strip()
print(json.dumps(result))
'''

if __name__=='__main__':
    r=subprocess.run(SSH+['python3 -c '+shlex.quote(SOURCE)],capture_output=True,timeout=100)
    if r.returncode:raise RuntimeError(r.stderr.decode()[-3500:])
    data=json.loads(r.stdout)
    (ROOT/'evidence/ethershare-device-validation.json').write_text(json.dumps(data,indent=2)+'\n',encoding='utf-8')
    for name in ['phone','desktop']:
        r=subprocess.run(SSH+['cat /var/tmp/ethershare-captures/'+name+'.png'],capture_output=True,check=True)
        (ROOT/'evidence'/('ethershare-'+name+'.png')).write_bytes(r.stdout)
    print(json.dumps({k:v for k,v in data.items() if k not in ['idle','lte_usb','lte_hotspot']},indent=2))
    print('CPU percent:',{k:data[k]['controller_cpu_percent_one_core'] for k in ['idle','lte_usb','lte_hotspot']})
    assert all(x=='active' for x in data['services'])
    assert data['unauthorized_mutation_denied'] and data['config_permissions']=='0o600'
    assert all(x['exit']==0 and not x['stderr'] for x in data['renders'].values())
