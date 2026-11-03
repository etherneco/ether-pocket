"""Privacy and positioning policy. Importing this module never activates hardware."""
import copy
import datetime as dt
import json
import math
import os
from pathlib import Path
import secrets
import sqlite3
import time
import xml.etree.ElementTree as ET
from contextlib import contextmanager

class Rejected(ValueError):pass

def number(value,low,high):
    if isinstance(value,bool) or not isinstance(value,(float,int)) or not math.isfinite(value) or not low<=value<=high:
        raise Rejected('Invalid numeric range')
    return value

def position(data,now=None):
    now=time.time() if now is None else now
    p={k:number(data[k],a,b) for k,a,b in [('latitude',-90,90),('longitude',-180,180),('accuracy',0.01,10000000),('timestamp',1,now+5)]}
    if data.get('provider') not in ('qualcomm-loc','gpsd','geoclue','manual'):raise Rejected('Unknown provider')
    p.update(provider=data['provider'],kind='manual' if data['provider']=='manual' else 'live',fixType=str(data.get('fixType','unknown'))[:40])
    for k,a,b in [('altitude',-20000,100000),('verticalAccuracy',0,10000000),('speed',0,10000),('heading',0,360),('satellitesUsed',0,256)]:
        if k in data:p[k]=number(data[k],a,b)
    return p

def age(p,now=None):return max(0,(time.time() if now is None else now)-p['timestamp'])

def select(candidates,precise=True,max_age=30,now=None):
    rows=[p for p in candidates if p and p['kind']=='live' and age(p,now)<=max_age]
    if not rows:return None
    return min(rows,key=lambda p:(0 if precise and p['provider'] in ('qualcomm-loc','gpsd') and p['accuracy']<=100 else 1,p['accuracy'],age(p,now)))

def disclose(p,precision='approximate',grid=10000,now=None,cached=False):
    """Grid centres and conservative cell radius; strip all precise side channels."""
    if not p:return None
    if precision not in ('precise','approximate'):raise Rejected('Invalid precision')
    out=copy.deepcopy(p);out['age']=age(p,now)
    if cached:out['kind']='last-known'
    if precision=='approximate':
        number(grid,1000,100000)
        # Equal angular grid is intentionally coarse at high latitudes too. Radius
        # includes the full cell diagonal plus the original reported uncertainty.
        step=grid/111000
        out['latitude']=max(-90,min(90,(math.floor(p['latitude']/step)+0.5)*step))
        out['longitude']=max(-180,min(180,(math.floor(p['longitude']/step)+0.5)*step))
        out['accuracy']=p['accuracy']+math.sqrt(2)*grid
        for key in ('altitude','verticalAccuracy','speed','heading'):out.pop(key,None)
    out['precision']=precision
    return out

def options(data):
    if not isinstance(data,dict) or set(data)-{'precision','interval','timeout','maxAge','background','origin'}:raise Rejected('Unknown options')
    out=dict(precision='approximate',interval=10,timeout=60,maxAge=30,background=False,origin='')
    out.update(data)
    if out['precision'] not in ('precise','approximate'):raise Rejected('Invalid precision')
    for k,a,b in [('interval',5,300),('timeout',5,3600),('maxAge',1,3600)]:number(out[k],a,b)
    if type(out['background']) is not bool:raise Rejected('Invalid background option')
    origin=out['origin']
    if not isinstance(origin,str) or len(origin)>256:raise Rejected('Invalid origin')
    if origin:
        from urllib.parse import urlsplit
        u=urlsplit(origin)
        if u.scheme!='https' or not u.hostname or u.username or u.password or u.path not in ('','/') or u.query or u.fragment:
            raise Rejected('A secure website origin is required')
        out['origin']='https://'+u.netloc.lower()
    return out

def atomic(path,data):
    import tempfile
    path=Path(path);path.parent.mkdir(parents=True,exist_ok=True,mode=0o700)
    if path.is_symlink():raise Rejected('Symlink storage forbidden')
    fd,temp=tempfile.mkstemp(prefix='.',dir=path.parent)
    try:
        with os.fdopen(fd,'w') as f:json.dump(data,f,allow_nan=False);f.flush();os.fsync(f.fileno())
        os.replace(temp,path)
    finally:
        if os.path.exists(temp):os.unlink(temp)

class Permissions:
    def __init__(self):self.grants={};self.requests={};self.subscriptions={};self.audit=[]
    def request(self,owner,app,opts,now=None):
        opts=options(opts);now=time.monotonic() if now is None else now
        if len(self.requests)>=32:raise Rejected('Permission queue full')
        if sum(r['owner']==owner for r in self.requests.values())>=2:raise Rejected('Request already pending')
        token=secrets.token_hex(16)
        self.requests[token]=dict(owner=owner,app=app,options=opts,expires=now+120)
        return token
    def resolve(self,token,policy,precision,background=False,now=None):
        now=time.monotonic() if now is None else now
        if token not in self.requests:raise Rejected('Permission request expired')
        r=self.requests.pop(token)
        if r['expires']<now:raise Rejected('Permission request expired')
        if policy not in ('allow-while-using','ask-every-time','deny') or precision not in ('precise','approximate'):raise Rejected('Invalid permission policy')
        if type(background) is not bool:raise Rejected('Invalid background policy')
        # Ask every time grants one bounded session to this unique bus owner.
        key=(r['app'],r['options']['origin'])
        self.grants[key]=dict(policy=policy,precision=precision,background=background,once=r['owner'] if policy=='ask-every-time' else None,expires=now+r['options']['timeout'] if policy=='ask-every-time' else None)
        self.audit.append(dict(timestamp=time.time(),app=r['app'],policy=policy,precision=precision,background=background))
        self.audit=self.audit[-100:]
    def check(self,owner,app,opts,foreground,locked):
        g=self.grants.get((app,opts['origin']))
        if not g or g['policy']=='deny':raise Rejected('Location permission required')
        if g['policy']=='ask-every-time' and (g['once']!=owner or g['expires']<=time.monotonic()):raise Rejected('New permission required')
        bg=opts['background'] and g['background']
        if (locked or not foreground) and not bg:raise Rejected('Foreground use required')
        if opts['background'] and not bg:raise Rejected('Background permission required')
        return 'approximate' if 'approximate' in (g['precision'],opts['precision']) else 'precise'
    def subscribe(self,owner,app,opts,now=None):
        now=time.monotonic() if now is None else now
        if len(self.subscriptions)>=16 or sum(s['owner']==owner for s in self.subscriptions.values())>=2:raise Rejected('Subscription limit reached')
        token=secrets.token_hex(16)
        self.subscriptions[token]=dict(owner=owner,app=app,options=opts,expires=now+opts['timeout'],next=now)
        return token
    def stop(self,owner,token):
        s=self.subscriptions.get(token)
        if not s or s['owner']!=owner:raise Rejected('Subscription belongs to another client')
        del self.subscriptions[token]
        key=(s['app'],s['options']['origin']);g=self.grants.get(key)
        if g and g['policy']=='ask-every-time':self.grants.pop(key,None)
    def disconnect(self,owner):
        for pool in (self.requests,self.subscriptions):
            for key in list(pool):
                if pool[key]['owner']==owner:del pool[key]
        self.grants={k:g for k,g in self.grants.items() if g.get('once')!=owner}
    def revoke(self,app,origin=''):
        self.grants.pop((app,origin),None)
        self.subscriptions={k:s for k,s in self.subscriptions.items() if (s['app'],s['options']['origin'])!=(app,origin)}
    def expire(self,now=None):
        now=time.monotonic() if now is None else now
        for token,s in list(self.subscriptions.items()):
            if s['expires']<=now:self.stop(s['owner'],token)
        self.requests={k:r for k,r in self.requests.items() if r['expires']>now}

class History:
    def __init__(self,path):
        self.path=Path(path);self.enabled=False;self.retention=7;self.last=0
    @contextmanager
    def db(self):
        self.path.parent.mkdir(parents=True,exist_ok=True,mode=0o700)
        if self.path.is_symlink():raise Rejected('Symlink history forbidden')
        fd=os.open(self.path,os.O_CREAT|os.O_WRONLY,0o600);os.close(fd);os.chmod(self.path,0o600)
        db=sqlite3.connect(self.path)
        try:
            with db:
                db.execute('CREATE TABLE IF NOT EXISTS fixes(id INTEGER PRIMARY KEY, timestamp REAL, document TEXT)')
                yield db
        finally:db.close()
    def prune(self,db,now):
        db.execute('DELETE FROM fixes WHERE timestamp<?',(now-self.retention*86400,))
        db.execute('DELETE FROM fixes WHERE id NOT IN (SELECT id FROM fixes ORDER BY id DESC LIMIT 10000)')
    def record(self,p,now=None):
        now=time.time() if now is None else now
        if not self.enabled or p['kind']!='live' or age(p,now)>30 or now-self.last<10:return
        with self.db() as db:
            db.execute('INSERT INTO fixes(timestamp,document) VALUES(?,?)',(p['timestamp'],json.dumps(p)));self.prune(db,now)
        self.last=now
    def entries(self):
        if not self.path.exists():return []
        with self.db() as db:
            self.prune(db,time.time())
            return [dict(id=row[0],**json.loads(row[1])) for row in db.execute('SELECT id,document FROM fixes ORDER BY timestamp DESC LIMIT 10000')]
    def delete(self,ids=None):
        if not self.path.exists():return
        with self.db() as db:
            db.execute('PRAGMA secure_delete=ON')
            if ids is None:db.execute('DELETE FROM fixes')
            else:
                for id in ids:db.execute('DELETE FROM fixes WHERE id=?',(int(id),))
        with self.db() as db:db.execute('VACUUM')
    def export(self,kind):
        rows=list(reversed(self.entries()))
        if kind=='GeoJSON':return json.dumps(dict(type='FeatureCollection',features=[dict(type='Feature',geometry=dict(type='Point',coordinates=[p['longitude'],p['latitude']]),properties={k:p[k] for k in ('timestamp','accuracy','provider')}) for p in rows]))
        if kind!='GPX':raise Rejected('Unknown history format')
        root=ET.Element('gpx',version='1.1',creator='EtherLocation',xmlns='http://www.topografix.com/GPX/1/1')
        track=ET.SubElement(ET.SubElement(root,'trk'),'trkseg')
        for p in rows:
            node=ET.SubElement(track,'trkpt',lat=str(p['latitude']),lon=str(p['longitude']))
            ET.SubElement(node,'time').text=dt.datetime.fromtimestamp(p['timestamp'],dt.timezone.utc).isoformat().replace('+00:00','Z')
        return ET.tostring(root,encoding='unicode')

def distance(a,b):
    lat1,lat2=map(math.radians,(a['latitude'],b['latitude']))
    dlat=lat2-lat1;dlon=math.radians(b['longitude']-a['longitude'])
    v=math.sin(dlat/2)**2+math.cos(lat1)*math.cos(lat2)*math.sin(dlon/2)**2
    return 6371000*2*math.asin(math.sqrt(min(1,v)))

class Geofences:
    def __init__(self):self.zones={};self.states={}
    def put(self,id,data):
        if not isinstance(id,str) or not id.isalnum() or len(id)>40:raise Rejected('Invalid zone id')
        if len(self.zones)>=32 and id not in self.zones:raise Rejected('Zone limit reached')
        row={k:number(data[k],a,b) for k,a,b in [('latitude',-90,90),('longitude',-180,180),('radius',50,100000)]}
        row.update(enabled=bool(data.get('enabled',True)),dwell=number(data.get('dwell',60),10,3600))
        self.zones[id]=row;self.states.pop(id,None)
    def evaluate(self,p,now=None):
        now=time.time() if now is None else now
        if p['kind']!='live' or age(p,now)>30:return []
        events=[]
        for id,z in self.zones.items():
            if not z['enabled'] or p['accuracy']>min(100,z['radius']/2):continue
            d=distance(p,z);h=max(20,z['radius']*.1)
            target='inside' if d+p['accuracy']<z['radius']-h else 'outside' if d-p['accuracy']>z['radius']+h else None
            if target is None:
                if id in self.states:self.states[id]['candidate']=None
                continue
            s=self.states.setdefault(id,dict(stable=None,candidate=None,since=now,seen=p['timestamp'],dwelled=False,lastValid=now))
            if p['timestamp']<s['seen']:continue
            if now-s['lastValid']>30:s.update(candidate=None,entered=now,dwelled=False)
            s['lastValid']=now
            # Repeated callbacks for one fix cannot establish a transition.
            if p['timestamp']==s['seen'] and s['candidate'] is not None:continue
            s['seen']=p['timestamp']
            if s['candidate']!=target:s.update(candidate=target,since=now)
            elif now-s['since']>=10 and target!=s['stable']:
                previous=s['stable'];s.update(stable=target,entered=now,dwelled=False)
                if previous is not None:events.append(dict(zone=id,event='entry' if target=='inside' else 'exit'))
            elif target==s['stable']=='inside' and not s['dwelled'] and now-s.get('entered',now)>=z['dwell']:
                s['dwelled']=True;events.append(dict(zone=id,event='dwell'))
        return events
