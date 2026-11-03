"""Native map/UI acceptance on an isolated Debian session, never the phone bus.

The only fixture is an unlocked EtherLock response. No location data is injected.
The actual native UI/worker, real OSM dataset and SQLite renderer are exercised.
Run under dbus-run-session; HOME/XDG paths must point at the test directory.
"""
import json
import os
from pathlib import Path
import subprocess
import sys
import threading
import time
import dbus
import dbus.service
from dbus.mainloop.glib import DBusGMainLoop
from gi.repository import GLib

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'etherlocation'))
from maps import Maps
from core import atomic


class Lock(dbus.service.Object):
    def __init__(self,bus):
        self.name=dbus.service.BusName('com.etherneco.EtherLock1',bus)
        super().__init__(bus,'/com/etherneco/EtherLock1')
    @dbus.service.method('com.etherneco.EtherLock1',in_signature='',out_signature='s')
    def GetState(self):return json.dumps(dict(ready=True,locked=False,phase='unlocked'))


def main():
    DBusGMainLoop(set_as_default=True);bus=dbus.SessionBus();lock=Lock(bus);loop=GLib.MainLoop()
    root=Path.home()/'.local/share/ethermap'
    region=Maps(Path.home()/'.local/share/etherlocation/maps').import_file(ROOT/'build/ethermap-westminster-osm.mbtiles',True)
    atomic(root/'settings.json',dict(onlineTiles=False))
    output=ROOT/'evidence/ethermap-native';output.mkdir(parents=True,exist_ok=True)
    result=dict(fixture='isolated unlocked lock state only; no device positions injected',networkNamespace='No external network interfaces; unshare --net',dataset=region,views={})
    def run():
        env=dict(os.environ,DBUS_SYSTEM_BUS_ADDRESS=os.environ['DBUS_SESSION_BUS_ADDRESS'])
        service=subprocess.Popen(['/usr/bin/python3','/usr/share/etherlocation/service.py'],env=env,stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True)
        try:
            for _ in range(50):
                if bus.name_has_owner('com.etherneco.EtherLocation1'):break
                time.sleep(.1)
            if not bus.name_has_owner('com.etherneco.EtherLocation1'):raise RuntimeError('Isolated real EtherLocation failed to start')
            for name,size in [('portrait','420x820x24'),('narrow','360x780x24'),('landscape','900x540x24'),('settings','360x780x24'),('first-launch','420x820x24')]:
                file=output/(name+'.png')
                # Explicit physical dimensions avoid native-DPI surprises in screenshots.
                cmd=['xvfb-run','-a','-s','-screen 0 '+size,'env','LANG=C.UTF-8','LC_ALL=C.UTF-8','QT_QPA_PLATFORM=xcb','QT_QUICK_BACKEND=software','QT_SCALE_FACTOR=1','/usr/bin/ethermap','--size',size.rsplit('x',1)[0],'--smoke-test','--expect-offline','--screenshot',str(file)]+(['--settings'] if name=='settings' else [])
                env=dict(os.environ)
                if name=='first-launch':
                    fresh=Path.home()/('first-launch-'+str(os.getpid()));fresh.mkdir(mode=0o700)
                    env.update(HOME=str(fresh),XDG_CONFIG_HOME=str(fresh/'config'),XDG_CACHE_HOME=str(fresh/'cache'))
                p=subprocess.run(cmd,env=env,capture_output=True,text=True,timeout=25)
                result['views'][name]=dict(exit=p.returncode,stdout=p.stdout,stderr=p.stderr,screenshot=file.exists())
            p=subprocess.run(['xvfb-run','-a','-s','-screen 0 420x820x24','env','LANG=C.UTF-8','LC_ALL=C.UTF-8','QT_QPA_PLATFORM=xcb','QT_QUICK_BACKEND=software','QT_SCALE_FACTOR=1','/usr/bin/ethermap','--interaction-test'],capture_output=True,text=True,timeout=25)
            result['interactions']=dict(exit=p.returncode,stdout=p.stdout,stderr=p.stderr)
            (output/'result.json').write_text(json.dumps(result,indent=2)+'\n')
        finally:
            service.terminate()
            try:stdout,stderr=service.communicate(timeout=8)
            except subprocess.TimeoutExpired:service.kill();stdout,stderr=service.communicate()
            result['locationService']=dict(exit=service.returncode,stdout=stdout,stderr=stderr)
            (output/'result.json').write_text(json.dumps(result,indent=2)+'\n')
            GLib.idle_add(loop.quit)
    thread=threading.Thread(target=run);thread.start();loop.run();thread.join()
    print(json.dumps(result,indent=2))
    if result.get('locationService',{}).get('exit')!=0 or result.get('interactions',{}).get('exit')!=0 or not all(v['exit']==0 and v['screenshot'] and not v['stderr'].strip() for v in result['views'].values()):sys.exit(1)

if __name__=='__main__':main()
