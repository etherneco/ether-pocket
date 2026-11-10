"""Read-only device checks and capture of the formatted notification center."""
from pathlib import Path
import hashlib
import json
import subprocess
from importlib.util import module_from_spec, spec_from_file_location

ROOT = Path(__file__).resolve().parent.parent
spec = spec_from_file_location('readable_deploy', ROOT/'scripts/deploy-readable-data-ui.py')
deploy = module_from_spec(spec)
spec.loader.exec_module(deploy)
expected = {name: hashlib.sha256(path.read_bytes()).hexdigest() for name, path in {
    'ethershell': ROOT/'build/structured-ui/ethershell-arm64',
    'ethermap': ROOT/'build/structured-ui/ethermap-arm64',
    'etherbluetooth': ROOT/'build/structured-ui/etherbluetooth-arm64',
    'core': ROOT/'ethernotifications/core.py',
}.items()}
source = r'''
from pathlib import Path
import hashlib,json,socket,sqlite3,subprocess,sys,time
sys.path.insert(0,'/usr/share/ethernotifications')
from core import presentation
expected=EXPECTED
pid=subprocess.check_output(['pgrep','-u','1000','-x','ethershell'],text=True).strip()
proc=Path('/proc')/pid
binary=(proc/'exe').resolve()
paths={'ethershell':binary,'ethermap':Path('/usr/bin/ethermap'),'etherbluetooth':Path('/usr/bin/etherbluetooth'),'core':Path('/usr/share/ethernotifications/core.py')}
actual={k:hashlib.sha256(p.read_bytes()).hexdigest() for k,p in paths.items()}
assert actual==expected
env=dict(v.split('=',1) for v in (proc/'environ').read_bytes().decode().split('\0') if '=' in v)
endpoint='/run/user/1000/ethershell-control-experience-'+env['DISPLAY'].replace(':','').replace('.','-')
def request(data):
 with socket.socket(socket.AF_UNIX,socket.SOCK_STREAM) as s:
  s.settimeout(5);s.connect(endpoint);s.sendall(json.dumps(data).encode()+b'\n');return s.recv(16384).decode().strip()
state=json.loads(request({'command':'notification-state'}));assert state['ready'] and not state['locked'],state
notices=[]
with sqlite3.connect('file:/home/mobian/.local/state/ethernotifications/history.sqlite?mode=ro',uri=True) as db:
 for record, in db.execute('SELECT document FROM records'):
  row=json.loads(record)
  if row['appId']=='etherpower':
   title,body=presentation(row)
   assert '{' not in body and '"capacity"' not in body
   notices.append(dict(title=title,body=body))
assert notices
assert request({'page':'notices'})=='ok'
time.sleep(.7)
subprocess.run(['/usr/sbin/runuser','-u','mobian','--','env','DISPLAY='+env['DISPLAY'],'XAUTHORITY='+env.get('XAUTHORITY','/home/mobian/.Xauthority'),'scrot','-o','/var/tmp/readable-notifications.png'],check=True,timeout=10)
services={name:subprocess.check_output(['systemctl','is-active',name],text=True).strip() for name in ['ssh','NetworkManager','ModemManager','etherpower','etherhardware','bluetooth']}
print(json.dumps(dict(stage=str(binary.parent.parent.parent),hashes=actual,notifications=state,powerNotices=notices,services=services)))
'''.replace('EXPECTED', repr(expected))
result = subprocess.run(deploy.SSH+['python3 -'], input=source.encode('utf-8'),
                        capture_output=True, timeout=30)
if result.returncode:
    raise RuntimeError(result.stderr.decode(errors='replace'))
receipt = json.loads(result.stdout)
(ROOT/'evidence/readable-data-ui-verification.json').write_text(json.dumps(receipt, indent=2)+'\n', encoding='utf-8')
png = subprocess.run(deploy.SSH+['cat /var/tmp/readable-notifications.png'], capture_output=True, check=True, timeout=20).stdout
(ROOT/'evidence/readable-notifications.png').write_bytes(png)
print(json.dumps(receipt, indent=2))
