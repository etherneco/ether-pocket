"""Install and verify the diagnostic-only package on the pinned GM1920.

Does not enable the unit at boot, alter PAM, activate the sensor or restart UI.
"""
from pathlib import Path
import hashlib
import json
import runpy
import shlex
import subprocess

ROOT = Path(__file__).resolve().parent.parent
SSH = runpy.run_path(str(ROOT/'scripts/audit-etherfingerprint-device.py'))['SSH']
SOURCE = r'''
import hashlib,json,pathlib,subprocess,sys,tempfile
P=pathlib.Path
assert P('/etc/etherpocket/disk-identity').read_text().strip()=='GM1920-548cb338-mobian-sda21'
payload=sys.stdin.buffer.read()
assert hashlib.sha256(payload).hexdigest()==DIGEST
def run(args):
 p=subprocess.run(args,capture_output=True,text=True,timeout=30)
 return dict(code=p.returncode,stdout=p.stdout,stderr=p.stderr)
def probe():
 return dict(pam={str(p):hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted(P('/etc/pam.d').glob('*')) if p.is_file()},
  services=run(['systemctl','show','ssh','etherhardware','etherpower','etherupdate','NetworkManager','ModemManager','-p','Id','-p','MainPID','-p','ActiveState']),
  brightness={str(p):p.read_text().strip() for p in P('/sys/class/backlight').glob('*/brightness')})
out=dict(before=probe(),sha256=DIGEST)
with tempfile.TemporaryDirectory(prefix='etherfingerprint-',dir='/run') as folder:
 package=P(folder)/'etherfingerprint_0.1.0_arm64.deb';package.write_bytes(payload)
 for key,args in [('dryRun',['dpkg','--dry-run','--install',str(package)]),('install',['dpkg','--install',str(package)]),('start',['systemctl','start','etherfingerprintd'])]:
  out[key]=run(args)
  if out[key]['code']:raise RuntimeError(out[key])
out['status']=run(['systemctl','show','etherfingerprintd','-p','User','-p','ActiveState','-p','SubState','-p','MainPID','-p','DevicePolicy','-p','NoNewPrivileges'])
out['snapshot']=run(['/usr/bin/etherfingerprint'])
assert out['snapshot']['code']==0,out['snapshot']
state=json.loads(out['snapshot']['stdout'])
assert state['detected'] and state['vendor']=='Goodix' and state['driver']=='goodix_fp',state
assert not any(state[k] for k in ['operational','enabled','canEnroll','canVerify','canManage','illuminationSupported'])
out['unprivilegedRead']=run(['runuser','-u','mobian','--','/usr/bin/etherfingerprint'])
assert out['unprivilegedRead']['code']==0
out['unprivilegedMutation']=run(['runuser','-u','mobian','--','busctl','--system','call','com.etherneco.EtherFingerprint1','/com/etherneco/EtherFingerprint1','com.etherneco.EtherFingerprint1','Verify','s','{"match":true}'])
assert out['unprivilegedMutation']['code']!=0
out['after']=probe()
assert out['before']==out['after'],'Regression in service identity, PAM or brightness'
out['bootEnablement']=run(['systemctl','is-enabled','etherfingerprintd'])
print(json.dumps(out,indent=2))
'''

if __name__ == '__main__':
    payload = (ROOT/'build/etherfingerprint_0.1.0_arm64.deb').read_bytes()
    source = SOURCE.replace('DIGEST', repr(hashlib.sha256(payload).hexdigest()))
    p = subprocess.run(SSH+['python3 -c '+shlex.quote(source)], input=payload,
                       capture_output=True, timeout=180)
    if p.returncode:
        raise SystemExit(p.stderr.decode(errors='replace'))
    data = json.loads(p.stdout)
    target = ROOT/'evidence/etherfingerprint-device-verification.json'
    target.write_text(json.dumps(data, indent=2)+'\n', encoding='utf-8')
    print(target)
