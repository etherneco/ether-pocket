"""Install only the three visually checked executables, preserving rollback copies."""
from pathlib import Path
import json,runpy
ROOT=Path(__file__).resolve().parent.parent
remote=runpy.run_path(str(ROOT/'scripts/verify-etherupdate-device.py'))['remote']
data=json.loads((ROOT/'evidence/ui-polish/apps/results.json').read_text())
assert all(app['exit']==0 for app in data['apps'].values())
code=r'''
import hashlib,json,pathlib,shutil,os
data=DATA;stage=pathlib.Path(data['stage'])
assert stage.parent==pathlib.Path('/opt/etherpocket-ui')
assert pathlib.Path('/etc/etherpocket/disk-identity').read_text().strip()=='GM1920-548cb338-mobian-sda21'
backup=pathlib.Path('/var/backups/etherpocket-ui')/stage.name;backup.mkdir(parents=True,exist_ok=False)
targets=[]
for app,qa in data['apps'].items():
 source=stage/app;target=pathlib.Path('/usr/bin')/app
 assert hashlib.sha256(source.read_bytes()).hexdigest()==qa['binary_sha256']
 assert source.stat().st_uid==0 and not source.stat().st_mode&0o022
 assert target.is_file() and not target.is_symlink()
 shutil.copy2(target,backup/app);targets.append((source,target,backup/app))
desktop=pathlib.Path('/usr/share/applications/ethercamera-media.desktop')
assert desktop.is_file() and not desktop.is_symlink()
shutil.copy2(desktop,backup/desktop.name)
changed=[]
try:
 for source,target,original in targets:
  temporary=target.with_name(target.name+'.ui-new');assert not temporary.exists()
  shutil.copy2(source,temporary);temporary.chmod(0o755);os.replace(temporary,target);changed.append((target,original))
 desktop.write_text(desktop.read_text().replace('Icon=camera-photo','Icon=image-x-generic'))
except BaseException:
 for target,original in changed:
  temporary=target.with_name(target.name+'.ui-rollback');shutil.copy2(original,temporary);os.replace(temporary,target)
 shutil.copy2(backup/desktop.name,desktop);raise
print(json.dumps({'backup':str(backup),'stage':str(stage),'installed':{t.name:hashlib.sha256(t.read_bytes()).hexdigest() for s,t,b in targets},'gallery_icon':True}))
'''.replace('DATA',repr(data))
result=json.loads(remote(code,timeout=30))
(ROOT/'evidence/ui-polish/apps/deployment.json').write_text(json.dumps(result,indent=2)+'\n')
print(json.dumps(result,indent=2))
