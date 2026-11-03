"""Install only session policy. Never restarts the working audio server or drivers."""
from pathlib import Path
import hashlib,json,runpy,shlex,subprocess
ROOT=Path(__file__).resolve().parent.parent
SSH=runpy.run_path(str(ROOT/'scripts/deploy-ethermobile.py'))['SSH']
SOURCE=r'''
import hashlib,json,pathlib,subprocess,sys,tempfile,time
assert pathlib.Path('/etc/etherpocket/disk-identity').read_text().strip()=='GM1920-548cb338-mobian-sda21'
payload=sys.stdin.buffer.read();assert hashlib.sha256(payload).hexdigest()==DIGEST
user=['runuser','-u','mobian','--','env','XDG_RUNTIME_DIR=/run/user/1000','DBUS_SESSION_BUS_ADDRESS=unix:path=/run/user/1000/bus']
def run(args):return subprocess.check_output(args,text=True,timeout=15).strip()
def probe():
 return {'bootId':pathlib.Path('/proc/sys/kernel/random/boot_id').read_text().strip(),
 'services':{u:subprocess.run(['systemctl','is-active',u],capture_output=True,text=True).stdout.strip() for u in ['NetworkManager','ssh','bluetooth','etherpower','etherhardware','etherpocket-modem','ModemManager','ethershare','ethermobile-data','etherpocket-usb-debug','etherpocket-usb-storage']},
 'audioPids':{u:run(user+['systemctl','--user','show',u,'-p','MainPID','--value']) for u in ['pipewire','pipewire-pulse','wireplumber']},
 'defaultSink':run(user+['pactl','get-default-sink']),'defaultSource':run(user+['pactl','get-default-source'])}
before=probe()
captures=json.loads(run(user+['pactl','--format=json','list','source-outputs']))
assert not captures,'Do not update session policy while an application is recording'
code_paths=['/usr/share/etheraudio/core.py','/usr/share/etheraudio/service.py','/usr/share/etheraudio/cli.py','/usr/bin/etheraudio','/usr/lib/systemd/user/etheraudio.service']
def code_hashes():return {f:hashlib.sha256(pathlib.Path(f).read_bytes()).hexdigest() if pathlib.Path(f).exists() else None for f in code_paths}
old_code=code_hashes()
was_active=subprocess.run(user+['systemctl','--user','is-active','etheraudio'],capture_output=True,text=True).stdout.strip()=='active'
with tempfile.TemporaryDirectory(dir='/var/tmp') as folder:
 p=pathlib.Path(folder)/'etheraudio.deb';p.write_bytes(payload)
 subprocess.run(['dpkg','--dry-run','-i',str(p)],check=True,stdout=sys.stderr)
 subprocess.run(['dpkg','-i',str(p)],check=True,stdout=sys.stderr)
subprocess.run(user+['systemctl','--user','daemon-reload'],check=True)
subprocess.run(user+['systemctl','--user','enable','--now','etheraudio'],check=True,stdout=sys.stderr)
if was_active and old_code!=code_hashes():subprocess.run(user+['systemctl','--user','restart','etheraudio'],check=True)
state={}
for _ in range(40):
 p=subprocess.run(user+['etheraudio','state'],capture_output=True,text=True,timeout=10)
 if p.returncode==0:
  state=json.loads(p.stdout)
  if state.get('ready') and not state.get('busy'):break
 time.sleep(.3)
assert state.get('ready'),state
tests=subprocess.run(user+['python3','-m','unittest','discover','-s','/usr/share/etheraudio/tests','-v'],capture_output=True,text=True)
assert tests.returncode==0,tests.stderr
after=probe();assert before==after,(before,after)
print(json.dumps({'packageSha256':DIGEST,'before':before,'after':after,'state':state,'tests':tests.stderr},indent=2))
'''
if __name__=='__main__':
    payload=(ROOT/'build/etheraudio_0.1.1_arm64.deb').read_bytes()
    p=subprocess.run(SSH+['python3 -c '+shlex.quote(SOURCE.replace('DIGEST',repr(hashlib.sha256(payload).hexdigest())))],input=payload,capture_output=True,timeout=100)
    if p.returncode:raise RuntimeError(p.stderr.decode(errors='replace')[-9000:])
    data=json.loads(p.stdout)
    (ROOT/'evidence/etheraudio-install.json').write_text(json.dumps(data,indent=2)+'\n',encoding='utf-8')
    print(json.dumps({'before':data['before'],'after':data['after'],'ready':data['state']['ready'],'tests':data['tests']},indent=2))
