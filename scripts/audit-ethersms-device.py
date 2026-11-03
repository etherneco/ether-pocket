from pathlib import Path
import json, subprocess, runpy
ROOT=Path(__file__).resolve().parent.parent
SSH=runpy.run_path(str(ROOT/'scripts/deploy-ethermobile.py'))['SSH']
remote=r'''
import json,subprocess,shutil
commands={
'messaging':['busctl','introspect','org.freedesktop.ModemManager1','/org/freedesktop/ModemManager1/Modem/1','org.freedesktop.ModemManager1.Modem.Messaging'],
'services':['systemctl','is-active','ModemManager','ofono','NetworkManager','ssh','bluetooth','etherpocket-modem'],
'capture':['arecord','-l'],
'audio':['runuser','-u','mobian','--','env','XDG_RUNTIME_DIR=/run/user/1000','pactl','list','short','sources'],
'notification':['runuser','-u','mobian','--','env','DBUS_SESSION_BUS_ADDRESS=unix:path=/run/user/1000/bus','busctl','--user','status','org.freedesktop.Notifications'],
'local_ai':['systemctl','is-active','ollama','ethermcp'],
'qrtr':['qrtr-lookup']}
out={}
for k,args in commands.items():
 try:
  r=subprocess.run(args,capture_output=True,text=True,timeout=20);out[k]={'code':r.returncode,'output':r.stdout[:12000]}
 except Exception as e:out[k]={'error':type(e).__name__}
r=subprocess.run(['mmcli','-m','1','-J'],capture_output=True,text=True,timeout=20)
d=json.loads(r.stdout)['modem'] if r.returncode==0 else {}
out['modem']={k:v for k,v in d.get('generic',{}).items() if k in ['state','unlock-required','power-state','ports','sim']}
out['registration']={k:v for k,v in d.get('3gpp',{}).items() if k in ['registration-state','packet-service-state']}
out['executables']={k:shutil.which(k) for k in ['whisper-cli','vosk-transcriber','espeak-ng','piper','parec','paplay']}
print(json.dumps(out,indent=2))
'''
if __name__=='__main__':
 r=subprocess.run(SSH+['python3 -'],input=remote.encode(),capture_output=True,timeout=100,check=True)
 data=json.loads(r.stdout); target=ROOT/'evidence/ethersms-audit-2026-10-19.json';target.write_text(json.dumps(data,indent=2)+'\n');print(target);print(json.dumps(data,indent=2))
