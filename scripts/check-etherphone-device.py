"""Stage and test on ARM64 without touching real radios or personal stores."""
from pathlib import Path
import io,json,runpy,shlex,subprocess,tarfile
ROOT=Path(__file__).resolve().parent.parent
SSH=runpy.run_path(str(ROOT/'scripts/deploy-ethermobile.py'))['SSH']
def remote(source,payload=None,timeout=90):
    p=subprocess.run(SSH+['python3 -c '+shlex.quote(source)],input=payload,capture_output=True,timeout=timeout)
    if p.returncode:raise RuntimeError(p.stderr.decode(errors='replace')[-10000:])
    return p.stdout
if __name__=='__main__':
    data=io.BytesIO()
    with tarfile.open(fileobj=data,mode='w:gz') as tar:
        for p in (ROOT/'etherphone').rglob('*'):
            if p.is_file() and '__pycache__' not in p.parts:tar.add(p,arcname='etherphone/'+str(p.relative_to(ROOT/'etherphone')).replace('\\','/'))
    source=r'''
import io,json,os,pathlib,subprocess,sys,tarfile,tempfile
assert pathlib.Path('/etc/etherpocket/disk-identity').read_text().strip()=='GM1920-548cb338-mobian-sda21'
folder=pathlib.Path(tempfile.mkdtemp(prefix='etherphone-qa-',dir='/var/tmp'))
with tarfile.open(fileobj=io.BytesIO(sys.stdin.buffer.read()),mode='r:gz') as tar:tar.extractall(folder,filter='data')
for p in [folder]+list(folder.rglob('*')):os.chown(p,1000,1000)
user=['runuser','-u','mobian','--','env','XDG_RUNTIME_DIR=/run/user/1000']
tests={}
for name,args in [('policy',['python3','-m','unittest','discover','-s',str(folder/'etherphone/tests'),'-v']),('protocol',['dbus-run-session','--','python3',str(folder/'etherphone/tests/service_fixture.py')])]:
 p=subprocess.run(user+args,capture_output=True,text=True,timeout=70)
 tests[name]={'exit':p.returncode,'out':p.stdout,'error':p.stderr}
print(json.dumps({'stage':str(folder),'tests':tests},indent=2))
'''
    result=json.loads(remote(source,data.getvalue(),timeout=100))
    (ROOT/'evidence/etherphone-arm64-tests.json').write_text(json.dumps(result,indent=2)+'\n',encoding='utf-8')
    print(json.dumps(result,indent=2));assert all(r['exit']==0 for r in result['tests'].values())
