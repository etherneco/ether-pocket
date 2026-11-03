"""Read-only telephony audit using the existing pinned USB SSH connection."""
from pathlib import Path
import json, runpy, shlex, subprocess
ROOT = Path(__file__).resolve().parent.parent
SSH = runpy.run_path(str(ROOT/'scripts/deploy-ethermobile.py'))['SSH']
SOURCE = r'''
import datetime,json,pathlib,subprocess,shutil,dbus
def run(args):
 if not shutil.which(args[0]):return {'available':False}
 try:
  p=subprocess.run(args,capture_output=True,text=True,timeout=12)
  return {'exit':p.returncode,'out':p.stdout[:30000],'error':p.stderr[:1000]}
 except subprocess.TimeoutExpired:return {'error':'timeout'}
def read(p):
 try:return pathlib.Path(p).read_text().replace('\0','').strip()
 except OSError:return None
bus=dbus.SystemBus()
objects=dbus.Interface(bus.get_object('org.freedesktop.ModemManager1','/org/freedesktop/ModemManager1'),'org.freedesktop.DBus.ObjectManager').GetManagedObjects(timeout=8)
safe={}
allowed={'State','StateFailedReason','PowerState','UnlockRequired','Sim','RegistrationState','PacketServiceState','OperatorName','AccessTechnologies','Calls','EmergencyOnly','SupportedCapabilities','CurrentCapabilities','Drivers','Plugin','Ports','Revision'}
for path,interfaces in objects.items():
 if '/Call/' in path:continue
 safe[str(path)]={str(i):{str(k):v for k,v in props.items() if str(k) in allowed} for i,props in interfaces.items()}
names=[str(n) for n in bus.list_names() if any(t in str(n).lower() for t in ('modem','ofono','ims','ether','networkmanager'))]
user=['runuser','-u','mobian','--','env','XDG_RUNTIME_DIR=/run/user/1000','DBUS_SESSION_BUS_ADDRESS=unix:path=/run/user/1000/bus']
result={'timestamp':datetime.datetime.now(datetime.timezone.utc).isoformat(),'kernel':read('/proc/sys/kernel/osrelease'),'model':read('/sys/firmware/devicetree/base/model'),'objects':safe,'busNames':names,
 'qrtr':run(['qrtr-lookup']),'packages':run(['dpkg-query','-W','-f=${Package} ${Version}\n','modemmanager','ofono','libqmi-utils','network-manager']),
 'services':run(['systemctl','is-active','ModemManager','NetworkManager','ssh','bluetooth','etherhardware','etherpower','etherpocket-modem']),
 'audio':run(user+['etheraudio','state']),
 'voiceHelp':run(['qmicli','--help-voice']),'imsHelp':run(['qmicli','--help-imsa']),
 'ucmVoiceFiles':[str(p) for p in pathlib.Path('/usr/share/alsa/ucm2').rglob('*') if p.is_file() and any(t in p.name.lower() for t in ('voice','earpiece','call'))],
 'scope':'Read-only. No call, firmware write, NV change, audio PCM, network change, suspend or service restart.'}
# Read-only service queries; QRTR supports independent clients. Never acquire a
# second manager or send provisioning/control commands. Only retain safe results.
for key,flag in [('voiceMessages','--voice-get-supported-messages'),('imsRegistration','--imsa-get-ims-registration-status'),('imsServices','--imsa-get-ims-services-status')]:
 result[key]=run(['qmicli','-d','qrtr://0',flag])
result['nas']=run(['qmicli','-d','qrtr://0','--nas-get-serving-system'])
card=run(['qmicli','-d','qrtr://0','--uim-get-card-status'])
result['sim']={'exit':card.get('exit'),'error':card.get('error'),'statusLines':[s.strip() for s in card.get('out','').splitlines() if any(t in s for t in ('Card state:','Application state:','PIN1 state:','Application type:'))]}
result['networkDevices']=run(['nmcli','-t','-f','DEVICE,TYPE,STATE','device'])
result['modemManagerLog']=run(['journalctl','-u','ModemManager','-n','35','--no-pager','-o','cat'])
# Journal output is not an identifier-safe protocol. Keep only known diagnostics.
result['modemManagerLog']['out']='\n'.join(s for s in result['modemManagerLog'].get('out','').splitlines() if any(t in s for t in ('net port','QMI modem','couldn\'t','failed to','Failed to')))
# Audio state can contain application metadata; export only call-path evidence.
try:
 a=json.loads(result['audio']['out']);result['audio']={k:a.get(k) for k in ('ready','callAudio','earpiece','hardwareRegistry')}
except (KeyError,ValueError):result['audio']={'error':'EtherAudio state unavailable'}
print(json.dumps(result,indent=2,default=lambda v:int(v)))
'''
if __name__ == '__main__':
    p=subprocess.run(SSH+['python3 -c '+shlex.quote(SOURCE)],capture_output=True,timeout=100)
    if p.returncode:raise RuntimeError(p.stderr.decode(errors='replace'))
    data=json.loads(p.stdout)
    (ROOT/'evidence/etherphone-audit-2026-10-20.json').write_text(json.dumps(data,indent=2)+'\n',encoding='utf-8')
    print(json.dumps(data,indent=2))
