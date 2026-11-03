"""Install the device owner's narrowly scoped Wi-Fi radio policy, then verify
off/on through the running EtherShell. USB SSH stays available throughout.
The initial radio state is restored even if verification fails.
"""
from pathlib import Path
import json
import runpy
import shlex
import subprocess

ROOT = Path(__file__).resolve().parent.parent
SSH = runpy.run_path(str(ROOT / 'scripts/deploy-ethermobile.py'))['SSH']

SOURCE = r'''import hashlib,json,pathlib,socket,subprocess,sys,time
assert pathlib.Path('/etc/etherpocket/disk-identity').read_text().strip()=='GM1920-548cb338-mobian-sda21'
rule=sys.stdin.buffer.read()
target=pathlib.Path('/etc/polkit-1/rules.d/49-etherpocket-wifi.rules')
if target.exists() and target.read_bytes()!=rule:
 raise RuntimeError('Existing Wi-Fi policy differs; inspect before replacing')
temporary=target.with_suffix('.new');temporary.write_bytes(rule);temporary.chmod(0o644);temporary.replace(target)
time.sleep(2) # polkit watches and reloads rules automatically
pids=subprocess.check_output(['pgrep','-u','1000','-x','ethershell'],text=True).split()
assert len(pids)==1
proc=pathlib.Path('/proc')/pids[0]
env=dict(i.split('=',1) for i in (proc/'environ').read_bytes().decode().split('\0') if '=' in i)
endpoint='/run/user/1000/ethershell-control-experience-'+env['DISPLAY'].replace(':','').replace('.','-')
def radio():
 return subprocess.check_output(['nmcli','-t','-f','WIFI','general'],text=True).strip()
def control(value):
 with socket.socket(socket.AF_UNIX,socket.SOCK_STREAM) as client:
  client.settimeout(5);client.connect(endpoint)
  client.sendall(json.dumps({'command':'control','action':'wifi','value':value}).encode()+b'\n')
  assert client.recv(8192).strip()==b'ok'
def wait(value):
 for _ in range(60):
  if radio()==value:return
  time.sleep(.25)
 raise RuntimeError('Wi-Fi did not become '+value)
def permissions():
 out=subprocess.check_output(['runuser','-u','mobian','--','nmcli','-t','general','permissions'],text=True)
 return dict(line.rsplit(':',1) for line in out.strip().splitlines())
initial=radio();assert initial in ('enabled','disabled')
result={'policy':str(target),'sha256':hashlib.sha256(rule).hexdigest(),'shell_pid':int(pids[0]),'initial':initial,'permissions':permissions()}
assert result['permissions']['org.freedesktop.NetworkManager.enable-disable-wifi']=='yes'
assert result['permissions']['org.freedesktop.NetworkManager.enable-disable-wwan']=='no'
try:
 control('off');wait('disabled')
 for _ in range(60):
  devices=subprocess.check_output(['nmcli','-t','-f','DEVICE,TYPE,STATE','device'],text=True)
  if 'wlan0:wifi:connected' not in devices:break
  time.sleep(.25)
 else:raise RuntimeError('wlan0 stayed connected after radio off')
 result['off']={'radio':radio(),'wlan0_connected':False,'rfkill':subprocess.check_output(['rfkill','list','wifi'],text=True)}
 control('on');wait('enabled');result['on']={'radio':radio()}
finally:
 control('on' if initial=='enabled' else 'off');wait(initial)
if initial=='enabled':
 for _ in range(120):
  if 'wlan0:wifi:connected' in subprocess.check_output(['nmcli','-t','-f','DEVICE,TYPE,STATE','device'],text=True):break
  time.sleep(.25)
 else:raise RuntimeError('Radio restored but Wi-Fi did not reconnect')
result['final']=radio()
result['services']={s:subprocess.check_output(['systemctl','is-active',s],text=True).strip() for s in ['NetworkManager','ssh','bluetooth']}
print(json.dumps(result,indent=2))
'''

if __name__ == '__main__':
    result = subprocess.run(
        SSH + ['python3 -c ' + shlex.quote(SOURCE)],
        input=(ROOT / 'config/49-etherpocket-wifi.rules').read_bytes(),
        capture_output=True, timeout=100,
    )
    if result.returncode:
        raise RuntimeError(result.stderr.decode('utf-8', errors='replace'))
    evidence = json.loads(result.stdout)
    (ROOT / 'evidence/wifi-radio-fix-2026-10-19.json').write_text(
        json.dumps(evidence, indent=2) + '\n', encoding='utf-8')
    print(json.dumps(evidence, indent=2))
