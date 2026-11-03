"""Managed API identity. X11/same-UID processes are not a sandbox boundary."""
import hashlib
import os
from pathlib import Path
import re
import subprocess
from core import Rejected

def protected(path):
    path=Path(path)
    if not path.is_absolute():return False
    for part in (path,*path.parents):
        s=part.stat()
        if s.st_uid!=0 or s.st_mode&0o022:return False
    return True

def application(pid):
    path=Path('/proc')/str(int(pid));exe=str((path/'exe').resolve(strict=True))
    args=(path/'cmdline').read_bytes().split(b'\0')
    script=args[1].decode(errors='replace') if len(args)>1 else ''
    if exe.startswith('/usr/bin/python') and script=='/usr/share/ethermap/backend.py' and protected(script):return 'ethermap'
    if exe=='/usr/bin/ethermap' and protected(exe):return 'ethermap'
    if exe.startswith('/usr/bin/python') and script in ('/usr/share/ethercamera/service.py','/usr/share/etherlocation/service.py') and protected(script):
        return 'ethercamera' if '/ethercamera/' in script else 'etherlocation'
    if re.fullmatch(r'/opt/ethershell2/[a-zA-Z0-9.-]+/usr/bin/ethershell',exe) and protected(exe):return 'ethershell'
    if exe in ('/usr/bin/ethercamera-app','/usr/bin/etherlocation-map','/usr/bin/ethershell') and protected(exe):
        return {'/usr/bin/ethercamera-app':'ethercamera','/usr/bin/etherlocation-map':'etherlocation','/usr/bin/ethershell':'ethershell'}[exe]
    # Never grant all interpreted applications a shared Python/shell identity.
    interpreter=Path(exe).name.startswith(('python','bash','dash','sh','node','perl','ruby'))
    key=exe
    if interpreter:
        if script.startswith('/') and protected(script):key+=':'+str(Path(script).resolve())
        else:key+=':session-process:'+str(pid)
    return 'process:'+hashlib.sha256(key.encode()).hexdigest()[:24]

def caller(bus,sender):
    if not sender or not sender.startswith(':') or bus.get_unix_user(sender)!=os.getuid():raise Rejected('Wrong session user')
    pid=int(bus.call_blocking('org.freedesktop.DBus','/org/freedesktop/DBus','org.freedesktop.DBus','GetConnectionUnixProcessID','s',(sender,),timeout=2))
    return pid,application(pid)

def foreground(app):
    try:
        r=subprocess.run(['xprop','-root','_NET_ACTIVE_WINDOW'],capture_output=True,text=True,timeout=1)
        window=re.search(r'0x[0-9a-fA-F]+',r.stdout)
        if not window:return False
        r=subprocess.run(['xprop','-id',window[0],'_NET_WM_PID'],capture_output=True,text=True,timeout=1)
        pid=re.search(r'=\s*(\d+)',r.stdout)
        return bool(pid and application(int(pid[1]))==app)
    except (OSError,subprocess.TimeoutExpired,ValueError):return False
