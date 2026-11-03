"""Local policy and filesystem boundaries. No secrets in public errors."""
from contextlib import contextmanager
import fcntl
import json
import os
from pathlib import Path, PurePosixPath
import re
import stat
import tempfile

class BackupError(Exception):pass

def identifier(value):
    if not isinstance(value,str) or not re.fullmatch(r'[a-zA-Z0-9][a-zA-Z0-9_.-]{0,99}',value):
        raise BackupError('Invalid identifier')
    return value

def relative(value):
    if not isinstance(value,str) or not value or '\\' in value or '\0' in value:
        raise BackupError('Unsafe restore path')
    p=PurePosixPath(value)
    if p.is_absolute() or any(x in ('','..','.') for x in value.split('/')):
        raise BackupError('Unsafe restore path')
    return p

def private(path):
    path=Path(path)
    path.mkdir(parents=True,exist_ok=True,mode=0o700)
    info=path.lstat()
    if not stat.S_ISDIR(info.st_mode) or info.st_uid!=os.geteuid() or info.st_mode&0o077:
        raise BackupError('Private directory ownership or permissions invalid')
    return path

def atomic(path,data):
    path=Path(path);fd,name=tempfile.mkstemp(prefix='.new-',dir=path.parent)
    try:
        with os.fdopen(fd,'w',encoding='utf-8') as f:
            json.dump(data,f,allow_nan=False,sort_keys=True);f.flush();os.fsync(f.fileno())
        os.replace(name,path)
        directory=os.open(path.parent,os.O_RDONLY|os.O_DIRECTORY)
        try:os.fsync(directory)
        finally:os.close(directory)
    finally:
        if os.path.exists(name):os.unlink(name)

def protected(path):
    path=Path(path)
    for p in [path,*path.parents]:
        s=p.lstat()
        if stat.S_ISLNK(s.st_mode) or s.st_uid!=0 or s.st_mode&0o022:
            raise BackupError('Policy must be root-owned and not writable by others')
    with path.open(encoding='utf-8') as f:return json.load(f)

def credential(path):
    path=Path(path)
    for p in [path,*path.parents]:
        s=p.lstat()
        if stat.S_ISLNK(s.st_mode) or s.st_uid!=os.geteuid() or s.st_mode&0o022:
            raise BackupError('Credential ownership invalid')
    s=path.stat()
    if not stat.S_ISREG(s.st_mode) or s.st_mode&0o077 or not 16<=s.st_size<=4096:
        raise BackupError('Credential must be a private regular file (16–4096 bytes)')
    return str(path)

@contextmanager
def lock(path):
    fd=os.open(path,os.O_CREAT|os.O_RDWR|os.O_NOFOLLOW,0o600)
    try:
        try:fcntl.flock(fd,fcntl.LOCK_EX|fcntl.LOCK_NB)
        except BlockingIOError:raise BackupError('Another backup or restore job is running') from None
        yield
    finally:os.close(fd)

def open_source(path,directory=False):
    """Walk every ancestor with dirfds: user-controlled symlinks never get followed."""
    p=Path(path)
    if not p.is_absolute() or '..' in p.parts:raise BackupError('Source must be absolute')
    fd=os.open('/',os.O_RDONLY|os.O_DIRECTORY)
    try:
        for index,part in enumerate(p.parts[1:]):
            flags=os.O_RDONLY|os.O_NOFOLLOW|os.O_NONBLOCK
            if index<len(p.parts)-2 or directory:flags|=os.O_DIRECTORY
            child=os.open(part,flags,dir_fd=fd);os.close(fd);fd=child
        result=fd;fd=-1;return result
    finally:
        if fd>=0:os.close(fd)
