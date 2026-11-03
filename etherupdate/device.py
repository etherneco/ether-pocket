import os
from pathlib import Path
import platform
import shutil
from engine import run


def identity():
    release={}
    for line in Path('/etc/os-release').read_text().splitlines():
        if '=' in line:
            key,value=line.split('=',1);release[key]=value.strip('"')
    try:model=Path('/proc/device-tree/model').read_text().strip('\0\n')
    except OSError:model='Unknown'
    # Commission family explicitly; no hardware serial/IMEI/IMSI is collected.
    try:family=Path('/etc/etherupdate/device-family').read_text().strip()
    except OSError:family='uncommissioned'
    return dict(architecture='arm64' if platform.machine()=='aarch64' else platform.machine(),
                distribution=release.get('ID'),distribution_major=int(release.get('VERSION_ID','0').split('.')[0]),
                kernel_abi=platform.release(),device_family=family,model=model,
                availableStorage=shutil.disk_usage('/var/lib').free)


def token():
    from credentials import CredentialStore
    managed=CredentialStore().load()
    if managed is not None:return managed
    directory=os.environ.get('CREDENTIALS_DIRECTORY')
    path=Path(directory)/'autoupdate-token' if directory else Path('/etc/etherupdate/autoupdate-token')
    if not path.exists():return ''
    st=path.stat()
    if st.st_uid!=0 or st.st_mode & 0o077:raise ValueError('Update credential permissions are unsafe')
    value=path.read_text().strip()
    if '\n' in value or '\r' in value:raise ValueError('Invalid update credential')
    return value
