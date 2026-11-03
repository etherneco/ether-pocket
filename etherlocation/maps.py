"""Private raster MBTiles storage. No public tile server or implicit network use."""
import hashlib
import json
import os
from pathlib import Path
import shutil
import sqlite3
import tempfile
import threading
from contextlib import closing
from urllib.parse import urlsplit
import urllib.request
from core import Rejected,atomic

MAX_BYTES=2*1024**3
def dataset_url(url):
    u=urlsplit(url)
    if u.scheme!='https' or not u.hostname or u.username or u.password or u.fragment:raise Rejected('A direct HTTPS dataset URL is required')
    if u.hostname=='tile.openstreetmap.org' or u.hostname.endswith('.tile.openstreetmap.org'):raise Rejected('Public OSM tile bulk downloads prohibited')
    return url
def inspect(path):
    path=Path(path)
    if path.is_symlink() or not path.is_file() or not 1<=path.stat().st_size<=MAX_BYTES:raise Rejected('Invalid map file or size exceeds 2 GiB')
    with closing(sqlite3.connect(path.resolve().as_uri()+'?mode=ro&immutable=1',uri=True)) as db:
        db.setlimit(sqlite3.SQLITE_LIMIT_LENGTH,4*1024**2)
        metadata=dict(db.execute('SELECT name,value FROM metadata LIMIT 100'))
        if metadata.get('format') not in ('png','jpg','jpeg'):raise Rejected('Only raster PNG/JPEG MBTiles supported; vector datasets require another renderer')
        if not metadata.get('attribution'):raise Rejected('Dataset attribution is required')
        if metadata.get('scheme','tms')!='tms':raise Rejected('Only TMS row numbering supported')
        if db.execute('PRAGMA quick_check').fetchone()[0]!='ok':raise Rejected('Corrupt map database')
        zoom=db.execute('SELECT min(zoom_level),max(zoom_level) FROM tiles').fetchone()
        if zoom[0] is None or zoom[0]<0 or zoom[1]>20:raise Rejected('Invalid zoom range')
        blob=db.execute('SELECT tile_data FROM tiles LIMIT 1').fetchone()[0]
        if not (blob.startswith(b'\x89PNG\r\n\x1a\n') or blob.startswith(b'\xff\xd8')):raise Rejected('Unsupported tile payload')
        return dict(name=metadata.get('name',path.stem)[:100],attribution=metadata['attribution'][:2000],
            minZoom=zoom[0],maxZoom=zoom[1],bounds=metadata.get('bounds'),size=path.stat().st_size,format=metadata['format'])

class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self,*args,**kwargs):raise Rejected('Map downloads do not follow redirects; configure final licensed URL')

class Maps:
    def __init__(self,root):
        self.root=Path(root);self.root.mkdir(parents=True,exist_ok=True,mode=0o700)
    def regions(self):
        rows=[]
        for p in sorted(self.root.glob('*.json')):
            if p.stem.endswith('.download'):continue
            try:
                row=json.loads(p.read_text());row.update(id=p.stem,available=(self.root/(p.stem+'.mbtiles')).is_file());rows.append(row)
            except (OSError,ValueError):pass
        return rows
    def import_file(self,source,license_confirmed=False):
        if not license_confirmed:raise Rejected('Confirm that the dataset permits local offline use')
        source=Path(source).expanduser();info=inspect(source)
        if sum(p.stat().st_size for p in self.root.glob('*.mbtiles'))+info['size']>4*MAX_BYTES:raise Rejected('Map storage quota exceeded (8 GiB)')
        if shutil.disk_usage(self.root).free<info['size']+100*1024**2:raise Rejected('Insufficient free map storage')
        digest=hashlib.sha256()
        fd,temp=tempfile.mkstemp(dir=self.root)
        try:
            with source.open('rb') as src,os.fdopen(fd,'wb') as dst:
                total=0
                while chunk:=src.read(1024**2):
                    total+=len(chunk)
                    if total>MAX_BYTES:raise Rejected('Map exceeds limit')
                    digest.update(chunk);dst.write(chunk)
                dst.flush();os.fsync(dst.fileno())
            inspect(temp)
            id=digest.hexdigest()[:32];target=self.root/(id+'.mbtiles')
            os.replace(temp,target);atomic(self.root/(id+'.json'),info);return dict(id=id,**info)
        finally:
            if os.path.exists(temp):os.unlink(temp)
    def delete(self,id):
        if len(id)!=32 or any(c not in '0123456789abcdef' for c in id):raise Rejected('Invalid map region')
        for suffix in ('.json','.mbtiles'):(self.root/(id+suffix)).unlink(missing_ok=True)
    def estimate(self,url):
        req=urllib.request.Request(dataset_url(url),method='HEAD',headers={'User-Agent':'EtherLocation/0.1','Accept-Encoding':'identity'})
        with urllib.request.build_opener(NoRedirect()).open(req,timeout=20) as response:
            total=int(response.headers.get('Content-Length',0))
            if not 1<=total<=MAX_BYTES:raise Rejected('Dataset size unavailable or exceeds 2 GiB')
            return dict(state='estimate',bytes=total,MiB=round(total/1024**2,2),resumeSupported=response.headers.get('Accept-Ranges')=='bytes')
    def download(self,url,sha256,license_confirmed,progress=lambda data:None,pause=None):
        if not license_confirmed:raise Rejected('Offline redistribution/use permission must be confirmed')
        dataset_url(url)
        if len(sha256)!=64 or any(c not in '0123456789abcdef' for c in sha256):raise Rejected('Expected SHA256 is required')
        key=hashlib.sha256((url+sha256).encode()).hexdigest()[:32]
        part=self.root/(key+'.part');offset=part.stat().st_size if part.exists() else 0
        req=urllib.request.Request(url,headers={'User-Agent':'EtherLocation/0.1','Accept-Encoding':'identity',**({'Range':f'bytes={offset}-'} if offset else {})})
        with urllib.request.build_opener(NoRedirect()).open(req,timeout=20) as response:
            if response.status not in (200,206):raise Rejected('Download response rejected')
            if offset and response.status==206:
                import re
                match=re.fullmatch(r'bytes (\d+)-(\d+)/(\d+)',response.headers.get('Content-Range',''))
                if not match or int(match[1])!=offset:raise Rejected('Invalid resume response')
                total=int(match[3])
            else:offset=0;total=int(response.headers.get('Content-Length',0))
            if not 1<=total<=MAX_BYTES:raise Rejected('A bounded dataset Content-Length is required')
            if sum(p.stat().st_size for p in self.root.iterdir() if p.is_file() and p!=part)+total>4*MAX_BYTES:raise Rejected('Map/download storage quota exceeded')
            if shutil.disk_usage(self.root).free<2*total+100*1024**2:raise Rejected('Insufficient download/import storage')
            with part.open('ab' if offset else 'wb') as out:
                received=offset
                while chunk:=response.read(1024**2):
                    received+=len(chunk)
                    if received>total:raise Rejected('Download exceeds declared size')
                    out.write(chunk);progress(dict(received=received,total=total,state='downloading'))
                    if pause and pause.is_set():return dict(state='paused',received=received,total=total)
            if received!=total:raise Rejected('Incomplete download; partial file retained for resume')
        digest=hashlib.sha256()
        with part.open('rb') as f:
            while chunk:=f.read(1024**2):digest.update(chunk)
        if digest.hexdigest()!=sha256:
            part.unlink(missing_ok=True);raise Rejected('Dataset checksum mismatch')
        info=self.import_file(part,True);part.unlink(missing_ok=True);return dict(state='complete',**info)

if __name__=='__main__':
    import argparse
    os.umask(0o077);parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('operation',choices=['list','import','delete','download','estimate'])
    parser.add_argument('value',nargs='?');parser.add_argument('--sha256');parser.add_argument('--offline-license-confirmed',action='store_true')
    args=parser.parse_args();maps=Maps(Path.home()/'.local/share/etherlocation/maps')
    try:
        if args.operation=='list':result=maps.regions()
        elif args.operation=='import':result=maps.import_file(args.value,args.offline_license_confirmed)
        elif args.operation=='delete':maps.delete(args.value);result=maps.regions()
        elif args.operation=='estimate':result=maps.estimate(args.value)
        else:result=maps.download(args.value,args.sha256 or '',args.offline_license_confirmed,lambda row:print(json.dumps(row),flush=True))
        print(json.dumps(result))
    except (OSError,ValueError,sqlite3.Error) as e:parser.exit(1,str(e)+'\n')
