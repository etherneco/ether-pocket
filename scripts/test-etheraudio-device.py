"""Bounded control tests with no playback, recording, call or suspend."""
from pathlib import Path
import json,runpy,shlex,subprocess
ROOT=Path(__file__).resolve().parent.parent
SSH=runpy.run_path(str(ROOT/'scripts/deploy-ethermobile.py'))['SSH']
SOURCE=r'''
import dbus,json,os,pathlib,subprocess,time
NAME='com.etherneco.EtherAudio1';PATH='/com/etherneco/EtherAudio1'
bus=dbus.SessionBus();api=dbus.Interface(bus.get_object(NAME,PATH),NAME)
def state():
 for _ in range(100):
  data=json.loads(str(api.GetState()))
  if data.get('ready') and not data.get('busy'):return data
  time.sleep(.1)
 raise AssertionError('Audio service did not settle')
def command(action,target,data):
 for _ in range(30):
  try:return api.Command(action,target,json.dumps(data),timeout=35)
  except dbus.DBusException as e:
   if e.get_dbus_name().endswith('.Busy'):time.sleep(.2)
   else:raise
 raise AssertionError('Command remained busy')
def rejected(action):
 try:action()
 except dbus.DBusException:return True
 raise AssertionError('Unsafe/unsupported operation accepted')
def server_pids():return {u:subprocess.check_output(['systemctl','--user','show',u,'-p','MainPID','--value'],text=True).strip() for u in ['pipewire','pipewire-pulse','wireplumber']}
before=state();pids=server_pids();assert not before['source-outputs'] and not before['sink-inputs'],'Do not disrupt active audio streams'
sink=next(r for r in before['sinks'] if r['name']==before['default-sink'])
checks={};profile=before['config'];original=sink['percent'];mute=sink['mute']
try:
 command('volume','sink',{'id':sink['index'],'percent':min(100,original+5)})
 checks['volumeReadback']=abs(next(r for r in state()['sinks'] if r['index']==sink['index'])['percent']-min(100,original+5))<=1
 command('mute','sink',{'id':sink['index'],'muted':not mute})
 checks['muteReadback']=next(r for r in state()['sinks'] if r['index']==sink['index'])['mute']==(not mute)
 command('mute','sink',{'id':sink['index'],'muted':mute});command('volume','sink',{'id':sink['index'],'percent':original})
 checks['badVolumeRejected']=rejected(lambda:command('volume','sink',{'id':sink['index'],'percent':101}))
 checks['noConsentRejected']=rejected(lambda:api.StartCapture(before['default-source'],'Not a recording test',False,dbus.UInt32(1)))
 checks['callRouteBlocked']=rejected(lambda:command('call-route','earpiece',{}))
 token=str(command('focus','call',{}));checks['focusPresent']=len(state()['focus'])==1
 checks['callProtectsRoute']=rejected(lambda:command('select','sink',{'name':before['default-sink']}))
 command('release-focus',token,{})
 other=dbus.SessionBus(private=True);peer=dbus.Interface(other.get_object(NAME,PATH),NAME)
 for _ in range(30):
  try:peer.Command('focus','alarm','{}');break
  except dbus.DBusException as e:
   if e.get_dbus_name().endswith('.Busy'):time.sleep(.2)
   else:raise
 other.close()
 for _ in range(50):
  if not state()['focus']:break
  time.sleep(.2)
 checks['focusCrashCleanup']=state()['focus']==[]
 command('configure','',{'automatic':profile['automatic']})
 subprocess.run(['systemctl','--user','restart','etheraudio'],check=True)
 api=dbus.Interface(bus.get_object(NAME,PATH),NAME);after=state()
 checks['savedConfigSurvivesServiceRestart']=after['config']==profile
 checks['routesPreserved']=after['default-sink']==before['default-sink'] and after['default-source']==before['default-source']
 checks['audioServersNotRestarted']=server_pids()==pids
 checks['noRecording']=not after['recording'] and not after['managedCaptures']
 pid=int(subprocess.check_output(['systemctl','--user','show','etheraudio','-p','MainPID','--value'],text=True))
 proc=pathlib.Path('/proc')/str(pid)
 def ticks():
  values=(proc/'stat').read_text().split();return int(values[13])+int(values[14])
 first=ticks();start=time.monotonic();time.sleep(20);duration=time.monotonic()-start
 overhead={'durationSeconds':duration,'cpuPercentOneCore':100*(ticks()-first)/os.sysconf('SC_CLK_TCK')/duration,
 'rss':next(s for s in (proc/'status').read_text().splitlines() if s.startswith('VmRSS:')),
 'scope':'Short process-overhead sample; no isolated electrical power or DSP offload measurement'}
 assert all(checks.values()),checks
 print(json.dumps({'checks':checks,'overhead':overhead,'before':before,'after':state(),'serverPids':pids},indent=2))
finally:
 try:command('mute','sink',{'id':sink['index'],'muted':mute});command('volume','sink',{'id':sink['index'],'percent':original})
 except dbus.DBusException:pass
'''
if __name__=='__main__':
    command='runuser -u mobian -- env XDG_RUNTIME_DIR=/run/user/1000 DBUS_SESSION_BUS_ADDRESS=unix:path=/run/user/1000/bus python3 -c '+shlex.quote(SOURCE)
    p=subprocess.run(SSH+[command],capture_output=True,timeout=100)
    if p.returncode:raise RuntimeError(p.stderr.decode(errors='replace')[-7000:])
    data=json.loads(p.stdout)
    (ROOT/'evidence/etheraudio-device-tests.json').write_text(json.dumps(data,indent=2)+'\n',encoding='utf-8')
    print(json.dumps({k:data[k] for k in ['checks','overhead']},indent=2))
