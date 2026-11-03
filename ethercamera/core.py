"""Camera policy and private, camera-owned media. No hardware side effects on import."""
import datetime
import json
import os
from pathlib import Path
import re
import time
import uuid

class CameraError(RuntimeError): pass

def atomic_json(path, data):
    import tempfile
    path=Path(path);path.parent.mkdir(mode=0o700,parents=True,exist_ok=True)
    if path.is_symlink():raise CameraError('Symlink settings are forbidden')
    fd,temp=tempfile.mkstemp(prefix='.'+path.name,dir=path.parent)
    try:
        with os.fdopen(fd,'w',encoding='utf-8') as stream:
            json.dump(data,stream);stream.flush();os.fsync(stream.fileno())
        os.replace(temp,path)
    finally:
        if os.path.exists(temp):os.unlink(temp)

class Preferences:
    DEFAULTS=dict(width=640,height=480,fps=15,format='JPEG',cameraPolicy='ask-each-time',videoAudio=False,videoWidth=640,videoHeight=480,videoFps=15)
    def __init__(self,path):
        self.path=Path(path);self.error='';self.data=dict(self.DEFAULTS)
        try:
            if self.path.exists():
                if self.path.is_symlink():raise CameraError('Symlink preferences forbidden')
                if self.path.stat().st_size>4096:raise CameraError('Settings too large')
                self.data=self.validate(json.loads(self.path.read_text(encoding='utf-8')))
        except (OSError,ValueError,CameraError):
            self.data['cameraPolicy']='deny';self.error='Invalid stored camera settings; managed capture blocked'

    def validate(self, changes):
        if not isinstance(changes,dict) or set(changes)-set(self.DEFAULTS):raise CameraError('Unknown camera setting')
        data=dict(self.data);data.update(changes)
        options({k:data[k] for k in ('width','height','fps','format')})
        if data['cameraPolicy'] not in ('deny','ask-each-time'):raise CameraError('Invalid permission policy')
        if type(data['videoAudio']) is not bool:raise CameraError('Audio default must be boolean')
        for key,low,high in [('videoWidth',160,640),('videoHeight',120,480),('videoFps',1,15)]:
            if type(data[key]) is not int or not low<=data[key]<=high:raise CameraError('Invalid software video setting: '+key)
        return data

    def update(self,changes):
        data=self.validate(changes);atomic_json(self.path,data);self.data=data;self.error=''
        return dict(data)

    def capture_options(self,changes):
        # Only capture keys accepted; policy cannot be overridden inside a request.
        options(changes)
        data={k:self.data[k] for k in ('width','height','fps','format')};data.update(changes)
        return options(data)

    def video_options(self):
        return options(dict(width=self.data['videoWidth'],height=self.data['videoHeight'],fps=self.data['videoFps'],format='JPEG'))

class UsageHistory:
    def __init__(self,path):
        self.path=Path(path);self.entries=[]
        try:
            if self.path.is_symlink() or self.path.stat().st_size>40000:return
            rows=json.loads(self.path.read_text(encoding='utf-8'))
            if isinstance(rows,list):
                self.entries=[dict(event=r['event'],timestamp=r['timestamp']) for r in rows[-100:]
                    if isinstance(r,dict) and isinstance(r.get('event'),str) and len(r['event'])<=160 and type(r.get('timestamp')) is int]
        except (OSError,ValueError):pass

    def add(self,event):
        # No application purposes, owner tokens, media IDs, paths or scan text.
        known={'session-granted','preview-starting','photo-saved','recording-starting','recording-saved',
               'Released','Locked','Suspend requested','Owner or lock service exited','Service stopping','Service stopped',
               'Camera permission revoked','Five-minute session limit','Software video duration limit',
               'Storage low','Thermal recording limit','Battery recording limit','Power telemetry unavailable'}
        event=event if event in known else 'Camera operation stopped'
        self.entries=(self.entries+[dict(event=event,timestamp=int(time.time()))])[-100:]
        atomic_json(self.path,self.entries)
        return self.entries

def role(driver, card, caps):
    text = (driver + ' ' + card).lower()
    if 'req' in text: return 'vendor-request-manager'
    if 'sync' in text: return 'vendor-sync'
    if 'rotator' in text: return 'rotator'
    if 'vidc' in text or caps & 0xC000 or caps & 0x2002: return 'codec-or-output'
    if caps & 0x1001: return 'capture-candidate'
    return 'non-capture'

def options(document):
    if not isinstance(document, dict) or set(document) - {'width','height','fps','format'}:
        raise CameraError('Unknown capture options')
    result = dict(width=640, height=480, fps=15, format='JPEG')
    result.update(document)
    for key, low, high in [('width',160,1920),('height',120,1080),('fps',1,30)]:
        if type(result[key]) is not int or not low <= result[key] <= high:
            raise CameraError('Invalid ' + key)
    if result['format'] not in ('JPEG','PNG'): raise CameraError('Use JPEG or PNG')
    return result

class Sessions:
    def __init__(self, clock=time.monotonic):
        self.clock=clock; self.session=None

    def acquire(self, owner, device, purpose, consent, unlocked):
        if not unlocked: raise CameraError('EtherLock unavailable or session locked')
        if consent is not True: raise CameraError('Explicit user consent is required')
        if self.session: raise CameraError('Camera busy')
        if not isinstance(purpose,str) or not 1 <= len(purpose.strip()) <= 160:
            raise CameraError('Provide a short capture purpose')
        token=uuid.uuid4().hex
        self.session=dict(token=token,owner=owner,device=device,purpose=purpose,started=self.clock())
        return token

    def check(self, owner, token):
        if not self.session or self.session['owner'] != owner or self.session['token'] != token:
            raise CameraError('Session does not belong to caller')
        return self.session

    def release(self): self.session=None

class Library:
    """Indexes only explicit EtherCamera media, never recursively scans Pictures."""
    def __init__(self, root):
        self.root=Path(root).absolute()
        self.root.mkdir(mode=0o700,parents=True,exist_ok=True)
        if self.root.is_symlink(): raise CameraError('Media root must not be a symlink')

    def path(self, reference, suffix):
        if not re.fullmatch(r'[0-9a-f]{32}',reference): raise CameraError('Invalid media reference')
        if suffix not in ('.jpg','.png','.mp4','.pdf','.json'): raise CameraError('Invalid media type')
        p=self.root/(reference+suffix)
        if p.is_symlink(): raise CameraError('Symlink media is forbidden')
        return p

    def allocate(self, suffix):
        ref=uuid.uuid4().hex
        p=self.path(ref,suffix)
        fd=os.open(p,os.O_WRONLY|os.O_CREAT|os.O_EXCL,0o600);os.close(fd)
        return ref,p

    def commit(self, ref, suffix, metadata):
        p=self.path(ref,suffix)
        if not p.is_file() or not p.stat().st_size: raise CameraError('Empty capture')
        allowed={'camera','width','height','orientation','exposure','album','kind'}
        data={k:v for k,v in metadata.items() if k in allowed}
        data.update(reference=ref,suffix=suffix,bytes=p.stat().st_size,
                    timestamp=datetime.datetime.now(datetime.timezone.utc).isoformat())
        target=self.path(ref,'.json')
        fd=os.open(target,os.O_WRONLY|os.O_CREAT|os.O_EXCL,0o600)
        with os.fdopen(fd,'w',encoding='utf-8') as f:json.dump(data,f)
        return data

    def list(self, search='', limit=200, offset=0, kind='', album=''):
        import heapq
        if len(search)>160: raise CameraError('Search too long')
        offset=max(0,int(offset));limit=max(1,min(int(limit),200))
        if offset>100000:raise CameraError('Media page offset too large')
        def records():
            for p in self.root.glob('*.json'):
                try:
                    ref=p.stem;meta=self.path(ref,'.json')
                    if meta.stat().st_size>8192:continue
                    data=json.loads(meta.read_text(encoding='utf-8'))
                    media=self.path(ref,data['suffix'])
                    if not isinstance(data.get('timestamp'),str) or data.get('reference')!=ref:continue
                    if media.is_file() and search.casefold() in json.dumps(data).casefold() and (not kind or data.get('kind')==kind) and (not album or data.get('album')==album):yield data
                except (OSError,ValueError,KeyError,TypeError,CameraError):continue
        return heapq.nlargest(offset+limit,records(),key=lambda x:(x['timestamp'],x['reference']))[offset:]

    def get(self, ref):
        p=self.path(ref,'.json')
        if p.stat().st_size>8192:raise CameraError('Invalid metadata')
        data=json.loads(p.read_text())
        return self.path(ref,data['suffix']),data

    def delete(self, ref):
        p,_=self.get(ref);p.unlink();self.path(ref,'.json').unlink()
        cache=self.root/'.thumbnails'/(ref+'.jpg')
        if not cache.is_symlink():cache.unlink(missing_ok=True)

    def set_album(self, ref, album):
        if not isinstance(album,str) or len(album)>80 or any(ord(c)<32 for c in album):raise CameraError('Invalid album name')
        _,data=self.get(ref);data['album']=album.strip()
        atomic_json(self.path(ref,'.json'),data)
        return data

    def thumbnail(self, ref):
        import io
        from PIL import Image,ImageOps
        p,data=self.get(ref)
        folder=self.root/'.thumbnails'
        if folder.is_symlink():raise CameraError('Symlink thumbnail directory forbidden')
        folder.mkdir(mode=0o700,exist_ok=True)
        target=folder/(ref+'.jpg')
        if target.is_symlink():raise CameraError('Symlink thumbnail forbidden')
        if target.exists() and target.stat().st_size<1024*1024 and target.stat().st_mtime_ns>=p.stat().st_mtime_ns:
            return target.read_bytes()
        if data['suffix'] in ('.jpg','.png'):
            with Image.open(p) as image:
                if image.width*image.height>24_000_000:raise CameraError('Image too large')
                image=ImageOps.exif_transpose(image).convert('RGB');image.thumbnail((320,320))
                stream=io.BytesIO();image.save(stream,'JPEG',quality=80);payload=stream.getvalue()
        elif data['suffix']=='.mp4':
            import cv2
            cap=cv2.VideoCapture(str(p))
            try:ok,frame=cap.read()
            finally:cap.release()
            if not ok:raise CameraError('No video thumbnail frame')
            h,w=frame.shape[:2];frame=cv2.resize(frame,(max(1,int(w*min(320/w,320/h))),max(1,int(h*min(320/w,320/h)))))
            ok,encoded=cv2.imencode('.jpg',frame)
            if not ok:raise CameraError('Thumbnail encoding failed')
            payload=encoded.tobytes()
        else:raise CameraError('PDF thumbnail unavailable; use document icon')
        import tempfile
        fd,temp=tempfile.mkstemp(prefix='.'+ref,dir=folder)
        try:
            with os.fdopen(fd,'wb') as out:out.write(payload)
            os.replace(temp,target)
        finally:
            if os.path.exists(temp):os.unlink(temp)
        return payload

    def export(self, ref, directory):
        import shutil
        p,meta=self.get(ref);directory=Path(directory)
        if directory.is_symlink():raise CameraError('Symlink export directory forbidden')
        directory.mkdir(mode=0o700,parents=True,exist_ok=True)
        target=directory/(ref+meta['suffix'])
        fd=os.open(target,os.O_WRONLY|os.O_CREAT|os.O_EXCL|os.O_NOFOLLOW,0o600)
        try:
            with os.fdopen(fd,'wb') as out,p.open('rb') as source:shutil.copyfileobj(source,out)
        except Exception:target.unlink(missing_ok=True);raise
        return target

def payload_details(text):
    import urllib.parse
    kind='text';details={}
    if text.lower().startswith(('https://','http://')):
        try:
            parsed=urllib.parse.urlsplit(text)
            if parsed.hostname:kind='url';details={'url':text}
        except ValueError:pass
    elif text.startswith(('WIFI:','MECARD:')):
        fields={};part='';escaped=False;parts=[]
        for char in text.split(':',1)[1]:
            if escaped:part+='\\'+char;escaped=False
            elif char=='\\':escaped=True
            elif char==';':parts.append(part);part=''
            else:part+=char
        if part:parts.append(part)
        for part in parts:
            if ':' not in part:continue
            key,value=part.split(':',1);fields[key]=re.sub(r'\\(.)',r'\1',value)
        if text.startswith('WIFI:'):
            kind='wifi';details=dict(ssid=fields.get('S',''),security=fields.get('T','nopass'),password=fields.get('P',''),hidden=fields.get('H','').lower()=='true')
        else:kind='contact';details=dict(name=fields.get('N',''),telephone=fields.get('TEL',''),email=fields.get('EMAIL',''))
    elif text.upper().startswith('BEGIN:VCARD'):
        kind='contact'
        for line in re.sub(r'\r?\n[ \t]','',text).splitlines():
            if ':' not in line:continue
            key,value=line.split(':',1);key=key.split(';',1)[0].upper()
            if key in ('FN','N','TEL','EMAIL'):details.setdefault(key,[]).append(value)
    return kind,details

def manual_code(format, text):
    allowed={'EAN-13','EAN-8','UPC-A','Code 128','Code 39','QR Code','Data Matrix'}
    if format not in allowed or not isinstance(text,str) or not 1<=len(text)<=8192:raise CameraError('Invalid manual code')
    if format in ('EAN-13','EAN-8','UPC-A'):
        length={'EAN-13':13,'EAN-8':8,'UPC-A':12}[format]
        if not re.fullmatch(r'[0-9]{'+str(length)+'}',text):raise CameraError('Invalid barcode length')
        checksum=(10-sum(int(n)*(3 if i%2==0 else 1) for i,n in enumerate(reversed(text[:-1]))))%10
        if checksum!=int(text[-1]):raise CameraError('Invalid barcode check digit')
    if format=='Code 128' and (len(text)>160 or any(not 32<=ord(c)<=126 for c in text)):raise CameraError('Use printable Code 128 text')
    if format=='Code 39' and (len(text)>160 or not re.fullmatch(r'[A-Z0-9 .$/+%\-]+',text)):raise CameraError('Invalid Code 39 characters')
    kind,details=payload_details(text)
    return dict(format=format,text=text,kind=kind,details=details,requiresConfirmation=True,manual=True,verifiedBySensor=False)

class Scanner:
    def __init__(self): self.seen={}
    def decode(self, jpeg, continuous=False):
        import io
        import zxingcpp
        from PIL import Image
        results=[];now=time.monotonic()
        self.seen={k:v for k,v in self.seen.items() if now-v<2}
        for item in zxingcpp.read_barcodes(Image.open(io.BytesIO(jpeg))):
            if not item.valid or not item.text or len(item.text)>8192:continue
            key=(str(item.format),item.text)
            if continuous and key in self.seen:continue
            self.seen[key]=now
            text=item.text
            kind,details=payload_details(text)
            results.append(dict(format=str(item.format),text=text,kind=kind,details=details,requiresConfirmation=True))
        return results
