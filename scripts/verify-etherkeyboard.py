"""Test automatic EtherKeyboard on the handset in a private X11 session."""
from pathlib import Path
import io
import json
import runpy
import tarfile

ROOT = Path(__file__).resolve().parent.parent
remote = runpy.run_path(str(ROOT / 'scripts/verify-etherupdate-device.py'))['remote']

if __name__ == '__main__':
    payload = io.BytesIO()
    with tarfile.open(fileobj=payload, mode='w') as archive:
        archive.add(ROOT / 'build/ethershell-keyboard-arm64', arcname='ethershell')
        archive.add(ROOT / 'scripts/test-ethershell-mobile-ui.py', arcname='qa.py')
    source = r'''
import hashlib,io,json,os,pathlib,subprocess,sys,tarfile,tempfile
assert pathlib.Path('/etc/etherpocket/disk-identity').read_text().strip()=='GM1920-548cb338-mobian-sda21'
pid=subprocess.check_output(['pgrep','-u','1000','-x','ethershell'],text=True).strip()
previous=str((pathlib.Path('/proc')/pid/'exe').resolve().parents[2])
folder=pathlib.Path(tempfile.mkdtemp(prefix='etherkeyboard-qa-',dir='/var/tmp'))
with tarfile.open(fileobj=io.BytesIO(sys.stdin.buffer.read())) as archive:archive.extractall(folder,filter='data')
(folder/'ethershell').chmod(0o755)
(folder/'inputs').mkdir()
for path in [folder,*folder.rglob('*')]:os.chown(path,1000,1000)
runs={}
for name,size,extra in [('hotplug','360x900x24',['ETHERSHELL_KEYBOARD_UI_ONLY=1','ETHERSHELL_TEST_INPUT_ROOT='+str(folder/'inputs')]),('settings','480x1000x24',[])]:
    output=folder/name
    with (folder/(name+'-runner.log')).open('wb') as log:
        result=subprocess.run(['runuser','-u','mobian','--','env',*extra,'python3',str(folder/'qa.py'),'--binary',str(folder/'ethershell'),'--output',str(output),'--suite','settings','--size',size],stdout=log,stderr=log,timeout=110)
    results=output/'results.json'
    runs[name]={'exit':result.returncode,'results':json.loads(results.read_text()) if results.exists() else {},'sessionTail':(output/'session.log').read_text(errors='replace')[-3000:]}
print(json.dumps({'path':str(folder),'previous':previous,'sha256':hashlib.sha256((folder/'ethershell').read_bytes()).hexdigest(),'runs':runs}))
'''
    data = json.loads(remote(source, payload.getvalue(), timeout=180))
    (ROOT / 'evidence/etherkeyboard-qa.json').write_text(json.dumps(data, indent=2) + '\n', encoding='utf-8')
    for name, run in data['runs'].items():
        print(name, 'exit:', run['exit'], 'checks:', len(run['results']),
              'failures:', [key for key, value in run['results'].items() if not value])
    assert all(run['exit'] == 0 and run['results'] and all(run['results'].values()) for run in data['runs'].values())
