"""GM1920 IPA preflight/staging; runtime initialization is separately opt-in.

Default is read-only. --stage copies hash-verified firmware from this phone's
vendor_b into its Linux root filesystem. --initialize additionally performs the
exact vendor /dev/ipa startup write ONCE per boot. Confirm the shared IPA/Wi-Fi
runtime risk with the user before an agent executes --initialize.
No partition is opened for writing. No radio enable, service reset or reboot.
"""
from pathlib import Path
import argparse
import json
import runpy
import shlex
import subprocess

ROOT=Path(__file__).resolve().parent.parent
SSH=runpy.run_path(str(ROOT/'scripts/deploy-ethermobile.py'))['SSH']
REMOTE=r'''
import hashlib,json,os,pathlib,platform,subprocess
expected=EXPECTED
stage=STAGE
initialize=INITIALIZE
def sha(data):return hashlib.sha256(data).hexdigest()
def read(path):return pathlib.Path(path).read_text().strip()
def probe():
 return {'interfaces':sorted(p.name for p in pathlib.Path('/sys/class/net').glob('*')),
 'services':subprocess.run(['systemctl','is-active','NetworkManager','ssh','bluetooth','etherpocket-modem'],capture_output=True,text=True).stdout,
 'subsystems':{read(p/'name'):read(p/'state') for p in pathlib.Path('/sys/bus/msm_subsys/devices').glob('*')}}
assert os.geteuid()==0
assert platform.release()=='4.14.117-perf'
assert read('/etc/etherpocket/disk-identity')=='GM1920-548cb338-mobian-sda21'
assert pathlib.Path('/proc/device-tree/model').read_bytes().rstrip(b'\0')==b'SDX50M MTP 18827 15'
assert pathlib.Path('/dev/ipa').is_char_device()
before=probe()
assert before['subsystems'].get('modem')=='ONLINE'
assert before['services'].splitlines()==['active']*4
source='/dev/disk/by-partlabel/vendor_b'
rule=subprocess.run(['debugfs','-R','cat /etc/init/ipa_fws.rc',source],capture_output=True,check=True,timeout=15).stdout
assert sha(rule)=='2c0ef77a59bc7409806c1a53b76ff770effeab2304893597309efd1d18dad610'
payloads={}
for path,meta in expected.items():
 data=subprocess.run(['debugfs','-R','cat '+path,source],capture_output=True,check=True,timeout=15).stdout
 assert len(data)==meta['bytes'] and sha(data)==meta['sha256'], 'Vendor firmware hash mismatch'
 payloads[pathlib.Path(path).name]=data
prepared=[]
for name,data in payloads.items():
 target=pathlib.Path('/lib/firmware')/name
 if target.is_symlink():raise RuntimeError('Refusing a firmware symlink')
 if target.exists():
  assert sha(target.read_bytes())==sha(data), 'Refusing to overwrite different firmware'
 elif stage:
  fd=os.open(target,os.O_WRONLY|os.O_CREAT|os.O_EXCL|os.O_NOFOLLOW,0o644)
  with os.fdopen(fd,'wb') as f:f.write(data)
  prepared.append(name)
 if initialize:assert target.exists() and sha(target.read_bytes())==sha(data)
result={'mode':'initialize' if initialize else 'stage' if stage else 'preflight',
        'source':source,'before':before,'firmware_manifest':expected,'staged_files':prepared,
        'startup_rule_sha256':sha(rule),'runtime_write_performed':False}
if initialize:
 assert not any(n.startswith(('rmnet','wwan','mhi')) for n in before['interfaces']), 'Packet path already exists; inspect before another startup'
 assert before['subsystems'].get('ipa_fws')=='OFFLINING', 'Unexpected IPA state; inspect first'
 marker=os.open('/run/ethermobile-ipa-attempted',os.O_WRONLY|os.O_CREAT|os.O_EXCL,0o600)
 os.close(marker)
 fd=os.open('/dev/ipa',os.O_WRONLY|os.O_NOFOLLOW)
 try:assert os.write(fd,b'1')==1
 finally:os.close(fd)
 result['runtime_write_performed']=True
result['after']=probe()
print(json.dumps(result,indent=2))
'''

if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--stage',action='store_true',help='Install only these verified device firmware files into Linux')
    parser.add_argument('--initialize',action='store_true',help='Explicit shared-subsystem startup test; confirmation required before agent execution')
    args=parser.parse_args()
    manifest=json.loads((ROOT/'evidence/ethermobile-vendor-2026-10-18.json').read_text(encoding='utf-8'))['firmware']
    script=REMOTE.replace('EXPECTED',repr(manifest)).replace('STAGE',repr(args.stage)).replace('INITIALIZE',repr(args.initialize))
    r=subprocess.run(SSH+['python3 -c '+shlex.quote(script)],capture_output=True,check=True,timeout=120)
    report=json.loads(r.stdout)
    target=ROOT/('evidence/ethermobile-ipa-'+report['mode']+'-2026-10-18.json')
    target.write_text(json.dumps(report,indent=2)+'\n',encoding='utf-8')
    print(target)
    print('Verified firmware files:',len(manifest))
    print('Newly staged:',len(report['staged_files']))
    print('Runtime write performed:',report['runtime_write_performed'])
