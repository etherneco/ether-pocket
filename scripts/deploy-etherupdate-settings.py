"""Provision the locally built agent and stage the tested token settings UI.

This is initial local provisioning over pinned SSH, not a release from the API.
No access token, project mapping or signing key is installed by this script.
"""
from pathlib import Path
import hashlib,io,json,runpy,tarfile
ROOT=Path(__file__).resolve().parent.parent
remote=runpy.run_path(str(ROOT/'scripts/verify-etherupdate-device.py'))['remote']

if __name__=='__main__':
    files={n:ROOT/'build'/n for n in ['etherupdate_0.1.0_arm64.deb','ethershell_2.1.0_etherupdate_arm64.deb']}
    hashes={n:hashlib.sha256(p.read_bytes()).hexdigest() for n,p in files.items()}
    qa=json.loads((ROOT/'evidence/etherupdate-ui-package.json').read_text())
    assert qa['passed'] and qa['package_sha256']==hashes['ethershell_2.1.0_etherupdate_arm64.deb']
    payload=io.BytesIO()
    with tarfile.open(fileobj=payload,mode='w') as tar:
        for name,path in files.items():tar.add(path,arcname=name)
    source=r'''
import hashlib,io,json,os,pathlib,shutil,subprocess,sys,tarfile,tempfile,time
assert pathlib.Path('/etc/etherpocket/disk-identity').read_text().strip()=='GM1920-548cb338-mobian-sda21'
def run(args,timeout=40):return subprocess.run(args,capture_output=True,text=True,timeout=timeout,check=True)
def probe():return run(['systemctl','show','ssh','NetworkManager','etherpower','etherhardware','ModemManager','-p','MainPID','-p','ActiveState']).stdout
before=probe()
pids=run(['pgrep','-u','1000','-x','ethershell']).stdout.split();assert len(pids)==1
old=(pathlib.Path('/proc')/pids[0]/'exe').resolve().parent.parent.parent
assert old.parent==pathlib.Path('/opt/ethershell2')
stage=old.parent/('2.1.0-update-token-'+HASHES['ethershell_2.1.0_etherupdate_arm64.deb'][:12])
assert stage!=old and not stage.exists()
with tempfile.TemporaryDirectory(prefix='etherupdate-provision-',dir='/var/tmp') as folder:
 folder=pathlib.Path(folder)
 with tarfile.open(fileobj=io.BytesIO(sys.stdin.buffer.read()),mode='r:') as archive:
  for member in archive:
   assert member.name in HASHES and member.isfile()
   data=archive.extractfile(member).read();assert hashlib.sha256(data).hexdigest()==HASHES[member.name]
   (folder/member.name).write_bytes(data)
 package=folder/'etherupdate_0.1.0_arm64.deb'
 run(['dpkg','--dry-run','-i',str(package)])
 run(['dpkg','-i',str(package)])
 run(['systemctl','daemon-reload'])
 run(['systemctl','enable','--now','etherupdate'])
 for i in range(30):
  p=run(['etherupdate','state']);state=json.loads(p.stdout)
  if state.get('ready'):break
  time.sleep(.2)
 assert state.get('ready') and not state.get('credentialConfigured') and not state.get('installed'), 'Agent must start with no credentials or commissioned updates'
 # Exercise real Unix-FD D-Bus transfer and live rejection with synthetic input.
 code="import dbus,os,json; from dbus.types import UnixFd; r,w=os.pipe();os.write(w,b'synthetic_test_value_1234567890');os.close(w); api=dbus.Interface(dbus.SystemBus().get_object('com.etherneco.EtherUpdate1','/com/etherneco/EtherUpdate1'),'com.etherneco.EtherUpdate1');\ntry:\n api.SetCredential(UnixFd(r),timeout=90);raise AssertionError('Invalid token accepted')\nexcept dbus.DBusException as e:\n assert 'Token validation failed' in str(e);print(json.dumps({'invalidTokenRejected':True}))\nfinally:os.close(r)"
 validation=json.loads(run(['python3','-c',code],110).stdout)
 state=json.loads(run(['etherupdate','state']).stdout);assert not state['credentialConfigured']
 assert not pathlib.Path('/var/lib/etherupdate/credentials/autoupdate-token').exists()
 shutil.copytree(old,stage,symlinks=True)
 run(['dpkg-deb','-x',str(folder/'ethershell_2.1.0_etherupdate_arm64.deb'),str(stage)])
 # Root ownership and non-writable binaries protect the newly staged executable.
 assert (stage/'usr/bin/ethershell').stat().st_uid==0 and not (stage/'usr/bin/ethershell').stat().st_mode & 0o022
after=probe();assert before==after
print(json.dumps(dict(stage=str(stage),previous=str(old),package_sha256=HASHES['ethershell_2.1.0_etherupdate_arm64.deb'],
 binary_sha256=hashlib.sha256((stage/'usr/bin/ethershell').read_bytes()).hexdigest(),qa_passed=True,agentReady=state['ready'],credentialConfigured=state['credentialConfigured'],validation=validation,servicesUnchanged=before==after)))
'''.replace('HASHES',repr(hashes))
    result=json.loads(remote(source,payload.getvalue(),timeout=180))
    (ROOT/'evidence/etherupdate-token-stage.json').write_text(json.dumps(result,indent=2)+'\n',encoding='utf-8')
    print(json.dumps(result,indent=2))
