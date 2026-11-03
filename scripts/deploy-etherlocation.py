"""Install EtherLocation and the optional camera API update after offline tests.

Preserves live shell, modem, network, audio, lock and power processes.
"""
from pathlib import Path
import hashlib,io,json,runpy,shlex,subprocess,tarfile
ROOT=Path(__file__).resolve().parent.parent
SSH=runpy.run_path(str(ROOT/'scripts/deploy-ethermobile.py'))['SSH']
SOURCE=r'''
import hashlib,io,json,os,pathlib,subprocess,sys,tarfile,tempfile
assert pathlib.Path('/etc/etherpocket/disk-identity').read_text().strip()=='GM1920-548cb338-mobian-sda21'
user=['runuser','-u','mobian','--','env','LANG=C.UTF-8','XDG_RUNTIME_DIR=/run/user/1000','DBUS_SESSION_BUS_ADDRESS=unix:path=/run/user/1000/bus']
def run(args):return subprocess.run(args,capture_output=True,text=True,timeout=40)
def production_shells():
 result=[]
 for pid in run(['pgrep','-u','1000','-x','ethershell']).stdout.split():
  try:
   if b'--development' not in (pathlib.Path('/proc')/pid/'cmdline').read_bytes():result.append(pid)
  except FileNotFoundError:pass
 return sorted(result)
def probe():
 return dict(boot=pathlib.Path('/proc/sys/kernel/random/boot_id').read_text().strip(),
  services={s:run(['systemctl','is-active',s]).stdout.strip() for s in ['ssh','NetworkManager','ModemManager','etherhardware','etherpower','etherpocket-modem','bluetooth']},
  sessionPids={s:run(user+['systemctl','--user','show',s,'-p','MainPID','--value']).stdout.strip() for s in ['etherlock','ethernotifications','pipewire','pipewire-pulse','wireplumber']},
  network=run(['nmcli','-t','-f','DEVICE,TYPE,STATE','device']).stdout,
  shell=production_shells())
before=probe()
previousLocation=run(user+['etherlocation','state'])
previousConfiguration=json.loads(previousLocation.stdout)['config'] if previousLocation.returncode==0 else None
if previousLocation.returncode==0:assert not json.loads(previousLocation.stdout)['active'],'Wait for active location sessions before updating'
camera=run(user+['ethercamera','state']);assert camera.returncode==0
assert not json.loads(camera.stdout)['busy'],'Close active camera before updating'
with tempfile.TemporaryDirectory(prefix='etherlocation-install-',dir='/var/tmp') as folder:
 folder=pathlib.Path(folder)
 with tarfile.open(fileobj=io.BytesIO(sys.stdin.buffer.read()),mode='r:') as archive:
  for member in archive.getmembers():
   assert member.name in HASHES and member.isfile()
   data=archive.extractfile(member).read();assert hashlib.sha256(data).hexdigest()==HASHES[member.name]
   (folder/member.name).write_bytes(data)
 packages=[str(folder/n) for n in HASHES if n.endswith('.deb')]
 for args in (['dpkg','--dry-run','-i']+packages,['dpkg','-i']+packages):
  p=run(args);assert p.returncode==0,p.stdout+p.stderr
 p=run(user+['systemctl','--user','daemon-reload']);assert p.returncode==0,p.stderr
 p=run(user+['systemctl','--user','restart','etherlocation']);assert p.returncode==0,p.stderr
 p=run(user+['systemctl','--user','restart','ethercamera']);assert p.returncode==0,p.stderr
 p=run(user+['etherlocation','state']);assert p.returncode==0,p.stderr
 state=json.loads(p.stdout);assert state['ready'] and not state['active']
 if previousConfiguration is not None:assert state['config']==previousConfiguration,'Location preferences must survive an update'
 else:assert not state['config']['history'] and not state['config']['enabled']
 data=(folder/'overview.mbtiles').read_bytes();public=pathlib.Path('/var/tmp/etherlocation-world-overview.mbtiles');public.write_bytes(data);public.chmod(0o644)
 p=run(user+['python3','/usr/share/etherlocation/maps.py','import',str(public),'--offline-license-confirmed']);assert p.returncode==0,p.stderr
 region=json.loads(p.stdout)
 tests=run(user+['python3','-m','unittest','discover','-s','/usr/share/etherlocation/tests','-v']);assert tests.returncode==0,tests.stderr
 cameraTests=run(user+['python3','-m','unittest','discover','-s','/usr/share/ethercamera/tests','-v']);assert cameraTests.returncode==0,cameraTests.stderr
after=probe();assert before==after,(before,after)
print(json.dumps(dict(hashes=HASHES,before=before,after=after,state=state,region=region,tests=tests.stderr,cameraTests=cameraTests.stderr),indent=2))
'''
if __name__=='__main__':
    files={'etherlocation.deb':ROOT/'build/etherlocation_0.1.0_arm64.deb','ethercamera.deb':ROOT/'build/ethercamera_0.4.1_arm64.deb','etherhardware.deb':ROOT/'build/etherhardware_0.1.1_arm64.deb','overview.mbtiles':ROOT/'build/etherlocation-world-overview.mbtiles'}
    hashes={n:hashlib.sha256(p.read_bytes()).hexdigest() for n,p in files.items()}
    payload=io.BytesIO()
    with tarfile.open(fileobj=payload,mode='w') as archive:
        for n,p in files.items():archive.add(p,arcname=n)
    p=subprocess.run(SSH+['python3 -c '+shlex.quote(SOURCE.replace('HASHES',repr(hashes)))],input=payload.getvalue(),capture_output=True,timeout=150)
    if p.returncode:raise RuntimeError(p.stderr.decode(errors='replace')[-6000:])
    data=json.loads(p.stdout);target=ROOT/'evidence/etherlocation-install.json';first=ROOT/'evidence/etherlocation-defaults-install.json'
    if target.exists() and not first.exists():first.write_bytes(target.read_bytes())
    target.write_text(json.dumps(data,indent=2)+'\n',encoding='utf-8')
    print(json.dumps(dict(state=data['state'],region=data['region'],servicesUnchanged=data['before']==data['after']),indent=2))
