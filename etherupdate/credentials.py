"""Root-only managed credentials. No secret appears in public state or errors."""
import os
from pathlib import Path
import re
import stat
import tempfile
from security import Rejected


def validate(value):
    if not isinstance(value,str) or not re.fullmatch(r'[A-Za-z0-9._~-]{20,4096}',value):
        raise Rejected('Enter only the API token, without a URL or whitespace')
    return value


def read_descriptor(fd):
    # Never let a caller stall the privileged worker by supplying an empty pipe.
    os.set_blocking(fd,False)
    try:
        value=os.read(fd,4097)
        if len(value)>4096:raise Rejected('Token is too long')
        return validate(value.decode('ascii'))
    except (BlockingIOError,UnicodeError,OSError):
        raise Rejected('Unable to read token from the secure input') from None


class CredentialStore:
    def __init__(self,directory='/var/lib/etherupdate/credentials'):
        self.directory=Path(directory);self.path=self.directory/'autoupdate-token'

    def secure_directory(self):
        self.directory.mkdir(parents=True,exist_ok=True,mode=0o700)
        for part in (self.directory,*self.directory.parents):
            s=part.lstat()
            if not stat.S_ISDIR(s.st_mode) or s.st_uid!=0 or s.st_mode & 0o022:
                raise Rejected('Credential storage permissions are unsafe')
        os.chmod(self.directory,0o700)

    def load(self):
        if not self.directory.exists():return None
        self.secure_directory()
        try:fd=os.open(self.path,os.O_RDONLY|os.O_NOFOLLOW|os.O_NONBLOCK)
        except FileNotFoundError:return None
        try:
            s=os.fstat(fd)
            if not stat.S_ISREG(s.st_mode) or s.st_uid!=0 or s.st_mode & 0o077:
                raise Rejected('Credential file permissions are unsafe')
            value=os.read(fd,4097).decode('ascii')
            # Empty content is an explicit disable override for LoadCredential.
            return validate(value) if value else ''
        finally:os.close(fd)

    def save(self,value):
        if value:validate(value)
        self.secure_directory()
        fd,name=tempfile.mkstemp(prefix='.token-',dir=self.directory)
        try:
            with os.fdopen(fd,'wb') as stream:
                stream.write(value.encode('ascii'));stream.flush();os.fsync(stream.fileno())
            os.replace(name,self.path)
            directory=os.open(self.directory,os.O_RDONLY|os.O_DIRECTORY)
            try:os.fsync(directory)
            finally:os.close(directory)
        finally:
            Path(name).unlink(missing_ok=True)
