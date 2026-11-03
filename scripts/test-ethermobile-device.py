"""Physical ARM64 acceptance, no radio changes or cellular activation.

The real NM lifecycle test stores then removes a reserved .invalid APN profile,
with autoconnect off and never-default on. This is configuration test data,
not a carrier APN or a simulated cellular connection.
"""
from pathlib import Path
import json
import runpy
import shlex
import subprocess
import uuid

ROOT=Path(__file__).resolve().parent.parent
SSH=runpy.run_path(str(ROOT/'scripts/deploy-ethermobile.py'))['SSH']

def remote(source,payload=None,timeout=120):
    return subprocess.run(SSH+['python3 -c '+shlex.quote(source)],input=payload,capture_output=True,check=True,timeout=timeout)

if __name__=='__main__':
    folder='/run/ethermobile-acceptance-'+uuid.uuid4().hex
    remote('import os;os.mkdir('+repr(folder)+',0o755)')
    try:
        for name in ['policy','profile']:
            payload=(ROOT/('build/ethermobile-'+name+'-test-arm64')).read_bytes()
            source='import os,sys;fd=os.open('+repr(folder+'/'+name)+',os.O_WRONLY|os.O_CREAT|os.O_EXCL,0o755);os.write(fd,sys.stdin.buffer.read());os.close(fd)'
            remote(source,payload)
        source='''import hashlib,json,subprocess
def state():
 return hashlib.sha256(subprocess.run(['nmcli','-t','-f','UUID,TYPE,DEVICE','connection','show','--active'],capture_output=True,check=True).stdout).hexdigest()
def run(args,admin=False):
 p=subprocess.run((['env','LANG=C.UTF-8'] if admin else ['runuser','-u','mobian','--','env','LANG=C.UTF-8'])+args,capture_output=True,text=True,timeout=100)
 return {'exit':p.returncode,'output':p.stdout,'stderr':p.stderr}
before=state()
tests={'policy':run([FOLDER+'/policy']),
       'profile-denied-without-agent':run(['ETHERMOBILE_EXPECT_AUTH_FAILURE=1',FOLDER+'/profile']),
       'profile-administrator-lifecycle':run([FOLDER+'/profile'],admin=True)}
print(json.dumps({'tests':tests,'active_connections_unchanged':before==state()},indent=2))
'''.replace('FOLDER',repr(folder))
        result=json.loads(remote(source,timeout=240).stdout)
        result['views']={}
        for name,args in [('pocket',['--compact']),('doctor',['--compact','--doctor']),('desktop-dark',['--external','--dark'])]:
            source='''import json,subprocess
p=subprocess.run(['runuser','-u','mobian','--','env','LANG=C.UTF-8','QT_QPA_PLATFORM=offscreen','QT_QUICK_BACKEND=software','ethermobile']+ARGS+['--smoke-test'],capture_output=True,text=True,timeout=30)
print(json.dumps({'exit':p.returncode,'output':p.stdout,'stderr':p.stderr}))
'''.replace('ARGS',repr(args))
            view=json.loads(remote(source).stdout)
            result['views'][name]=view
            if view['exit']==0:
                shot=subprocess.run(SSH+['cat /tmp/ethermobile-smoke-1000.png'],capture_output=True,check=True,timeout=15).stdout
                (ROOT/('evidence/ethermobile-'+name+'-device.png')).write_bytes(shot)
        (ROOT/'evidence/ethermobile-acceptance-2026-10-18.json').write_text(json.dumps(result,indent=2)+'\n',encoding='utf-8')
        print(json.dumps(result,indent=2))
        assert all(t['exit']==0 for t in result['tests'].values())
        assert all(t['exit']==0 and not t['stderr'] for t in result['views'].values())
        assert result['active_connections_unchanged']
    finally:
        remote('import pathlib;p=pathlib.Path('+repr(folder)+');[(p/n).unlink(missing_ok=True) for n in ["policy","profile"]];p.rmdir()')
