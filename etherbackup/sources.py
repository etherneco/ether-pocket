"""Explicit source contracts and bounded, symlink-free consistent staging."""
import hashlib
import json
import os
from pathlib import Path
import shutil
import sqlite3
import stat
import subprocess
import sys
import time
from contextlib import closing
from security import BackupError, atomic, open_source, relative

SQLITE_EXPORT=r'''
import os,sqlite3,sys,tempfile,time
from pathlib import Path
source=Path(sys.argv[1]);start=time.monotonic()
def progress(*args):
 if time.monotonic()-start>60:raise RuntimeError('Database export timed out')
with tempfile.TemporaryDirectory(prefix='etherbackup-sqlite-') as folder:
 with sqlite3.connect(source.as_uri()+'?mode=ro',uri=True,timeout=10) as src, sqlite3.connect(folder+'/export.sqlite') as dst:
  src.execute('PRAGMA trusted_schema=OFF');dst.execute('PRAGMA trusted_schema=OFF')
  src.backup(dst,pages=256,progress=progress,sleep=.05)
  if dst.execute('PRAGMA integrity_check').fetchall()!=[('ok',)]:raise RuntimeError('Database integrity failed')
 with open(folder+'/export.sqlite','rb') as f:
  import shutil
  shutil.copyfileobj(f,sys.stdout.buffer)
'''

def digest(path):
    h=hashlib.sha256()
    with open(path,'rb') as f:
        for block in iter(lambda:f.read(1024**2),b''):h.update(block)
    return h.hexdigest()

def validate_database(path):
    with open(path,'rb') as f:header=f.read(16)
    if header!=b'SQLite format 3\0':return False
    start=time.monotonic()
    with closing(sqlite3.connect(Path(path).as_uri()+'?mode=ro',uri=True,timeout=5)) as db:
        db.execute('PRAGMA trusted_schema=OFF')
        db.set_progress_handler(lambda:int(time.monotonic()-start>30),10000)
        if db.execute('PRAGMA integrity_check').fetchall()!=[('ok',)]:raise BackupError('Restored database integrity failed')
    return True

def database_metadata(path):
    with closing(sqlite3.connect(Path(path).as_uri()+'?mode=ro',uri=True,timeout=5)) as db:
        db.execute('PRAGMA trusted_schema=OFF')
        schema=db.execute('SELECT type,name,tbl_name,sql FROM sqlite_schema ORDER BY type,name').fetchall()
        return dict(userVersion=db.execute('PRAGMA user_version').fetchone()[0],
                    schemaSha256=hashlib.sha256(json.dumps(schema).encode()).hexdigest(),
                    automaticMigrationOrDowngradeAllowed=False)

class SourceRegistry:
    def __init__(self,config):self.config=config
    def contracts(self,profile,components=None):
        if profile not in self.config['profiles']:raise BackupError('Unknown backup profile')
        names=self.config['profiles'][profile]
        if components is not None:
            mapping=self.config.get('updateComponents',{})
            if not components or any(c not in mapping for c in components):raise BackupError('Update component backup contract not commissioned')
            names=list(dict.fromkeys(n for c in components for n in mapping[c]))
        contracts=[]
        for name in names:
            c=self.config['sources'][name]
            if c.get('consistency') not in ('files-and-sqlite-online','static-files'):raise BackupError('Application consistency contract unsupported')
            if not c.get('schemaVersions') or c.get('secrets')!='explicit-paths-only':raise BackupError('Incomplete application contract')
            contracts.append(dict(c,id=name))
        return contracts

    def stage(self,profile,stage,components=None,guard=lambda:None):
        stage=Path(stage);tree=stage/'files';tree.mkdir(mode=0o700)
        files={};missing=[];skipped=[];total=0;started=time.monotonic()
        max_bytes=self.config.get('maxStageBytes',16*1024**3);max_files=self.config.get('maxFiles',100000)
        seen=set()
        reserved=[Path(p) for p in ('/dev','/proc','/sys','/run','/var/lib/etherbackup','/etc/etherbackup')]
        reserved.append(stage.parent)
        for destination in self.config.get('destinations',{}).values():
            for field in ('passwordFile','sshKey'):
                if destination.get(field):reserved.append(Path(destination[field]))
            if destination.get('repository','').startswith('/'):reserved.append(Path(destination['repository']))
        def copy(path,contract):
            nonlocal total
            if time.monotonic()-started>3600:raise BackupError('Source staging timed out')
            guard()
            path=Path(path);name=path.as_posix().lstrip('/')
            if any(path==p or path.is_relative_to(p) for p in reserved):return
            if name in seen:return
            seen.add(name)
            if any(path==Path(p) or path.is_relative_to(Path(p)) for p in contract.get('exclude',[])):return
            if path.name.endswith(('-wal','-shm','-journal')):return
            try:fd=open_source(path)
            except FileNotFoundError:missing.append(str(path));return
            except OSError:raise BackupError('A source is inaccessible or became a symlink') from None
            try:
                info=os.fstat(fd)
                if stat.S_ISDIR(info.st_mode):
                    # Each child is opened through an independently checked dirfd walk.
                    for entry in sorted(os.listdir(fd)):
                        child=path/entry
                        if stat.S_ISLNK(os.stat(entry,dir_fd=fd,follow_symlinks=False).st_mode):
                            skipped.append(str(child));continue
                        copy(child,contract)
                    return
                if not stat.S_ISREG(info.st_mode):skipped.append(str(path));return
                if len(files)>=max_files or total+info.st_size>max_bytes:raise BackupError('Source staging limit exceeded')
                if shutil.disk_usage(stage).free<info.st_size+64*1024**2:raise BackupError('Insufficient staging space')
                target=tree.joinpath(*relative(name).parts);target.parent.mkdir(parents=True,exist_ok=True,mode=0o700)
                with os.fdopen(os.dup(fd),'rb') as src, target.open('xb') as dst:
                    header=src.read(16);src.seek(0)
                    is_db=header==b'SQLite format 3\0'
                    if is_db:
                        kwargs={}
                        # A user-controlled database path is never opened by SQLite as root.
                        if os.geteuid()==0:
                            owner=info.st_uid;group=info.st_gid
                            # Root-owned files inside mutable user directories still
                            # have a user-controlled SQLite pathname/WAL namespace.
                            if owner==0:
                                for parent in path.parents:
                                    parent_info=parent.stat()
                                    if parent_info.st_uid!=0:
                                        owner=parent_info.st_uid;group=parent_info.st_gid;break
                                    if parent_info.st_mode&0o022:
                                        owner=self.config.get('sessionUid',1000);group=owner;break
                            if owner!=0:kwargs=dict(user=owner,group=group,extra_groups=[])
                        try:
                            p=subprocess.run([sys.executable,'-I','-c',SQLITE_EXPORT,str(path)],stdout=dst,stderr=subprocess.DEVNULL,timeout=90,**kwargs)
                            if p.returncode:raise BackupError('Consistent SQLite export failed')
                        except subprocess.TimeoutExpired:raise BackupError('Consistent SQLite export timed out') from None
                    else:
                        # Bound reads even if a file is concurrently appended forever.
                        remaining=info.st_size
                        while remaining:
                            block=src.read(min(1024**2,remaining))
                            if not block:raise BackupError('Source changed during staging; retry')
                            dst.write(block);remaining-=len(block)
                        after=os.fstat(fd)
                        if (info.st_size,info.st_mtime_ns,info.st_ctime_ns)!=(after.st_size,after.st_mtime_ns,after.st_ctime_ns):
                            raise BackupError('Source changed during staging; retry')
                    dst.flush();os.fsync(dst.fileno())
                total+=target.stat().st_size
                if total>max_bytes:raise BackupError('Source staging limit exceeded')
                target.chmod(stat.S_IMODE(info.st_mode)&0o777)
                os.utime(target,ns=(info.st_atime_ns,info.st_mtime_ns))
                files[name]=dict(sha256=digest(target),size=target.stat().st_size,mode=stat.S_IMODE(info.st_mode)&0o777,
                                 mtimeNs=info.st_mtime_ns,uid=info.st_uid,gid=info.st_gid,sqlite=is_db,contract=contract['id'])
                if is_db:files[name]['database']=database_metadata(target)
            finally:os.close(fd)
        contracts=self.contracts(profile,components)
        for contract in contracts:
            for path in contract['paths']:
                p=Path(path)
                if not p.is_absolute() or any(p==Path(x) or p.is_relative_to(Path(x)) for x in ('/dev','/proc','/sys','/run','/var/lib/etherbackup','/etc/etherbackup')):
                    raise BackupError('Forbidden backup source')
                copy(path,contract)
        if not files:raise BackupError('No configured data exists; no operational backup created')
        return dict(files=files,missing=missing,skippedSymlinks=skipped,bytes=total,
                    contracts=[{k:c.get(k) for k in ('id','schemaVersions','consistency','secrets','prepare','complete','restoreValidation')} for c in contracts])
