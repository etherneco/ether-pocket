"""Local map policy and segmented tracks. No hardware or network activation."""
import datetime as dt
import json
import math
import os
from pathlib import Path
import sqlite3
import time
import xml.etree.ElementTree as ET
from contextlib import contextmanager
from core import Rejected, number, distance

REAL = ('qualcomm-loc', 'gpsd', 'wifi', 'cellular', 'geoclue')


def coordinates(lat, lon):
    return dict(latitude=number(float(lat), -90, 90), longitude=number(float(lon), -180, 180))


def choose(candidates, now=None):
    now = time.time() if now is None else now
    rows = []
    for p in candidates:
        if not p:
            continue
        try:
            coordinates(p['latitude'], p['longitude'])
            age = now-number(p['timestamp'], 1, now+5)
            kind = p.get('kind')
            provider = p.get('provider')
            if kind == 'manual':
                rank = 5
            elif kind == 'last-known' or age > (3600 if provider == 'ip' else 30):
                rank = 4
            elif provider in ('qualcomm-loc', 'gpsd') and p.get('accuracy', 1e9) <= 100:
                rank = 0
            elif provider in REAL:
                rank = 1 if provider in ('wifi', 'geoclue') else 2
            elif provider == 'ip':
                rank = 3
            else:
                continue
            rows.append((rank, p.get('accuracy') or 1e9, age, p))
        except (ValueError, KeyError, TypeError):
            continue
    if not rows:
        return None
    rank, _, age, p = min(rows, key=lambda r: r[:3])
    return dict(p, age=max(0, age), stale=rank == 4,
                kind='last-known' if rank == 4 else p['kind'])


def recordable(p, now=None):
    now = time.time() if now is None else now
    try:
        coordinates(p['latitude'], p['longitude'])
        return (p.get('provider') in REAL and p.get('kind') == 'live'
                and p.get('precision') == 'precise' and 0 <= now-p['timestamp'] <= 30
                and 0 < p['accuracy'] <= 100)
    except (ValueError, KeyError, TypeError):
        return False


class Tracks:
    def __init__(self, path):
        self.path = Path(path)
        self.active = None
        self.paused = False
        self.segment = 0
        self.previous = None
        self.interrupted = False

    @contextmanager
    def db(self):
        self.path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
        if self.path.is_symlink():
            raise Rejected('Symlink track database forbidden')
        fd = os.open(self.path, os.O_CREAT | os.O_WRONLY, 0o600)
        os.close(fd)
        os.chmod(self.path, 0o600)
        db = sqlite3.connect(self.path)
        try:
            with db:
                db.execute('PRAGMA secure_delete=ON')
                db.execute('CREATE TABLE IF NOT EXISTS tracks(id INTEGER PRIMARY KEY,name TEXT,started REAL,stopped REAL,imported INTEGER DEFAULT 0)')
                db.execute('CREATE TABLE IF NOT EXISTS points(id INTEGER PRIMARY KEY,track INTEGER,segment INTEGER,document TEXT)')
                db.execute('CREATE TABLE IF NOT EXISTS places(id INTEGER PRIMARY KEY,name TEXT,latitude REAL,longitude REAL)')
                yield db
        finally:
            db.close()

    def start(self, consent=False):
        if not consent:
            raise Rejected('Enable local track history explicitly before recording')
        if self.active is not None:
            raise Rejected('Stop the current track first')
        now = time.time()
        with self.db() as db:
            if db.execute('SELECT count(*) FROM tracks').fetchone()[0]>=200:raise Rejected('Delete old tracks before recording (200-track limit)')
            self.active = db.execute('INSERT INTO tracks(name,started) VALUES(?,?)', ('Track '+dt.datetime.now().strftime('%Y-%m-%d %H:%M'), now)).lastrowid
        self.segment = 0
        self.previous = None
        self.paused = False
        self.interrupted = False
        return self.active

    def gap(self):
        if self.previous is not None:
            self.segment += 1
        self.previous = None
        self.interrupted = self.active is not None

    def pause(self):
        self.paused = True
        self.gap()

    def resume(self):
        if self.active is None:
            raise Rejected('No active recording')
        self.paused = False
        self.gap()

    def stop(self):
        if self.active is not None:
            with self.db() as db:
                db.execute('UPDATE tracks SET stopped=? WHERE id=?', (time.time(), self.active))
        self.active = None
        self.previous = None
        self.paused = False
        self.interrupted = False

    def sample(self, p, now=None):
        if self.active is None or self.paused:
            return False
        if not recordable(p, now):
            self.gap()
            return False
        p = {k:p[k] for k in ('latitude','longitude','timestamp','provider','accuracy','altitude','speed','heading','kind','precision') if k in p}
        if self.previous:
            elapsed = p['timestamp']-self.previous['timestamp']
            if elapsed <= 0:
                return False
            # Long gaps and implausible jumps must never become travelled distance.
            if elapsed > 90 or distance(self.previous, p) / elapsed > 100:
                self.gap()
        with self.db() as db:
            if db.execute('SELECT count(*) FROM points WHERE track=?', (self.active,)).fetchone()[0] >= 100000:
                self.pause()
                raise Rejected('Track sample limit reached; stop and save')
            db.execute('INSERT INTO points(track,segment,document) VALUES(?,?,?)', (self.active, self.segment, json.dumps(p, allow_nan=False)))
        self.previous = p
        self.interrupted = False
        return True

    def points(self, id):
        if not self.path.exists():return []
        with self.db() as db:
            return [dict(json.loads(r[1]), segment=r[0]) for r in db.execute('SELECT segment,document FROM points WHERE track=? ORDER BY id', (int(id),))]

    def summary(self, id):
        rows = self.points(id)
        total = elapsed = 0
        for a,b in zip(rows, rows[1:]):
            if a['segment'] == b['segment']:
                total += distance(a,b)
                if a.get('timestamp') and b.get('timestamp'):elapsed += max(0,b['timestamp']-a['timestamp'])
        return dict(distance=total, duration=elapsed, samples=len(rows))

    def list(self):
        if not self.path.exists():return []
        with self.db() as db:
            return [dict(id=r[0],name=r[1],started=r[2],stopped=r[3],imported=bool(r[4])) for r in db.execute('SELECT * FROM tracks ORDER BY id DESC LIMIT 200')]

    def rename(self, id, name):
        if not name.strip() or len(name)>100:raise Rejected('Track name required (max 100 characters)')
        with self.db() as db:db.execute('UPDATE tracks SET name=? WHERE id=?', (name.strip(),int(id)))

    def delete(self, id):
        if int(id) == self.active:raise Rejected('Stop recording before deleting')
        with self.db() as db:
            db.execute('DELETE FROM points WHERE track=?', (int(id),))
            db.execute('DELETE FROM tracks WHERE id=?', (int(id),))
        with self.db() as db:db.execute('VACUUM')

    def prune(self, days):
        number(days,1,90)
        if not self.path.exists():return
        with self.db() as db:
            ids=[r[0] for r in db.execute('SELECT id FROM tracks WHERE started<? AND id!=?', (time.time()-days*86400,self.active or -1))]
            for id in ids:
                db.execute('DELETE FROM points WHERE track=?',(id,))
                db.execute('DELETE FROM tracks WHERE id=?',(id,))

    def clear(self):
        if self.active is not None:raise Rejected('Stop recording before deleting history')
        if not self.path.exists():return
        with self.db() as db:
            db.execute('DELETE FROM points');db.execute('DELETE FROM tracks');db.execute('DELETE FROM places')
        with self.db() as db:db.execute('VACUUM')

    def places(self, query=''):
        if not self.path.exists():return []
        with self.db() as db:return [dict(id=r[0],name=r[1],latitude=r[2],longitude=r[3]) for r in db.execute('SELECT * FROM places WHERE name LIKE ? LIMIT 100',('%'+query+'%',))]

    def save_place(self, name, lat, lon):
        p=coordinates(lat,lon)
        if not name.strip() or len(name)>100:raise Rejected('Place name required')
        with self.db() as db:
            if db.execute('SELECT count(*) FROM places').fetchone()[0]>=1000:raise Rejected('Saved place limit reached')
            db.execute('INSERT INTO places(name,latitude,longitude) VALUES(?,?,?)',(name.strip(),p['latitude'],p['longitude']))

    def delete_place(self, id):
        with self.db() as db:db.execute('DELETE FROM places WHERE id=?',(int(id),))

    def export(self, id):
        ns='http://www.topografix.com/GPX/1/1'; ext='https://etherneco.com/ethermap/1'
        ET.register_namespace('',ns);ET.register_namespace('ether',ext)
        root=ET.Element('{'+ns+'}gpx',version='1.1',creator='EtherMAP')
        track=ET.SubElement(root,'{'+ns+'}trk')
        name=next((r['name'] for r in self.list() if r['id']==int(id)),'Track')
        ET.SubElement(track,'{'+ns+'}name').text=name
        segment=None
        for p in self.points(id):
            if segment != p['segment']:
                segment=p['segment'];node=ET.SubElement(track,'{'+ns+'}trkseg')
            point=ET.SubElement(node,'{'+ns+'}trkpt',lat=str(p['latitude']),lon=str(p['longitude']))
            if p.get('altitude') is not None:ET.SubElement(point,'{'+ns+'}ele').text=str(p['altitude'])
            if p.get('timestamp') is not None:ET.SubElement(point,'{'+ns+'}time').text=dt.datetime.fromtimestamp(p['timestamp'],dt.timezone.utc).isoformat().replace('+00:00','Z')
            extensions=ET.SubElement(point,'{'+ns+'}extensions')
            for k in ('provider','accuracy','speed'):
                if p.get(k) is not None:ET.SubElement(extensions,'{'+ext+'}'+k).text=str(p[k])
        return ET.tostring(root,encoding='unicode',xml_declaration=True)

    def import_gpx(self, data):
        if len(data)>16*1024**2 or b'<!DOCTYPE' in data.upper() or b'<!ENTITY' in data.upper():raise Rejected('Unsafe or oversized GPX')
        root=ET.fromstring(data)
        ns={'g':'http://www.topografix.com/GPX/1/1'}
        if root.tag!='{'+ns['g']+'}gpx':raise Rejected('GPX 1.1 required')
        points=[];segment=0
        for node in root.findall('g:trk/g:trkseg',ns):
            for p in node.findall('g:trkpt',ns):
                row=dict(coordinates(p.attrib['lat'],p.attrib['lon']),provider='imported',kind='imported')
                stamp=p.findtext('g:time',None,ns)
                if stamp:
                    stamp=dt.datetime.fromisoformat(stamp.replace('Z','+00:00'))
                    if stamp.tzinfo is None:raise Rejected('GPX time requires timezone')
                    row['timestamp']=stamp.timestamp()
                ele=p.findtext('g:ele',None,ns)
                if ele is not None:row['altitude']=number(float(ele),-20000,100000)
                # Imported extension source labels are untrusted and cannot become live fixes.
                for k in ('accuracy','speed'):
                    value=p.findtext('g:extensions/{https://etherneco.com/ethermap/1}'+k,None,ns)
                    if value is not None:row[k]=number(float(value),0,10000000 if k=='accuracy' else 10000)
                points.append((segment,json.dumps(row,allow_nan=False)))
                if len(points)>100000:raise Rejected('GPX point limit exceeded')
            segment+=1
        if not points:raise Rejected('No GPX track points')
        name=(root.findtext('g:trk/g:name','Imported track',ns) or 'Imported track')[:100]
        with self.db() as db:
            if db.execute('SELECT count(*) FROM tracks').fetchone()[0]>=200:raise Rejected('Track limit reached; delete old tracks before importing')
            id=db.execute('INSERT INTO tracks(name,started,stopped,imported) VALUES(?,?,?,1)',(name,time.time(),time.time())).lastrowid
            db.executemany('INSERT INTO points(track,segment,document) VALUES(?,?,?)',[(id,s,p) for s,p in points])
        return id
