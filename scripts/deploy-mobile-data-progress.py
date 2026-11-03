"""Stage the corrected IPA controls and diagnostics; activate after UI QA."""
from pathlib import Path
import argparse
import hashlib
import io
import json
import runpy
import shlex
import subprocess
import tarfile

ROOT=Path(__file__).resolve().parent.parent
SSH=runpy.run_path(str(ROOT/'scripts/deploy-ethermobile.py'))['SSH']
REPORT=ROOT/'evidence/mobile-data-progress-stage.json'


def remote(source,payload=None,timeout=90):
    result=subprocess.run(SSH+['python3 -c '+shlex.quote(source)],input=payload,capture_output=True,timeout=timeout)
    if result.returncode:raise RuntimeError(result.stderr.decode(errors='replace')[-6000:])
    return result.stdout


def stage():
    files={
        'shell':ROOT/'build/ethershell-mobile-data-arm64',
        'mobile':ROOT/'build/ethermobile-data-ui-arm64',
        'probe':ROOT/'build/ethermobile-data-probe-arm64',
        'ui-test.py':ROOT/'scripts/test-ethershell-mobile-ui.py',
        'ethermobile-data-wait.py':ROOT/'scripts/ethermobile-data-wait.py',
        'ethermobile-ipa-data.py':ROOT/'scripts/ethermobile-ipa-data.py',
        'ethermobile_data_status.py':ROOT/'scripts/ethermobile_data_status.py',
        'ethermobile-data.service':ROOT/'config/ethermobile-data.service',
        '49-ethermobile-data.rules':ROOT/'config/49-ethermobile-data.rules',
    }
    payload=io.BytesIO()
    with tarfile.open(fileobj=payload,mode='w:gz') as archive:
        for name,path in files.items():archive.add(path,arcname=name)
    digest=hashlib.sha256(files['shell'].read_bytes()).hexdigest()
    source=r'''
import dbus,hashlib,importlib.util,io,json,os,pathlib,shutil,subprocess,sys,tarfile,tempfile,time
P=pathlib.Path
assert P('/etc/etherpocket/disk-identity').read_text().strip()=='GM1920-548cb338-mobian-sda21'
pids=subprocess.check_output(['pgrep','-u','1000','-x','ethershell'],text=True).split();assert len(pids)==1
old=(P('/proc')/pids[0]/'exe').resolve().parent.parent.parent
stage=P('/opt/ethershell2/2.1.0-data-progress-'+DIGEST[:12])
backup=P('/root/ethermobile-data-progress-'+str(time.time_ns()));backup.mkdir(mode=0o700)
with tempfile.TemporaryDirectory() as folder:
    folder=P(folder)
    with tarfile.open(fileobj=io.BytesIO(sys.stdin.buffer.read()),mode='r:gz') as archive:archive.extractall(folder,filter='data')
    assert hashlib.sha256((folder/'shell').read_bytes()).hexdigest()==DIGEST
    if not stage.exists():shutil.copytree(old,stage,symlinks=True)
    shutil.copy2(folder/'shell',stage/'usr/bin/ethershell');(stage/'usr/bin/ethershell').chmod(0o755)
    for name in ['mobile','probe','ui-test.py']:shutil.copy2(folder/name,stage/name);(stage/name).chmod(0o755)
    for name in ['ethermobile-data-wait.py','ethermobile-ipa-data.py','ethermobile_data_status.py','ethermobile-data.service','49-ethermobile-data.rules']:
        target=P('/etc/systemd/system')/name if name.endswith('.service') else P('/etc/polkit-1/rules.d')/name if name.endswith('.rules') else P('/usr/local/lib/ethermobile')/name
        assert not target.is_symlink()
        if target.exists():
            saved=backup/str(target).lstrip('/');saved.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(target,saved)
        temporary=target.with_suffix('.new');assert not temporary.is_symlink()
        shutil.copyfile(folder/name,temporary);temporary.chmod(0o644);temporary.replace(target)
# Preserve complete keyfiles privately, then stop NM's incompatible auto attempts
# only for the configured IPA APN. IPA's own boot service remains enabled.
saved=backup/'system-connections';shutil.copytree('/etc/NetworkManager/system-connections',saved)
bus=dbus.SystemBus();settings=dbus.Interface(bus.get_object('org.freedesktop.NetworkManager','/org/freedesktop/NetworkManager/Settings'),'org.freedesktop.NetworkManager.Settings')
migrated=0
for path in settings.ListConnections():
    p=dbus.Interface(bus.get_object('org.freedesktop.NetworkManager',path),'org.freedesktop.NetworkManager.Settings.Connection').GetSettings()
    if str(p.get('connection',{}).get('type'))=='gsm' and str(p.get('gsm',{}).get('apn','')).lower()=='giffgaff.com' and bool(p['connection'].get('autoconnect',True)):
        subprocess.run(['nmcli','connection','modify','uuid',str(p['connection']['uuid']),'connection.autoconnect','no'],check=True,capture_output=True);migrated+=1
subprocess.run(['systemctl','daemon-reload'],check=True)
subprocess.run(['systemd-analyze','verify','/etc/systemd/system/ethermobile-data.service'],check=True,capture_output=True)
sys.path.insert(0,'/usr/local/lib/ethermobile');import ethermobile_data_status as status
state=P('/run/ethermobile-data.json')
if state.exists() and subprocess.run(['systemctl','is-active','--quiet','ethermobile-data']).returncode==0:
    live=json.loads(state.read_text())
    status.update('connected','Połączenie IPA już aktywne. Adres IP i DNS są gotowe.',state='connected',reset=True,apn='giffgaff.com',**{k:live[k] for k in ['interface','address','gateway','dns','pid']})
print(json.dumps({'stage':str(stage),'previous':str(old),'backup':str(backup),'sha256':DIGEST,'migrated_nm_autoconnect':migrated}))
'''.replace('DIGEST',repr(digest))
    report=json.loads(remote(source,payload.getvalue()))
    if REPORT.exists():
        previous=json.loads(REPORT.read_text())
        (ROOT/('evidence/mobile-data-progress-stage-'+previous['sha256'][:12]+'.json')).write_bytes(REPORT.read_bytes())
    REPORT.write_text(json.dumps(report,indent=2)+'\n');print(json.dumps(report,indent=2))


def activate():
    report=json.loads(REPORT.read_text())
    qa=json.loads((ROOT/'evidence/mobile-data-progress-final-qa.json').read_text())
    assert qa and all(v['exit']==0 for v in qa.values()),'UI acceptance must pass before activation'
    source=r'''
import hashlib,json,os,pathlib,shutil,socket,subprocess,time
P=pathlib.Path;stage=P(STAGE);old=P(OLD)
assert hashlib.sha256((stage/'usr/bin/ethershell').read_bytes()).hexdigest()==DIGEST
pids=subprocess.check_output(['pgrep','-u','1000','-x','ethershell'],text=True).split();assert len(pids)==1
proc=P('/proc')/pids[0];assert (proc/'exe').resolve()==old/'usr/bin/ethershell'
env=dict(v.split('=',1) for v in (proc/'environ').read_bytes().decode().split('\0') if '=' in v)
launcher=P('/home/mobian/.local/bin/ethershell2-start');original=launcher.read_bytes()
backup=launcher.with_name('ethershell2-start.before-data-progress-'+DIGEST[:12]);backup.write_bytes(original);backup.chmod(0o755);os.chown(backup,1000,1000)
def run(action,directory,environment):
    command=['/usr/sbin/runuser','-u','mobian','--','/usr/bin/python3',str(directory/'usr/share/ethershell/current_session.py'),action]
    if action=='stop':subprocess.run(command,env=environment,check=True,capture_output=True,timeout=20)
    else:
        log=open('/var/tmp/ethershell-data-progress.log','ab');subprocess.Popen(command,env=environment,stdin=subprocess.DEVNULL,stdout=log,stderr=log,start_new_session=True)
newenv=dict(env,PATH=str(stage/'usr/bin')+':'+env.get('PATH','/usr/bin:/bin'),ETHERSHELL_PROFILE_DEFAULT=str(stage/'usr/share/ethershell/profiles.json'))
try:
    run('stop',old,env)
    launcher.write_bytes(original.replace(str(old).encode(),str(stage).encode()));launcher.chmod(0o755);os.chown(launcher,1000,1000)
    run('start',stage,newenv);time.sleep(6)
    pids=subprocess.check_output(['pgrep','-u','1000','-x','ethershell'],text=True).split();assert len(pids)==1 and (P('/proc')/pids[0]/'exe').resolve()==stage/'usr/bin/ethershell'
except BaseException:
    launcher.write_bytes(original);run('stop',stage,newenv);run('start',old,env);raise
target=P('/usr/bin/ethermobile');saved=P(BACKUP)/'ethermobile';shutil.copy2(target,saved)
temporary=target.with_suffix('.new');shutil.copy2(stage/'mobile',temporary);temporary.chmod(0o755);temporary.replace(target)
endpoint='/run/user/1000/ethershell-control-experience-'+env['DISPLAY'].replace(':','').replace('.','-')
with socket.socket(socket.AF_UNIX,socket.SOCK_STREAM) as client:
    client.settimeout(10);client.connect(endpoint);client.sendall(b'{"command":"settings-page","route":"mobile"}\n');assert client.recv(8192).strip()==b'ok'
print(json.dumps({'stage':str(stage),'pid':pids[0],'launcher_backup':str(backup)}))
'''.replace('STAGE',repr(report['stage'])).replace('OLD',repr(report['previous'])).replace('DIGEST',repr(report['sha256'])).replace('BACKUP',repr(report['backup']))
    deployed=json.loads(remote(source,timeout=60))
    (ROOT/'evidence/mobile-data-progress-deployment.json').write_text(json.dumps(deployed,indent=2)+'\n');print(json.dumps(deployed,indent=2))


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('action',choices=['stage','activate']);args=parser.parse_args()
    stage() if args.action=='stage' else activate()
