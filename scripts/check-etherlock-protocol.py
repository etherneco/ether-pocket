"""ARM64 pure policy and real private-D-Bus acceptance, without live locking."""
from pathlib import Path
import hashlib
import io
import json
import runpy
import tarfile
ROOT=Path(__file__).resolve().parents[1]
remote=runpy.run_path(str(ROOT/'scripts/check-etherphone-device.py'))['remote']
if __name__=='__main__':
    names=['core.py','service.py','tests/service_fixture.py','tests/test_core.py']
    payload=io.BytesIO()
    with tarfile.open(fileobj=payload,mode='w:gz') as tar:
        for name in names:tar.add(ROOT/'etherlock'/name,arcname='etherlock/'+name)
    source=r'''
import io,json,os,pathlib,subprocess,sys,tarfile,tempfile
folder=pathlib.Path(tempfile.mkdtemp(prefix='etherlock-protocol-',dir='/var/tmp'))
with tarfile.open(fileobj=io.BytesIO(sys.stdin.buffer.read()),mode='r:gz') as tar:tar.extractall(folder,filter='data')
for p in [folder]+list(folder.rglob('*')):os.chown(p,1000,1000)
tests={}
for name,args in [('policy',['python3','-m','unittest','discover','-s',str(folder/'etherlock/tests'),'-p','test_*.py','-v']),('protocol',['dbus-run-session','--','python3',str(folder/'etherlock/tests/service_fixture.py')])]:
 p=subprocess.run(['runuser','-u','mobian','--','env','XDG_RUNTIME_DIR=/run/user/1000']+args,capture_output=True,text=True,timeout=30)
 tests[name]={'exit':p.returncode,'out':p.stdout,'error':p.stderr}
print(json.dumps(tests))
'''
    tests=json.loads(remote(source,payload.getvalue(),timeout=70))
    data={'sourceHashes':{name:hashlib.sha256((ROOT/'etherlock'/name).read_bytes()).hexdigest() for name in names},'tests':tests}
    (ROOT/'evidence/etherlock-protocol-tests.json').write_text(json.dumps(data,indent=2)+'\n',encoding='utf-8')
    print(json.dumps(data,indent=2));assert all(test['exit']==0 for test in tests.values())
