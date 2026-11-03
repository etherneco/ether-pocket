"""Read-only live D-Bus/diagnostics/privacy/performance acceptance."""
from pathlib import Path
import json
import runpy
import shlex
import subprocess
ROOT = Path(__file__).resolve().parent.parent
SSH = runpy.run_path(str(ROOT / 'scripts/deploy-ethermobile.py'))['SSH']

if __name__ == '__main__':
    source = r'''
import dbus,json,pathlib,subprocess,time
bus=dbus.SystemBus()
api=dbus.Interface(bus.get_object('com.etherneco.EtherHardware1','/com/etherneco/EtherHardware1'),'com.etherneco.EtherHardware1')
def state():return json.loads(str(api.GetState()))
def settled(min_generation=0):
 for _ in range(120):
  s=state()
  if s.get('ready') and not s.get('busy') and s['generation']>min_generation:return s
  time.sleep(.25)
 raise AssertionError('Hardware collection did not settle')
s=settled();start=s['generation'];api.RunDiagnostics('all');s=settled(start)
assert all(c['lastVerification'] for c in s['capabilities'] if c['hardwareProvider'])
assert len(json.loads(str(api.GetCapabilities()))['capabilities'])==len(s['capabilities'])
assert json.loads(str(api.GetCapability('not.a.capability'))) is None
assert json.loads(str(api.GetCapability('wifi.client')))['id']=='wifi.client'
try:api.Refresh('../invalid')
except dbus.DBusException as e:assert e.get_dbus_name().endswith('.Invalid')
else:raise AssertionError('Invalid category accepted')
report=str(api.ExportReport('json'));doc=json.loads(report)
assert not any(c['status']=='Working' for c in doc['components'] if c['category']=='camera')
assert 'IMEI' not in report and 'ICCID' not in report
assert not s.get('eventWarning'),s.get('eventWarning')
firmware=[{'component':r['id'],**r['driver']['firmware']} for r in s['components'] if r.get('driver',{}).get('firmware',{}).get('dependencies')]
pid=int(subprocess.check_output(['systemctl','show','etherhardware','-p','MainPID','--value'],text=True))
proc=pathlib.Path('/proc')/str(pid)
def sample():
 stats=(proc/'stat').read_text().split();status=(proc/'status').read_text().splitlines()
 return {'ticks':int(stats[13])+int(stats[14]),'rss':next(x for x in status if x.startswith('VmRSS:')),'generation':state()['generation'],'monotonic':time.monotonic()}
before=sample();time.sleep(20);after=sample()
import os
cpu=100*(after['ticks']-before['ticks'])/os.sysconf('SC_CLK_TCK')/(after['monotonic']-before['monotonic'])
assert cpu<3,('Unexpected idle CPU',cpu)
print(json.dumps({'diagnosticsReady':True,'inventory':s,'firmwareMetadata':firmware,
 'performance':{'durationSeconds':after['monotonic']-before['monotonic'],'cpuPercentOfOneCore':cpu,'before':before,'after':after,'limitation':'Short CPU/RSS sample; not a battery-life measurement'},
 'invalidInputRejected':True,'eventSubscriptionAvailable':True,'redactedReportBytes':len(report)},indent=2))
'''
    p = subprocess.run(SSH + ['python3 -c ' + shlex.quote(source)], capture_output=True, timeout=80)
    if p.returncode:
        raise RuntimeError(p.stderr.decode(errors='replace')[-5000:])
    data = json.loads(p.stdout)
    (ROOT / 'evidence/etherhardware-diagnostics.json').write_text(json.dumps(data, indent=2) + '\n', encoding='utf-8')
    print(json.dumps({k: data[k] for k in ('diagnosticsReady', 'performance', 'eventSubscriptionAvailable')}, indent=2))
