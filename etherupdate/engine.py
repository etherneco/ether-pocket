"""Installation strategies and recovery, controlled exclusively by local policy."""
import os
from pathlib import Path, PurePosixPath
import shutil
import subprocess
import tarfile
from security import Rejected, atomic, verify_file


def run(args, timeout=30):
    try:
        p=subprocess.run(args, capture_output=True, text=True, timeout=timeout,
                         env={'PATH':'/usr/sbin:/usr/bin:/sbin:/bin','LANG':'C.UTF-8','DEBIAN_FRONTEND':'noninteractive'})
    except (subprocess.TimeoutExpired, OSError):raise Rejected('Local validation command unavailable or timed out') from None
    if p.returncode:raise Rejected('Local validation failed: '+Path(args[0]).name)
    return p.stdout.strip()


def newer(candidate, installed):
    if not installed:return True
    # Debian versions include epochs and tilde prereleases; PHP version_compare
    # and string/float/SemVer comparison are not suitable for these artifacts.
    for value in (candidate,installed):
        run(['/usr/bin/dpkg','--validate-version',value])
    return subprocess.run(['/usr/bin/dpkg','--compare-versions',candidate,'gt',installed],capture_output=True).returncode==0


class InstallationEngine:
    def __init__(self, root='/opt/etherupdate-components', runner=run):
        self.root=Path(root);self.root.mkdir(parents=True,exist_ok=True)
        self.run=runner

    def component(self, manifest, policy):
        if manifest['package'] != policy['package'] or manifest['type'] != policy['type']:
            raise Rejected('Release does not match locally allowed package and strategy')
        if policy.get('critical',True):raise Rejected('Critical system updates require a dedicated recovery implementation')
        if manifest['package']=='etherupdate':raise Rejected('Self-update recovery is not commissioned')
        if not policy.get('health') or not all(isinstance(cmd,list) and cmd and str(cmd[0]).startswith('/') for cmd in policy['health']):
            raise Rejected('Meaningful local health validation must be configured')
        return self.root/manifest['package']

    def installed(self, policy):
        if policy['type']=='deb':
            try:return self.run(['/usr/bin/dpkg-query','-W','-f=${Version}',policy['package']])
            except Rejected:return ''
        link=self.root/policy['package']/'current'
        return link.resolve().name if link.is_symlink() else ''

    def preflight(self,path,manifest,policy):
        base=self.component(manifest,policy)
        verify_file(path,manifest)
        if not newer(manifest['version'],self.installed(policy)):raise Rejected('Downgrade or reinstall refused')
        for package,version in manifest.get('dependencies',{}).items():
            from security import identifier
            identifier(package)
            installed=self.run(['/usr/bin/dpkg-query','-W','-f=${Version}',package])
            if installed != version and not newer(installed,version):raise Rejected('Dependency not satisfied: '+package)
        if shutil.disk_usage(self.root).free < max(manifest['size']*3,64*1024**2):raise Rejected('Insufficient installation space')
        if manifest['type']=='deb':
            if not policy.get('manualRecoveryVerified'):raise Rejected('Debian rollback is unavailable; commission a manual recovery plan first')
            fields=self.run(['/usr/bin/dpkg-deb','-f',str(path),'Package','Version','Architecture']).splitlines()
            expected=[manifest['package'],manifest['version'],'arm64']
            # dpkg-deb prefixes field labels when several fields are requested.
            if [s.split(': ',1)[-1] for s in fields] != expected:raise Rejected('Debian control identity mismatch')
            simulation=self.run(['/usr/bin/apt-get','-s','--no-download','--no-remove','install',str(path)],120)
            for line in simulation.splitlines():
                if line.startswith(('Remv ','Inst ')) and (line.startswith('Remv ') or line.split()[1]!=manifest['package']):
                    raise Rejected('Dependency transaction changes another package; separate review required')
        return base

    def prepare(self,path,manifest,policy):
        base=self.preflight(path,manifest,policy)
        if manifest['type']=='deb':return dict(strategy='manual',previous=self.installed(policy),automatic=False)
        base.mkdir(parents=True,exist_ok=True)
        previous=str((base/'current').resolve()) if (base/'current').is_symlink() else None
        version=base/manifest['version']
        if version.exists():raise Rejected('Version directory already exists; inspect previous attempt')
        version.mkdir()
        try:
            with tarfile.open(path,'r:*') as archive:
                total=0;seen=set()
                for count,member in enumerate(archive):
                    name=PurePosixPath(member.name)
                    if count>=10000 or name.is_absolute() or '..' in name.parts or not name.parts or '\\' in member.name:
                        raise Rejected('Unsafe archive path or member count')
                    if name in seen or not (member.isdir() or member.isfile()) or member.mode & 0o7000:
                        raise Rejected('Archive links, duplicate paths, special files or privileged modes refused')
                    seen.add(name);total+=member.size
                    if total>1024**3:raise Rejected('Archive expands beyond limit')
                    target=version.joinpath(*name.parts)
                    if member.isdir():target.mkdir(parents=True,exist_ok=True,mode=0o755)
                    else:
                        target.parent.mkdir(parents=True,exist_ok=True)
                        with archive.extractfile(member) as src, target.open('xb') as dst:shutil.copyfileobj(src,dst)
                        target.chmod(0o755 if member.mode & 0o111 else 0o644)
            # Directory and recovery record exist before activation. Persist files.
            for child in version.rglob('*'):
                if child.is_file():
                    with child.open('rb') as f:os.fsync(f.fileno())
            for directory in [p for p in version.rglob('*') if p.is_dir()][::-1]+[version,base]:
                fd=os.open(directory,os.O_RDONLY|getattr(os,'O_DIRECTORY',0))
                try:os.fsync(fd)
                finally:os.close(fd)
            return dict(strategy='versioned-directory',previous=previous,target=str(version),automatic=bool(previous))
        except Exception:
            shutil.rmtree(version);raise

    def activate(self,manifest,recovery,path):
        if manifest['type']=='deb':
            self.run(['/usr/bin/apt-get','-y','--no-download','--no-remove','install',str(path)],900)
            return
        self.switch(self.root/manifest['package'],recovery['target'])

    def switch(self,base,target):
        base=Path(base);target=Path(target)
        if target.parent.resolve()!=base.resolve() or not target.is_dir():raise Rejected('Invalid recovery directory')
        temp=base/'current.new';temp.unlink(missing_ok=True)
        temp.symlink_to(target.name,target_is_directory=True);os.replace(temp,base/'current')
        fd=os.open(base,os.O_RDONLY|getattr(os,'O_DIRECTORY',0))
        try:os.fsync(fd)
        finally:os.close(fd)

    def health(self,manifest,policy):
        unit=policy.get('service')
        if unit:self.run(['/usr/bin/systemctl','restart',unit],30)
        if manifest['type']=='deb' and self.installed(policy)!=manifest['version']:raise Rejected('Installed package version differs')
        for command in policy['health']:self.run(command,30)
        return dict(passed=True,checks=len(policy['health']),service=unit)

    def rollback(self,manifest,policy,recovery):
        if not recovery.get('automatic') or recovery.get('strategy')!='versioned-directory':
            raise Rejected('Automatic recovery unavailable; manual intervention required')
        self.switch(self.root/manifest['package'],recovery['previous'])
        unit=policy.get('service')
        if unit:self.run(['/usr/bin/systemctl','restart',unit],30)
        for command in policy['health']:self.run(command,30)
        return dict(passed=True,restored=recovery['previous'])
