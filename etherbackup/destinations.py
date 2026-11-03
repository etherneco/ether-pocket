"""Precommissioned local, USB, mounted NAS and pinned SFTP repositories."""
import json
import os
from pathlib import Path
import re
import shlex
import shutil
import subprocess
from security import BackupError, credential, identifier

def usb_candidates():
    result=subprocess.run(['lsblk','-J','-b','-o','NAME,PATH,TRAN,UUID,FSTYPE,MOUNTPOINTS,SIZE'],capture_output=True,text=True,timeout=10,check=True)
    candidates=[]
    def walk(node,external=False):
        external=external or node.get('tran')=='usb'
        if external and node.get('uuid') and node.get('fstype'):
            candidates.append(dict(device=node['path'],uuid=node['uuid'],filesystem=node['fstype'],
                                   mounts=[p for p in node.get('mountpoints',[]) if p],size=node['size']))
        for child in node.get('children',[]):walk(child,external)
    for node in json.loads(result.stdout)['blockdevices']:walk(node)
    return candidates

def usb_configuration(name,mount):
    identifier(name);mount=str(Path(mount))
    if mount=='/' or '..' in Path(mount).parts or not Path(mount).is_absolute() or any(p.is_symlink() for p in [Path(mount),*Path(mount).parents]):
        raise BackupError('An absolute mounted USB directory without symlink ancestors is required')
    candidate=next((c for c in usb_candidates() if mount in c['mounts']),None)
    if not candidate or not os.path.ismount(mount):raise BackupError('No mounted USB filesystem at this path; use existing storage tools to mount it first')
    return dict(kind='usb',mount=mount,uuid=candidate['uuid'],repository=mount+'/etherpocket-restic-'+name,
                passwordFile='/etc/etherbackup/credentials/'+name+'-password',independentKeyConfirmed=False)

def inspect(config, reserve=64*1024**2):
    kind=config.get('kind');repo=config.get('repository','')
    credential(config['passwordFile'])
    if kind=='sftp':
        # A protected SSH config holds key/known-host paths, never supplied by UI.
        if not re.fullmatch(r'sftp:[a-zA-Z0-9_-]+:/[a-zA-Z0-9_./-]+',repo) or '..' in repo.split('/'):
            raise BackupError('SFTP requires a commissioned SSH alias and absolute path')
        from security import protected
        for key in ('sshConfig','knownHosts','sshKey'):
            p=Path(config[key]);s=p.lstat()
            if p.is_symlink() or s.st_uid!=0 or s.st_mode&0o022 or not p.is_file():raise BackupError('Untrusted SSH configuration')
            for parent in p.parents:
                st=parent.lstat()
                if parent.is_symlink() or st.st_uid!=0 or st.st_mode&0o022:raise BackupError('Untrusted SSH configuration directory')
        if Path(config['sshKey']).stat().st_mode&0o077:raise BackupError('SSH key permissions invalid')
        command=['ssh','-F',config['sshConfig'],'-i',config['sshKey'],'-o','IdentitiesOnly=yes','-o','BatchMode=yes',
                 '-o','StrictHostKeyChecking=yes','-o','UserKnownHostsFile='+config['knownHosts'],
                 '-o','GlobalKnownHostsFile=/dev/null','-o','ConnectTimeout=10',
                 '-o','ServerAliveInterval=15','-o','ServerAliveCountMax=3']
        host=repo.split(':')[1]
        command += [host,'-s','sftp']
        return dict(independent=True,independenceVerified=bool(config.get('independentRecoveryTested')),freeBytes=None,options=['-o','sftp.command='+shlex.join(command)])
    if kind not in ('local','usb','nas') or not repo.startswith('/') or '..' in Path(repo).parts:
        raise BackupError('Unsupported destination')
    p=Path(repo)
    if any(x.is_symlink() for x in [p,*p.parents]):raise BackupError('Destination symlinks refused')
    parent=p if p.exists() else p.parent
    if not parent.is_dir():raise BackupError('Destination unavailable')
    # Prevent a missing external mount silently falling back to the root disk.
    mount=config.get('mount')
    if kind in ('usb','nas'):
        if not mount or mount=='/' or not os.path.ismount(mount) or not p.is_relative_to(Path(mount)) or p==Path(mount):
            raise BackupError('Expected external mount unavailable')
        result=subprocess.run(['findmnt','-J','-T',mount,'-o','TARGET,SOURCE,FSTYPE,UUID'],capture_output=True,text=True,timeout=10,check=True)
        fs=json.loads(result.stdout)['filesystems'][0]
        if fs['target']!=mount or (kind=='usb' and (not config.get('uuid') or fs.get('uuid')!=config['uuid'])):
            raise BackupError('External filesystem identity differs')
        if kind=='nas' and fs['fstype'] not in ('nfs','nfs4','cifs','smb3'):raise BackupError('Expected NAS filesystem unavailable')
        if kind=='usb':
            topology=subprocess.run(['lsblk','-s','-J','-o','NAME,TRAN',fs['source']],capture_output=True,text=True,timeout=10,check=True)
            def usb(node):return node.get('tran')=='usb' or any(usb(c) for c in node.get('children',[]))
            if not any(usb(node) for node in json.loads(topology.stdout)['blockdevices']):raise BackupError('Mounted filesystem is not verified USB storage')
    free=shutil.disk_usage(parent).free
    if free<reserve:raise BackupError('Destination storage running low')
    # All internal UFS LUNs belong to one handset; only commissioned USB UUID
    # or a mounted network filesystem can establish independent storage here.
    independent=kind in ('usb','nas')
    return dict(independent=independent,independenceVerified=independent,freeBytes=free,options=[])
