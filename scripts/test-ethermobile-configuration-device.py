"""Real ARM64 NM persistence, read-back, secrets, conflict and rollback acceptance.
No data activation, radio mutation, service restart or Wi-Fi profile modification.
"""
from pathlib import Path
import hashlib
import json
import runpy
import shlex
import subprocess
import uuid
ROOT=Path(__file__).resolve().parent.parent
SSH=runpy.run_path(str(ROOT/'scripts/deploy-ethermobile.py'))['SSH']
if __name__=='__main__':
    payload=(ROOT/'build/ethermobile-configuration-test-arm64').read_bytes()
    fixture='EtherMobile configuration-'+uuid.uuid4().hex
    source='''import hashlib,json,os,pathlib,subprocess,sys,tempfile
payload=sys.stdin.buffer.read();assert hashlib.sha256(payload).hexdigest()==DIGEST
fixture=FIXTURE
def state():return hashlib.sha256(subprocess.run(['nmcli','-t','-f','UUID,TYPE,DEVICE','connection','show','--active'],capture_output=True,check=True).stdout).hexdigest()
before=state();results={}
with tempfile.TemporaryDirectory(prefix='ethermobile-config-',dir='/run') as folder:
 os.chmod(folder,0o755);binary=pathlib.Path(folder)/'test';binary.write_bytes(payload);binary.chmod(0o755)
 try:
  for admin in [False,True]:
   args=(['env','LANG=C.UTF-8'] if admin else ['runuser','-u','mobian','--','env','LANG=C.UTF-8','ETHERMOBILE_EXPECT_AUTH_FAILURE=1'])+['ETHERMOBILE_FIXTURE_ID='+fixture,str(binary)]
   p=subprocess.run(args,capture_output=True,text=True,timeout=100)
   results['administrator' if admin else 'unprivileged']={'exit':p.returncode,'stdout':p.stdout,'stderr':p.stderr}
 finally:
  for name in [fixture,fixture+' copy']:subprocess.run(['nmcli','connection','delete','id',name],capture_output=True)
results['active_connections_unchanged']=before==state()
print(json.dumps(results,indent=2))
'''.replace('DIGEST',repr(hashlib.sha256(payload).hexdigest())).replace('fixture=FIXTURE','fixture='+repr(fixture))
    r=subprocess.run(SSH+['python3 -c '+shlex.quote(source)],input=payload,capture_output=True,check=True,timeout=240)
    results=json.loads(r.stdout)
    (ROOT/'evidence/ethermobile-configuration-2026-10-18.json').write_text(json.dumps(results,indent=2)+'\n',encoding='utf-8')
    print(json.dumps(results,indent=2))
    assert results['administrator']['exit']==0 and results['unprivileged']['exit']==0 and results['active_connections_unchanged']
