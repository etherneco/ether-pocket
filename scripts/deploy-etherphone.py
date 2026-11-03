"""Install local packages, retain private backup; never change modem/radio state."""
from pathlib import Path
import hashlib,io,json,runpy,tarfile
ROOT=Path(__file__).resolve().parent.parent
remote=runpy.run_path(str(ROOT/'scripts/check-etherphone-device.py'))['remote']
if __name__=='__main__':
    names=['etherphone_0.1.0_arm64.deb','ethersms-phone_0.1.0_arm64.deb']
    hashes={n:hashlib.sha256((ROOT/'build'/n).read_bytes()).hexdigest() for n in names}
    payload=io.BytesIO()
    with tarfile.open(fileobj=payload,mode='w:gz') as tar:
        for n in names:tar.add(ROOT/'build'/n,arcname=n)
    source=r'''
import dbus,hashlib,io,json,os,pathlib,sqlite3,subprocess,sys,tarfile,tempfile,time
assert pathlib.Path('/etc/etherpocket/disk-identity').read_text().strip()=='GM1920-548cb338-mobian-sda21'
assert subprocess.run(['pgrep','-u','1000','-x','ethersms'],capture_output=True).returncode!=0,'Close EtherSMS before replacing its contact provider'
user=['runuser','-u','mobian','--','env','XDG_RUNTIME_DIR=/run/user/1000','DBUS_SESSION_BUS_ADDRESS=unix:path=/run/user/1000/bus']
def run(args):return subprocess.check_output(args,text=True,timeout=15).strip()
def probe():
 return {'boot':pathlib.Path('/proc/sys/kernel/random/boot_id').read_text().strip(),
 'services':{u:run(['systemctl','is-active',u]) for u in ['ssh','NetworkManager','ModemManager','etherpocket-modem','bluetooth','etherpower','etherhardware','ethershare']},
 'audioPids':{u:run(user+['systemctl','--user','show',u,'-p','MainPID','--value']) for u in ['pipewire','pipewire-pulse','wireplumber','etheraudio']},
 'devices':run(['nmcli','-t','-f','DEVICE,TYPE,STATE','device'])}
before=probe()
core_paths=[pathlib.Path('/usr/share/etherphone',n) for n in ['core.py','service.py','provider.py','cli.py']]
old_hashes=[hashlib.sha256(p.read_bytes()).hexdigest() if p.exists() else None for p in core_paths]
prior_ready=True
if pathlib.Path('/usr/bin/etherphone-control').exists():
 prior=subprocess.run(user+['etherphone-control','state'],capture_output=True,text=True,timeout=10)
 if prior.returncode==0:
  assert not json.loads(prior.stdout).get('calls'),'Refuse to replace a live call controller'
  prior_ready=json.loads(prior.stdout).get('ready',False)
base=pathlib.Path('/home/mobian/.local/share/etherphone');base.mkdir(mode=0o700,parents=True,exist_ok=True);base.chmod(0o700);os.chown(base,1000,1000)
backup=base/('preinstall-'+str(time.time_ns()));backup.mkdir(mode=0o700);os.chown(backup,1000,1000)
for p in [pathlib.Path('/home/mobian/.local/share/Etherneco/EtherSMS/messages.sqlite'),pathlib.Path('/home/mobian/.local/share/ethercontacts/contacts.sqlite')]:
 if p.exists():
  dest=backup/(p.parent.name+'-'+p.name);a=sqlite3.connect('file:'+str(p)+'?mode=ro',uri=True);b=sqlite3.connect(dest);a.backup(b);a.close();b.close();dest.chmod(0o600);os.chown(dest,1000,1000)
with tempfile.TemporaryDirectory(dir='/var/tmp') as f:
 folder=pathlib.Path(f)
 with tarfile.open(fileobj=io.BytesIO(sys.stdin.buffer.read()),mode='r:gz') as tar:tar.extractall(folder,filter='data')
 packages=[]
 for name,digest in HASHES.items():
  p=folder/name;assert hashlib.sha256(p.read_bytes()).hexdigest()==digest;packages.append(str(p))
 subprocess.run(['dpkg','--dry-run','-i']+packages,check=True,stdout=sys.stderr)
 subprocess.run(['dpkg','-i']+packages,check=True,stdout=sys.stderr)
subprocess.run(user+['systemctl','--user','daemon-reload'],check=True)
subprocess.run(user+['systemctl','--user','enable','--now','etherphone'],check=True,stdout=sys.stderr)
new_hashes=[hashlib.sha256(p.read_bytes()).hexdigest() for p in core_paths]
if old_hashes!=new_hashes or not prior_ready:subprocess.run(user+['systemctl','--user','restart','etherphone'],check=True,stdout=sys.stderr)
state={}
for _ in range(50):
 p=subprocess.run(user+['etherphone-control','state'],capture_output=True,text=True,timeout=10)
 if p.returncode==0:
  state=json.loads(p.stdout)
  if state.get('ready'):break
 time.sleep(.1)
assert state.get('ready'),state
assert not state['calls'],'Do not run unattended acceptance during calls'
report=json.loads(run(user+['etherphone-control','diagnostics']))
after=probe();assert before==after,(before,after)
print(json.dumps({'packages':HASHES,'before':before,'after':after,'backup':str(backup),'state':{k:state.get(k) for k in ['ready','status','audio','volte','ims','incomingWake','powerInhibited','lastFailure','realCallVerified']},'diagnostics':report,'unitEnabled':run(user+['systemctl','--user','is-enabled','etherphone'])},indent=2))
'''.replace('HASHES',repr(hashes))
    result=json.loads(remote(source,payload.getvalue(),timeout=100))
    (ROOT/'evidence/etherphone-install.json').write_text(json.dumps(result,indent=2)+'\n',encoding='utf-8')
    print(json.dumps(result,indent=2))
