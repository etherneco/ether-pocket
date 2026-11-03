"""Install EtherMAP and its location API update with an on-device rollback package."""
from pathlib import Path
import hashlib,io,json,runpy,shlex,subprocess,tarfile
ROOT=Path(__file__).resolve().parents[1]
SSH=runpy.run_path(str(ROOT/'scripts/deploy-ethermobile.py'))['SSH']
SOURCE=r'''
import hashlib,io,json,os,pathlib,shutil,subprocess,sys,tarfile,tempfile,time
assert pathlib.Path('/etc/etherpocket/disk-identity').read_text().strip()=='GM1920-548cb338-mobian-sda21'
user=['runuser','-u','mobian','--','env','LANG=C.UTF-8','XDG_RUNTIME_DIR=/run/user/1000','DBUS_SESSION_BUS_ADDRESS=unix:path=/run/user/1000/bus']
def run(args,timeout=40):return subprocess.run(args,capture_output=True,text=True,timeout=timeout)
def check(args,timeout=40):
 p=run(args,timeout);assert p.returncode==0,p.stdout+p.stderr;return p
def state():return json.loads(check(user+['etherlocation','state']).stdout)
def probe():
 return dict(boot=pathlib.Path('/proc/sys/kernel/random/boot_id').read_text().strip(),
  services={s:check(['systemctl','show',s,'-p','ActiveState','-p','MainPID']).stdout for s in ['ssh','NetworkManager','ModemManager','etherhardware','etherpower','etherpocket-modem','bluetooth']},
  session={s:check(user+['systemctl','--user','show',s,'-p','MainPID']).stdout for s in ['etherlock','ethernotifications','pipewire','pipewire-pulse','wireplumber']},
  network=check(['nmcli','-t','-f','DEVICE,TYPE,STATE','device']).stdout,
  shell=run(['pgrep','-u','1000','-x','ethershell']).stdout)
before=probe();oldstate=state();assert not oldstate['active'] and not oldstate['activeApplications'],'Wait for active location sessions'
assert run(['pgrep','-x','ethermap']).returncode!=0,'Close EtherMAP before updating'
backup=pathlib.Path('/var/backups/ethermap-'+time.strftime('%Y%m%d-%H%M%S'));backup.mkdir(mode=0o700)
oldPackage=backup/'etherlocation-before.deb'
# Reconstruct the installed predecessor, not an unrelated local build.
with tempfile.TemporaryDirectory(prefix='ethermap-rollback-',dir='/var/tmp') as tmp:
 root=pathlib.Path(tmp);control=root/'DEBIAN';control.mkdir()
 from email.parser import Parser
 fields=Parser().parsestr(check(['dpkg-query','-s','etherlocation']).stdout)
 keep=['Package','Version','Architecture','Maintainer','Depends','Section','Priority','Homepage','Description']
 (control/'control').write_text('\n'.join(k+': '+fields[k] for k in keep if fields.get(k))+'\n')
 for name in check(['dpkg-query','-L','etherlocation']).stdout.splitlines():
  src=pathlib.Path(name)
  if not src.is_absolute() or not src.exists() and not src.is_symlink():continue
  dst=root/name.lstrip('/')
  if src.is_dir() and not src.is_symlink():dst.mkdir(parents=True,exist_ok=True)
  else:
   dst.parent.mkdir(parents=True,exist_ok=True)
   if src.is_symlink():dst.symlink_to(os.readlink(src))
   else:shutil.copy2(src,dst)
 for name in ['preinst','postinst','prerm','postrm','conffiles','triggers']:
  src=pathlib.Path('/var/lib/dpkg/info/etherlocation.'+name)
  if src.exists():shutil.copy2(src,control/name)
 check(['dpkg-deb','--build',str(root),str(oldPackage)])
records=[]
with tempfile.TemporaryDirectory(prefix='ethermap-install-',dir='/var/tmp') as tmp:
 folder=pathlib.Path(tmp)
 with tarfile.open(fileobj=io.BytesIO(sys.stdin.buffer.read()),mode='r:') as archive:
  for m in archive.getmembers():
   assert m.name in HASHES and m.isfile()
   data=archive.extractfile(m).read();assert hashlib.sha256(data).hexdigest()==HASHES[m.name]
   (folder/m.name).write_bytes(data)
 packages=[str(folder/n) for n in HASHES]
 check(['dpkg','--dry-run','-i']+packages)
 try:
  p=check(['dpkg','-i']+packages);records.append(p.stdout+p.stderr)
  check(user+['systemctl','--user','daemon-reload']);check(user+['systemctl','--user','restart','etherlocation'])
  current=state();assert current['ready'] and not current['active'] and current['config']==oldstate['config']
  # Bundled ODbL dataset is permitted offline data; no public tiles requested.
  region=json.loads(check(user+['python3','/usr/share/etherlocation/maps.py','import','/usr/share/ethermap/maps/westminster.mbtiles','--offline-license-confirmed']).stdout)
  suites={}
  for name in ['etherlocation','ethermap']:
   p=check(user+['python3','-m','unittest','discover','-s','/usr/share/'+name+'/tests','-v'],90)
   suites[name]=p.stdout+p.stderr
  after=probe();assert before==after,(before,after)
 except BaseException:
  run(['dpkg','-r','ethermap']);check(['dpkg','-i',str(oldPackage)])
  check(user+['systemctl','--user','daemon-reload']);check(user+['systemctl','--user','restart','etherlocation']);raise
result=dict(hashes=HASHES,rollbackPackage=str(oldPackage),previousState=oldstate,state=current,before=before,after=after,servicesUnchanged=before==after,region=region,tests=suites,installLog=records)
(backup/'deployment.json').write_text(json.dumps(result,indent=2)+'\n')
print(json.dumps(result,indent=2))
'''
if __name__=='__main__':
 files={'etherlocation.deb':ROOT/'build/etherlocation_0.1.1_arm64.deb','ethermap.deb':ROOT/'build/ethermap_0.1.0_arm64.deb'}
 hashes={n:hashlib.sha256(p.read_bytes()).hexdigest() for n,p in files.items()}
 buffer=io.BytesIO()
 with tarfile.open(fileobj=buffer,mode='w') as archive:
  for n,p in files.items():archive.add(p,arcname=n)
 p=subprocess.run(SSH+['python3 -c '+shlex.quote(SOURCE.replace('HASHES',repr(hashes)))],input=buffer.getvalue(),capture_output=True,timeout=180)
 if p.returncode:raise RuntimeError(p.stderr.decode(errors='replace')[-8000:])
 result=json.loads(p.stdout);(ROOT/'evidence/ethermap-device-install.json').write_text(json.dumps(result,indent=2)+'\n')
 print(json.dumps({k:result[k] for k in ['servicesUnchanged','rollbackPackage','state','region']},indent=2))
