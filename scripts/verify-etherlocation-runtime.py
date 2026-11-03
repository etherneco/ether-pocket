"""Bounded real-provider and resource observations; reports contain no coordinates."""
from pathlib import Path
import json,runpy,subprocess
ROOT=Path(__file__).resolve().parent.parent
SSH=runpy.run_path(str(ROOT/'scripts/deploy-ethermobile.py'))['SSH']
SOURCE=r'''
import hashlib,json,pathlib,subprocess,time,os
user=['runuser','-u','mobian','--','env','LANG=C.UTF-8','XDG_RUNTIME_DIR=/run/user/1000','DBUS_SESSION_BUS_ADDRESS=unix:path=/run/user/1000/bus']
def read(p):
 try:return pathlib.Path(p).read_text().strip()
 except OSError:return None
def power():
 return {p.name:{k:read(p/k) for k in ['status','current_now','voltage_now','capacity','online']} for p in pathlib.Path('/sys/class/power_supply').glob('*') if p.name in ('battery','usb','ac')}
def process():
 rows=[]
 for p in pathlib.Path('/proc').glob('[0-9]*/cmdline'):
  try:
   if p.read_bytes().startswith(b'/usr/bin/python3\0/usr/share/etherlocation/service.py'):
    fields=(p.parent/'stat').read_text().split(') ')[1].split();rows.append(dict(pid=p.parent.name,cpuTicks=int(fields[11])+int(fields[12])))
  except OSError:pass
 return rows
idleBefore=process();powerDisabled=power();time.sleep(5);idleAfter=process()
backend='/usr/libexec/etherlocation-qmi'
child=subprocess.Popen(user+[backend,'--test-seconds','60'],stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True)
time.sleep(10);powerSearching=power()
out,err=child.communicate(timeout=80);events=[json.loads(x) for x in out.splitlines()]
registry=subprocess.run(user+['etherhardware','diagnose','sensors'],capture_output=True,text=True,timeout=20)
for _ in range(20):
 time.sleep(.5)
 state=subprocess.run(user+['etherhardware','state'],capture_output=True,text=True,timeout=10)
 if state.returncode==0 and not json.loads(state.stdout).get('busy'):break
cap=subprocess.run(user+['etherhardware','capability','sensors.gnss'],capture_output=True,text=True,timeout=10)
print(json.dumps(dict(nativeSha256=hashlib.sha256(pathlib.Path(backend).read_bytes()).hexdigest(),exit=child.returncode,events=events,stderr=err,coordinates='redacted',
 idleBefore=idleBefore,idleAfter=idleAfter,clockTicks=os.sysconf('SC_CLK_TCK'),idleObservationSeconds=5,powerDisabled=powerDisabled,powerSearching=powerSearching,
 powerScope='USB-connected observations only; not battery-only GNSS consumption or navigation measurements',
 fixedPower='Not tested: no verified fix',navigationPower='Not tested: navigation deferred',
 hardwareDiagnosticExit=registry.returncode,gnssCapability=json.loads(cap.stdout) if cap.returncode==0 else cap.stderr),indent=2))
'''
if __name__=='__main__':
 p=subprocess.run(SSH+['python3 -'],input=SOURCE.encode(),capture_output=True,timeout=125)
 if p.returncode:raise RuntimeError(p.stderr.decode(errors='replace'))
 data=json.loads(p.stdout);(ROOT/'evidence/etherlocation-runtime-verification.json').write_text(json.dumps(data,indent=2)+'\n',encoding='utf-8')
 print(json.dumps(dict(exit=data['exit'],events=len(data['events']),fixes=sum(r['event']=='fix' for r in data['events']),resourcesReleased=any(r['event']=='released' for r in data['events']),capability=data['gnssCapability']),indent=2))
