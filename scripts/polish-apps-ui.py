"""Stage and render the Files, SMS and Maps UI revisions in private profiles."""
from pathlib import Path
import hashlib,io,json,runpy,tarfile
ROOT=Path(__file__).resolve().parent.parent
remote=runpy.run_path(str(ROOT/'scripts/verify-etherupdate-device.py'))['remote']
if __name__=='__main__':
 payload=io.BytesIO()
 with tarfile.open(fileobj=payload,mode='w') as tar:
  for app in ['etherfiles','ethersms','ethermap']:tar.add(ROOT/('build/'+app+'-ui-polish-arm64'),arcname=app)
 code=r'''
import hashlib,io,json,os,pathlib,subprocess,sys,tarfile
data=sys.stdin.buffer.read();folder=pathlib.Path('/opt/etherpocket-ui')/hashlib.sha256(data).hexdigest()[:12]
assert pathlib.Path('/etc/etherpocket/disk-identity').read_text().strip()=='GM1920-548cb338-mobian-sda21'
folder.mkdir(parents=True,exist_ok=True)
with tarfile.open(fileobj=io.BytesIO(data),mode='r:') as tar:tar.extractall(folder,filter='data')
out=pathlib.Path('/var/tmp')/('ui-apps-'+folder.name);out.mkdir(exist_ok=True);os.chown(out,1000,1000)
results={}
fixture=out/'lockfixture.py'
fixture.write_text("""import dbus,dbus.service,subprocess,sys
from dbus.mainloop.glib import DBusGMainLoop
from gi.repository import GLib
DBusGMainLoop(set_as_default=True)
class Lock(dbus.service.Object):
 @dbus.service.method('com.etherneco.EtherLock1',in_signature='',out_signature='s')
 def GetState(self):return '{"ready":true,"locked":false,"phase":"unlocked"}'
bus=dbus.SessionBus();name=dbus.service.BusName('com.etherneco.EtherLock1',bus);lock=Lock(bus,'/com/etherneco/EtherLock1')
p=subprocess.Popen(sys.argv[1:]);loop=GLib.MainLoop()
def check():
 if p.poll() is not None:loop.quit();return False
 return True
GLib.timeout_add(100,check);loop.run();sys.exit(p.returncode)
""")
for app,args in [('etherfiles',['--pocket','--screenshot']),('ethersms',['--capture']),('ethermap',['--smoke-test','--screenshot'])]:
 binary=folder/app;binary.chmod(0o755)
 home=out/app;home.mkdir(exist_ok=True);os.chown(home,1000,1000)
 runtime=home/'runtime';runtime.mkdir(mode=0o700,exist_ok=True);os.chown(runtime,1000,1000)
 image=out/(app+'.png')
 env=['HOME='+str(home),'XDG_CONFIG_HOME='+str(home/'config'),'XDG_DATA_HOME='+str(home/'data'),'XDG_CACHE_HOME='+str(home/'cache'),'XDG_RUNTIME_DIR='+str(runtime),'GIO_USE_VFS=local','GVFS_DISABLE_FUSE=1','QT_QPA_PLATFORM=offscreen','QT_QUICK_BACKEND=software','LANG=C.UTF-8']
 command=(['python3',str(fixture)] if app=='ethermap' else [])+[str(binary)]+args+[str(image)]
 p=subprocess.run(['runuser','-u','mobian','--','env']+env+['dbus-run-session','--']+command,capture_output=True,text=True,timeout=30)
 results[app]={'exit':p.returncode,'log':p.stdout+p.stderr,'binary_sha256':hashlib.sha256(binary.read_bytes()).hexdigest()}
(out/'results.json').write_text(json.dumps({'stage':str(folder),'apps':results},indent=2))
with tarfile.open(fileobj=sys.stdout.buffer,mode='w|gz') as tar:
 for p in out.iterdir():
  if p.is_file():tar.add(p,arcname=p.name)
'''
 result=remote(code,payload.getvalue(),timeout=100)
 out=ROOT/'evidence/ui-polish/apps';out.mkdir(parents=True,exist_ok=True)
 with tarfile.open(fileobj=io.BytesIO(result),mode='r:gz') as tar:tar.extractall(out,filter='data')
 results=json.loads((out/'results.json').read_text())
 print(json.dumps(results,indent=2))
 assert all(v['exit']==0 for v in results['apps'].values())
