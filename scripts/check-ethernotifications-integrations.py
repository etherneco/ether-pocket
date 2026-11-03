"""Regression tests against private buses/stores; no real modem/audio operations."""
from pathlib import Path
import io,json,runpy,tarfile
ROOT=Path(__file__).resolve().parent.parent
remote=runpy.run_path(str(ROOT/'scripts/check-etherphone-device.py'))['remote']
if __name__=='__main__':
    payload=io.BytesIO()
    with tarfile.open(fileobj=payload,mode='w:gz') as tar:
        for name in ('etheraudio','etherphone'):
            for p in (ROOT/name).rglob('*.py'):
                if '__pycache__' not in p.parts:tar.add(p,arcname=name+'/'+p.relative_to(ROOT/name).as_posix())
        tar.add(ROOT/'build/ethersms-notifications-test',arcname='ethersms-test')
    source=r'''
import io,json,os,pathlib,subprocess,sys,tarfile,tempfile
folder=pathlib.Path(tempfile.mkdtemp(prefix='ethernotifications-regression-',dir='/var/tmp'))
with tarfile.open(fileobj=io.BytesIO(sys.stdin.buffer.read()),mode='r:gz') as tar:tar.extractall(folder,filter='data')
(folder/'ethersms-test').chmod(0o755)
runtime=folder/'runtime';runtime.mkdir(mode=0o700)
for p in [folder]+list(folder.rglob('*')):os.chown(p,1000,1000)
user=['runuser','-u','mobian','--','env','XDG_RUNTIME_DIR='+str(runtime),'QT_QPA_PLATFORM=offscreen','XDG_DATA_HOME='+str(folder/'data'),'XDG_CONFIG_HOME='+str(folder/'config'),'ETHERCONTACTS_DATABASE='+str(folder/'contacts.sqlite')]
tests={}
for name,args in [('phone-core',['python3','-m','unittest','discover','-s',str(folder/'etherphone/tests'),'-v']),('phone-protocol',['dbus-run-session','--','python3',str(folder/'etherphone/tests/service_fixture.py')]),('audio-core',['python3','-m','unittest','discover','-s',str(folder/'etheraudio/tests'),'-v']),('audio-protocol',['dbus-run-session','--','sh','-c','export DBUS_SYSTEM_BUS_ADDRESS="$DBUS_SESSION_BUS_ADDRESS"; exec python3 '+str(folder/'etheraudio/tests/service_fixture.py')]),('sms-core',['dbus-run-session','--',str(folder/'ethersms-test')])]:
 p=subprocess.run(user+args,capture_output=True,text=True,timeout=65);tests[name]={'exit':p.returncode,'out':p.stdout,'error':p.stderr}
print(json.dumps({'stage':str(folder),'tests':tests},indent=2))
'''
    result=json.loads(remote(source,payload.getvalue(),timeout=170))
    (ROOT/'evidence/ethernotifications-integration-tests.json').write_text(json.dumps(result,indent=2),encoding='utf-8')
    print(json.dumps({k:v['exit'] for k,v in result['tests'].items()}))
    if any(v['exit'] for v in result['tests'].values()):print(json.dumps(result,indent=2))
    assert all(v['exit']==0 for v in result['tests'].values())
