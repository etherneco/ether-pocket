"""Bounded private cache. A completed transfer still requires verification."""
import os
from pathlib import Path
import shutil
import time
from security import Rejected, verify_file


class ArtifactManager:
    def __init__(self, directory, provider, limit=2*1024**3):
        self.directory = Path(directory); self.directory.mkdir(parents=True, exist_ok=True, mode=0o700)
        self.provider, self.limit = provider, limit

    def path(self, manifest): return self.directory / (manifest['sha256'] + '.artifact')

    def cleanup(self, required=0):
        files = sorted(self.directory.glob('*'), key=lambda p:p.stat().st_mtime)
        total = sum(p.stat().st_size for p in files if p.is_file())
        for p in files:
            if total + required <= self.limit: break
            if p.is_file():
                size=p.stat().st_size;p.unlink();total-=size
        if required > self.limit or shutil.disk_usage(self.directory).free < required + 64*1024**2:
            raise Rejected('Insufficient update cache space')

    def download(self, manifest, url, cancel, progress):
        target = self.path(manifest)
        if target.exists():
            try: verify_file(target, manifest); return target
            except Rejected: target.unlink()
        part = target.with_suffix('.part')
        self.cleanup(manifest['size'])
        # Restart from zero unless a strong validator is available. Do not append
        # arbitrary Range responses to a previous transfer.
        for attempt in range(3):
            try:
                with self.provider.open(url, extra={'Accept':'application/octet-stream'}) as response, open(part, 'wb') as stream:
                    if response.status != 200: raise Rejected('Unexpected download response')
                    count = 0
                    deadline = time.monotonic() + 1800
                    for chunk in iter(lambda: response.read(256*1024), b''):
                        if cancel.is_set(): raise Rejected('Cancelled')
                        count += len(chunk)
                        if count > manifest['size']: raise Rejected('Download exceeds signed size')
                        if time.monotonic() > deadline: raise Rejected('Download exceeded deadline')
                        stream.write(chunk); progress(count, manifest['size'])
                    stream.flush();os.fsync(stream.fileno())
                verify_file(part, manifest)
                os.replace(part, target)
                return target
            except Rejected:
                part.unlink(missing_ok=True);raise
            except (OSError, RuntimeError):
                part.unlink(missing_ok=True)
                if cancel.is_set(): raise Rejected('Cancelled')
                if attempt == 2: raise
                cancel.wait(2**attempt)
        raise Rejected('Download failed')

    def import_file(self, manifest, source):
        source = Path(source)
        if not source.is_file() or source.is_symlink(): raise Rejected('Import requires a regular file')
        verify_file(source, manifest)
        self.cleanup(manifest['size'])
        part = self.path(manifest).with_suffix('.part')
        try:
            with source.open('rb') as src, part.open('wb') as dst:
                remaining = manifest['size']
                while remaining:
                    data = src.read(min(remaining, 1024*1024))
                    if not data: raise Rejected('Import changed while reading')
                    dst.write(data); remaining -= len(data)
                dst.flush(); os.fsync(dst.fileno())
            verify_file(part, manifest);os.replace(part,self.path(manifest))
        finally: part.unlink(missing_ok=True)
        return self.path(manifest)
