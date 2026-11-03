"""Resolve a same-UID graphical process for the adopted-shell auth agent.

Polkit accepts process/bus-name subjects for CheckAuthorization. A unix-session
subject is for agent registration and is not used for authorization checks.
"""
from pathlib import Path
import re
from security import BackupError

def graphical_process(uid,scope,cgroups=Path('/sys/fs/cgroup'),proc=Path('/proc')):
    if uid<=0 or not re.fullmatch(r'session-[A-Za-z0-9]+\.scope',str(scope)):
        raise BackupError('Invalid graphical session identity')
    group=cgroups/'user.slice'/('user-'+str(uid)+'.slice')/str(scope)
    try:candidates=sorted(int(v) for v in (group/'cgroup.procs').read_text().split())
    except (OSError,ValueError):raise BackupError('Graphical session processes unavailable') from None
    for pid in candidates:
        path=proc/str(pid)
        try:
            if path.stat().st_uid!=uid:continue
            start=int((path/'stat').read_text().rsplit(')',1)[1].split()[19])
            # The kernel cgroup membership and UID must still agree after reading.
            if path.stat().st_uid!=uid or '/'+str(scope) not in (path/'cgroup').read_text().splitlines()[0]:continue
            return dict(pid=pid,start=start,uid=uid)
        except (OSError,ValueError,IndexError):continue
    raise BackupError('No matching graphical user process; use the independent administrator CLI')
