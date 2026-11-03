"""Isolated tests on native ARM64; no package/service deployment or activation."""
from pathlib import Path
import io
import json
import runpy
import shlex
import subprocess
import tarfile
ROOT=Path(__file__).resolve().parent.parent
SSH=runpy.run_path(str(ROOT/'scripts/deploy-ethermobile.py'))['SSH']


def remote(source,payload=None,timeout=90):
    result=subprocess.run(SSH+['python3 -c '+shlex.quote(source)],input=payload,capture_output=True,timeout=timeout)
    if result.returncode:raise RuntimeError(result.stderr.decode(errors='replace')[-5000:])
    return result.stdout


if __name__=='__main__':
    payload=io.BytesIO()
    with tarfile.open(fileobj=payload,mode='w') as tar:
        for p in (ROOT/'etherupdate').rglob('*.py'):
            if '__pycache__' not in p.parts:tar.add(p,arcname=p.relative_to(ROOT).as_posix())
    source=r'''
import io,json,pathlib,subprocess,sys,tarfile,tempfile
assert pathlib.Path('/etc/etherpocket/disk-identity').read_text().strip()=='GM1920-548cb338-mobian-sda21'
def services():
 return subprocess.run(['systemctl','show','ssh','NetworkManager','etherpower','etherhardware','ModemManager','-p','MainPID','-p','ActiveState'],capture_output=True,text=True,check=True).stdout
before=services()
with tempfile.TemporaryDirectory(prefix='etherupdate-tests-',dir='/var/tmp') as folder:
 with tarfile.open(fileobj=io.BytesIO(sys.stdin.buffer.read()),mode='r:') as tar:tar.extractall(folder,filter='data')
 p=subprocess.run(['python3','-m','unittest','discover','-s',folder+'/etherupdate/tests','-v'],capture_output=True,text=True,timeout=60)
 data=dict(exit=p.returncode,log=p.stdout+p.stderr,before=before,after=services(),architecture=subprocess.check_output(['uname','-m'],text=True).strip())
 print(json.dumps(data))
'''
    result=json.loads(remote(source,payload.getvalue()))
    (ROOT/'evidence/etherupdate-device-tests.json').write_text(json.dumps(result,indent=2)+'\n',encoding='utf-8')
    print(json.dumps(result,indent=2));assert result['exit']==0 and result['before']==result['after']
