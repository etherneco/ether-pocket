"""Preview home in its own authenticated X11 display and private profile."""
from pathlib import Path
import json,runpy
ROOT=Path(__file__).resolve().parent.parent
remote=runpy.run_path(str(ROOT/'scripts/verify-etherupdate-device.py'))['remote']
data=json.loads((ROOT/'evidence/ui-polish/stage.json').read_text())
preview=r'''
import os,pathlib,secrets,signal,subprocess,sys,tempfile,time
with tempfile.TemporaryDirectory(prefix='etherpolish-preview-') as folder:
 root=pathlib.Path(folder);auth=root/'Xauthority';auth.touch(mode=0o600)
 subprocess.run(['xauth','-f',str(auth),'add',':939','MIT-MAGIC-COOKIE-1',secrets.token_hex(16)],check=True,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
 runtime=root/'runtime';runtime.mkdir(mode=0o700)
 env=dict(os.environ,DISPLAY=':939',XAUTHORITY=str(auth),XDG_RUNTIME_DIR=str(runtime),XDG_CONFIG_HOME=str(root/'config'),XDG_DATA_HOME=str(root/'data'),XDG_CACHE_HOME=str(root/'cache'),ETHERSHELL_CONFIG_DIR=str(root/'config/ethershell'),ETHERSHELL_NESTED_CONFIRMED='1',ETHERSHELL_DEVELOPMENT='1',LANG='C.UTF-8',GIO_USE_VFS='local',GVFS_DISABLE_FUSE='1')
 env.pop('DBUS_SESSION_BUS_ADDRESS',None);env.pop('SESSION_MANAGER',None)
 assert not pathlib.Path('/tmp/.X11-unix/X939').exists()
 with open(os.devnull,'wb') as log:
  server=subprocess.Popen(['Xvfb',':939','-screen','0','1440x3120x24','-nolisten','tcp','-auth',str(auth)],env=env,stdout=log,stderr=log)
  app=None
  try:
   for _ in range(40):
    if subprocess.run(['xdpyinfo'],env=env,stdout=log,stderr=log).returncode==0:break
    time.sleep(.1)
   app=subprocess.Popen(['dbus-run-session','--',BINARY,'--development','--safe-mode'],env=env,stdout=log,stderr=log,start_new_session=True)
   time.sleep(5);assert app.poll() is None
   image=root/'preview.png'
   subprocess.run(['ffmpeg','-v','error','-f','x11grab','-video_size','1440x3120','-i',':939','-frames:v','1','-update','1',str(image)],env=env,check=True,stdout=log,stderr=log,timeout=10)
   sys.stdout.buffer.write(image.read_bytes())
  finally:
   if app is not None:
    try:os.killpg(app.pid,signal.SIGTERM)
    except ProcessLookupError:pass
    app.wait(timeout=8)
   server.terminate();server.wait(timeout=5)
'''.replace('BINARY',repr(data['stage']+'/usr/bin/ethershell'))
code="import subprocess,sys;p=subprocess.run(['runuser','-u','mobian','--','python3','-'],input="+repr(preview.encode())+",capture_output=True,timeout=30);assert p.returncode==0,p.stderr;sys.stdout.buffer.write(p.stdout)"
(ROOT/'evidence/ui-polish/preview-final.png').write_bytes(remote(code,timeout=40))
print('Saved evidence/ui-polish/preview-final.png')
