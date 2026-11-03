"""Read live MM state, retaining only an explicit non-secret field allowlist."""
from pathlib import Path
import json
import runpy
import subprocess
ROOT=Path(__file__).resolve().parent.parent
SSH=runpy.run_path(str(ROOT/'scripts/deploy-ethermobile.py'))['SSH']
REMOTE=r'''
import json,re,subprocess
def run(args):return subprocess.run(args,capture_output=True,text=True,timeout=20)
def flatten(data,prefix=''):
 result={}
 for k,v in data.items():
  key=prefix+'.'+k if prefix else k
  if isinstance(v,dict):result.update(flatten(v,key))
  else:result[key]=v
 return result
listed=run(['mmcli','-L'])
paths=re.findall(r'/org/freedesktop/ModemManager1/Modem/\d+',listed.stdout)
modems=[]
for path in paths:
 p=run(['mmcli','-m',path,'-J'])
 data=flatten(json.loads(p.stdout)) if p.returncode==0 else {}
 safe={k:v for k,v in data.items() if k in {
 'modem.generic.state','modem.generic.state-failed-reason','modem.generic.power-state',
 'modem.generic.signal-quality.value','modem.generic.signal-quality.recent',
 'modem.generic.access-technologies','modem.generic.ports','modem.generic.drivers',
 'modem.generic.plugin','modem.generic.current-capabilities','modem.generic.supported-capabilities',
 'modem.3gpp.operator-code','modem.3gpp.operator-name','modem.3gpp.registration-state',
 'modem.3gpp.packet-service-state','modem.generic.unlock-required','modem.generic.sim',
 'modem.generic.bearers'}}
 sim=data.get('modem.generic.sim')
 if sim and sim!='--':
  p=run(['mmcli','-i',sim,'-J'])
  sim_data=flatten(json.loads(p.stdout)) if p.returncode==0 else {}
  safe['sim_operator']={k:v for k,v in sim_data.items() if k in {'sim.properties.operator-name','sim.properties.operator-code','sim.properties.active'}}
 modems.append({'path':path,'properties':safe})
print(json.dumps({'modems':modems,'network_devices':run(['nmcli','-t','-f','DEVICE,TYPE,STATE','device']).stdout,'services':run(['systemctl','is-active','NetworkManager','ssh','bluetooth','etherpocket-modem']).stdout},indent=2))
'''
if __name__=='__main__':
    r=subprocess.run(SSH+['python3 -'],input=REMOTE.encode(),capture_output=True,check=True,timeout=90)
    report=json.loads(r.stdout)
    (ROOT/'evidence/ethermobile-live-state-2026-10-18.json').write_text(json.dumps(report,indent=2)+'\n',encoding='utf-8')
    print(json.dumps(report,indent=2))
