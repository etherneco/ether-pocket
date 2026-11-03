"""Test and deploy USB forwarding status without changing recovery addresses."""
from pathlib import Path
import base64
import json
import runpy
import shlex
import subprocess
import sys

ROOT = Path(__file__).resolve().parent.parent
SSH = runpy.run_path(str(ROOT/'scripts/deploy-ethermobile.py'))['SSH']
SOURCE = r'''
import base64,dbus,hashlib,json,pathlib,subprocess,tempfile,time
assert pathlib.Path('/etc/etherpocket/disk-identity').read_text().strip()=='GM1920-548cb338-mobian-sda21'
with tempfile.TemporaryDirectory(prefix='ethershare-usb-test-') as folder:
    root=pathlib.Path(folder)
    for name,payload in FILES.items():
        p=root/name;p.parent.mkdir(parents=True,exist_ok=True);p.write_bytes(base64.b64decode(payload))
    subprocess.run(['python3','-m','unittest','discover','-s',str(root/'tests'),'-p','test_ethershare.py'],check=True,stdout=__import__('sys').stderr)
    target=pathlib.Path('/usr/libexec/ethershare/core.py')
    assert hashlib.sha256(target.read_bytes()).hexdigest()=='b0dcff3871303d503f4377adc07570b44500d58e4b6c0e01a45a773b7ee1c383'
    api=dbus.Interface(dbus.SystemBus().get_object('com.etherneco.EtherShare1','/com/etherneco/EtherShare1'),'com.etherneco.EtherShare1')
    previous=json.loads(api.GetState())
    assert all(j['method']=='usb' for j in previous['active'])
    backup=target.with_name('core.py.before-usb-status-'+str(time.time_ns()))
    backup.write_bytes(target.read_bytes());backup.chmod(0o644)
    target.write_bytes((root/'ethershare/core.py').read_bytes())
    subprocess.run(['systemctl','restart','ethershare'],check=True)
    for _ in range(60):
        api=dbus.Interface(dbus.SystemBus().get_object('com.etherneco.EtherShare1','/com/etherneco/EtherShare1'),'com.etherneco.EtherShare1')
        state=json.loads(api.GetState())
        if state.get('ready') and not state.get('busy'):break
        time.sleep(.5)
    if previous['active'] and not state['active']:
        api.Start('usb','usb0',False,timeout=90)
    print(json.dumps({'backup':str(backup),'tests':18,'active':json.loads(api.GetState())['active']}))
'''


if __name__ == '__main__':
    files = {name: base64.b64encode((ROOT/name).read_bytes()).decode() for name in ['ethershare/core.py','tests/test_ethershare.py']}
    source = SOURCE.replace('FILES', repr(files))
    result = subprocess.run(SSH+['python3 -'],input=source.encode(),capture_output=True,timeout=150)
    sys.stderr.buffer.write(result.stderr)
    result.check_returncode()
    report = json.loads(result.stdout)
    (ROOT/'evidence/ethershare-usb-status-repair-2026-10-29.json').write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps(report,indent=2))
