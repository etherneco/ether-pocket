"""Backend-independent telephony policy. No D-Bus, modem or audio I/O here."""
from dataclasses import dataclass, field
from pathlib import Path
import json
import os
import re
import sqlite3
import time
import uuid

EMERGENCY_WARNING = ('Emergency calling is unverified. Do not rely on EtherPocket as your sole '
                     'emergency telephone. Keep a known-working phone available.')
STATES = {0:'Unknown', 1:'Dialling', 2:'Ringing', 3:'Incoming', 4:'Active',
          5:'Held', 6:'Waiting', 7:'Ended'}
# UK baseline for the installed device, plus network-supplied numbers when exposed.
# Recognition is not a claim that an emergency call can be completed.
EMERGENCY_NUMBERS = {'112', '999'}

class PhoneError(Exception):
    pass

def number(value, emergency_numbers=EMERGENCY_NUMBERS):
    if not isinstance(value, str) or len(value) > 128:
        raise PhoneError('Enter a telephone number')
    value = value.strip()
    if value in emergency_numbers:
        return value
    value = re.sub(r'[ ()\.\-]', '', value)
    if not re.fullmatch(r'\+?[0-9]{1,15}', value):
        raise PhoneError('Use digits and an optional leading +; service codes are unavailable')
    return value

def private_directory(path):
    path = Path(path)
    path.mkdir(mode=0o700, parents=True, exist_ok=True)
    if path.is_symlink():
        raise PhoneError('Private directory must not be a symbolic link')
    path.chmod(0o700)
    return path

def open_private(path):
    path = Path(path)
    private_directory(path.parent)
    # Avoid following a user-supplied link when creating a database or export.
    if path.is_symlink():
        raise PhoneError('Private file must not be a symbolic link')
    fd = os.open(path, os.O_CREAT | os.O_RDWR, 0o600)
    os.close(fd)
    path.chmod(0o600)
    db = sqlite3.connect(path, timeout=3)
    db.row_factory = sqlite3.Row
    db.execute('PRAGMA foreign_keys=ON')
    return db

CONTACT_SCHEMA = '''
CREATE TABLE IF NOT EXISTS people(
 id TEXT PRIMARY KEY, name TEXT NOT NULL, emails TEXT NOT NULL DEFAULT '[]',
 photo TEXT NOT NULL DEFAULT '', notes TEXT NOT NULL DEFAULT '',
 favourite INTEGER NOT NULL DEFAULT 0, recent REAL);
CREATE TABLE IF NOT EXISTS numbers(
 number TEXT PRIMARY KEY, contact TEXT NOT NULL REFERENCES people(id) ON DELETE CASCADE);
'''

class Contacts:
    """Single reusable store; EtherSMS attaches this same schema/database."""
    def __init__(self, path):
        self.db = open_private(path)
        self.db.executescript(CONTACT_SCHEMA)

    def list(self, search='', limit=300):
        rows = self.db.execute('''SELECT * FROM people p WHERE name LIKE ? OR notes LIKE ?
            OR EXISTS(SELECT 1 FROM numbers n WHERE n.contact=p.id AND n.number LIKE ?)
            ORDER BY favourite DESC,name COLLATE NOCASE LIMIT ?''', ['%'+search+'%']*3+[limit])
        result = []
        for row in rows:
            item = dict(row)
            item['numbers'] = [r[0] for r in self.db.execute('SELECT number FROM numbers WHERE contact=? ORDER BY number', (row['id'],))]
            item['emails'] = json.loads(item['emails'])
            result.append(item)
        return result

    def lookup(self, value):
        row = self.db.execute('SELECT p.id,p.name FROM people p JOIN numbers n ON p.id=n.contact WHERE n.number=?', (value,)).fetchone()
        return dict(row) if row else {}

    def save(self, data):
        if not isinstance(data, dict):
            raise PhoneError('Contact must be an object')
        name = data.get('name', '').strip()
        raw = data.get('numbers', [])
        emails = data.get('emails', [])
        if not name or len(name)>200 or not isinstance(raw,list) or len(raw)>30:
            raise PhoneError('A name and up to 30 phone numbers are required')
        values = list(dict.fromkeys(number(n) for n in raw))
        if not isinstance(emails,list) or len(emails)>30 or any(not isinstance(e,str) or len(e)>320 for e in emails):
            raise PhoneError('Invalid email addresses')
        notes, photo = data.get('notes',''), data.get('photo','')
        if not isinstance(notes,str) or len(notes)>10000 or not isinstance(photo,str) or len(photo)>2048:
            raise PhoneError('Contact details are too large')
        if photo and not photo.startswith('file:///'):
            raise PhoneError('Contact photos must be local file URLs')
        cid = str(data.get('id') or uuid.uuid4())
        if len(cid)>100:
            raise PhoneError('Invalid contact reference')
        try:
            with self.db:
                self.db.execute('''INSERT INTO people(id,name,emails,photo,notes,favourite) VALUES(?,?,?,?,?,?)
                    ON CONFLICT(id) DO UPDATE SET name=excluded.name,emails=excluded.emails,
                    photo=excluded.photo,notes=excluded.notes,favourite=excluded.favourite''',
                    (cid,name,json.dumps(emails),photo,notes,int(bool(data.get('favourite')))))
                self.db.execute('DELETE FROM numbers WHERE contact=?',(cid,))
                self.db.executemany('INSERT INTO numbers VALUES(?,?)',[(n,cid) for n in values])
        except sqlite3.IntegrityError:
            raise PhoneError('A phone number already belongs to another contact') from None
        return cid

    def remove(self, cid):
        with self.db:
            self.db.execute('DELETE FROM people WHERE id=?',(cid,))

    def touch(self, value, stamp):
        with self.db:
            self.db.execute('UPDATE people SET recent=? WHERE id=(SELECT contact FROM numbers WHERE number=?)',(stamp,value))

    def export_vcard(self):
        def esc(s):return s.replace('\\','\\\\').replace('\n',r'\n').replace(';',r'\;').replace(',',r'\,').replace('\r','')
        lines=[]
        for p in self.list(limit=-1):
            lines += ['BEGIN:VCARD','VERSION:3.0','FN:'+esc(p['name'])]
            lines += ['TEL:'+n for n in p['numbers']]
            lines += ['EMAIL:'+esc(e) for e in p['emails']]
            lines += ['NOTE:'+esc(p['notes']),'X-ETHERNECO-FAVOURITE:'+str(p['favourite']),'END:VCARD']
        # vCard folding at <=75 UTF-8 octets, preserving code points.
        folded=[]
        for line in lines:
            chunk=''
            for c in line:
                if len((chunk+c).encode())>75:
                    folded.append(chunk);chunk=' '
                chunk+=c
            folded.append(chunk)
        return '\r\n'.join(folded)+'\r\n'

    def import_vcard(self, text):
        if not isinstance(text,str) or len(text.encode())>2_000_000:
            raise PhoneError('vCard import exceeds 2 MB')
        def unesc(s):return re.sub(r'\\([nN,;\\])', lambda m:'\n' if m[1] in 'nN' else m[1],s)
        unfolded=re.sub(r'\r?\n[ \t]', '',text)
        cards=[];current=None
        for line in unfolded.splitlines():
            if line.upper()=='BEGIN:VCARD':current={'numbers':[],'emails':[]}
            elif line.upper()=='END:VCARD':
                if current is None:raise PhoneError('Malformed vCard')
                cards.append(current);current=None
            elif current is not None and ':' in line:
                key,value=line.split(':',1);key=key.split(';',1)[0].upper();value=unesc(value)
                if key=='FN':current['name']=value
                elif key=='TEL':current['numbers'].append(value.removeprefix('tel:'))
                elif key=='EMAIL':current['emails'].append(value)
                elif key=='NOTE':current['notes']=value
                elif key=='X-ETHERNECO-FAVOURITE':current['favourite']=value=='1'
        if current is not None or not cards or len(cards)>1000:
            raise PhoneError('Incomplete or empty vCard import')
        # Prevalidate and import atomically through an in-memory copy. A malformed
        # later card must not leave half an import in the live contact store.
        shadow=Contacts.__new__(Contacts);shadow.db=sqlite3.connect(':memory:');shadow.db.row_factory=sqlite3.Row
        shadow.db.execute('PRAGMA foreign_keys=ON');self.db.backup(shadow.db)
        imported=[]
        try:
            for card in cards:
                existing=[shadow.lookup(number(n)) for n in card['numbers']]
                owners={r['id'] for r in existing if r}
                if owners:raise PhoneError('Import contains an existing telephone number; edit or merge it explicitly')
                imported.append(shadow.save(card))
            # Validation uses a snapshot; commit only new rows under a live
            # SQLite write transaction. Never replace concurrently edited data.
            try:
                with self.db:
                    for cid in imported:
                        p=shadow.db.execute('SELECT * FROM people WHERE id=?',(cid,)).fetchone()
                        self.db.execute('INSERT INTO people VALUES(?,?,?,?,?,?,?)',tuple(p))
                        self.db.executemany('INSERT INTO numbers VALUES(?,?)',
                            [tuple(r) for r in shadow.db.execute('SELECT number,contact FROM numbers WHERE contact=?',(cid,))])
            except sqlite3.IntegrityError:
                raise PhoneError('Contact store changed or import contains an existing number; no cards imported') from None
        finally:shadow.db.close()
        return len(cards)

    def backup(self, path):
        path=Path(path)
        fd=os.open(path,os.O_WRONLY|os.O_CREAT|os.O_EXCL,0o600);os.close(fd)
        target=sqlite3.connect(path)
        try:self.db.backup(target)
        finally:target.close()

@dataclass
class Call:
    id: str
    number: str
    direction: str
    state: str
    start: float
    backend: str
    last: float = 0
    duration: float = 0
    active_since: float | None = None
    answered: bool = False
    requested: str = ''
    reason: int = 0
    contact: str = ''
    name: str = ''
    timing_complete: bool = True
    def public(self, now):
        d=vars(self).copy()
        d['duration']=int(self.duration+(max(0,now-self.active_since) if self.active_since is not None else 0))
        return d

class History:
    def __init__(self,path):
        self.db=open_private(path)
        self.db.execute('''CREATE TABLE IF NOT EXISTS calls(id TEXT PRIMARY KEY,number TEXT,contact TEXT,
            direction TEXT,start REAL,end REAL,duration INTEGER,result TEXT,backend TEXT)''')
        self.db.execute('CREATE TABLE IF NOT EXISTS live(key TEXT PRIMARY KEY,payload TEXT NOT NULL)')

    def save(self,c,result,end):
        with self.db:
            self.db.execute('INSERT OR IGNORE INTO calls VALUES(?,?,?,?,?,?,?,?,?)',
                (c.id,c.number,c.contact,c.direction,c.start,end,int(c.duration),result,c.backend))

    def list(self,search='',kind=''):
        return [dict(r) for r in self.db.execute('''SELECT * FROM calls WHERE number LIKE ?
            AND (?='' OR result=?) ORDER BY start DESC LIMIT 300''',('%'+search+'%',kind,kind))]

    def remove(self,cid):
        with self.db:self.db.execute('DELETE FROM calls WHERE id=?',(cid,))

    def clear(self):
        with self.db:self.db.execute('DELETE FROM calls')

class Manager:
    def __init__(self,history,contacts,clock=time.time):
        self.history,self.contacts,self.clock=history,contacts,clock
        self.calls={};self.events=[];self.failure=''
        for row in self.history.db.execute('SELECT key,payload FROM live'):
            saved=json.loads(row['payload']);saved.update(state='Unknown',last=0,active_since=None,requested='',timing_complete=False)
            self.calls[row['key']]=Call(**saved)

    def journal(self,key,c):
        saved=vars(c).copy()
        # Persist active time observed so far, never count service downtime.
        saved['duration']=c.duration+(max(0,c.last-c.active_since) if c.active_since is not None else 0)
        saved['active_since']=None
        with self.history.db:
            if c.state in ('Ended','Failed','Uncertain'):self.history.db.execute('DELETE FROM live WHERE key=?',(key,))
            else:self.history.db.execute('INSERT OR REPLACE INTO live VALUES(?,?)',(key,json.dumps(saved)))

    def observe(self,key,props,backend='modemmanager',stamp=None):
        stamp=self.clock() if stamp is None else stamp
        state=STATES.get(int(props.get('State',0)),'Unknown')
        c=self.calls.get(key)
        is_new=c is None
        if c and (stamp<c.last or c.state in ('Ended','Failed','Uncertain')):
            return
        if c is None:
            n=str(props.get('Number',''))[:128]
            who=self.contacts.lookup(n)
            c=Call(str(uuid.uuid4()),n,'Incoming' if int(props.get('Direction',0))==1 else 'Outgoing',state,stamp,backend,
                contact=who.get('id',''),name=who.get('name',''))
            self.calls[key]=c
        previous=c.state
        if c.active_since is not None and state!='Active':
            c.duration+=max(0,stamp-c.active_since);c.active_since=None
        if state=='Active':
            c.answered=True
            if c.active_since is None:c.active_since=stamp
        c.state,c.last,c.reason=state,stamp,int(props.get('StateReason',0))
        if props.get('Number'):
            c.number=str(props['Number'])[:128];who=self.contacts.lookup(c.number)
            c.contact,c.name=who.get('id',''),who.get('name','')
        request=c.requested
        if state!=previous:c.requested=''
        if state in ('Incoming','Waiting') and (is_new or previous not in ('Incoming','Waiting')):
            self.events.append(('Incoming',key))
        if state=='Ended':
            # MM reasons: 3 accepted, 4 terminated, 5 refused/busy, 6/7 errors.
            # Transferred/deflected (8/9) must not be misreported as failures.
            result='Failed' if c.reason in (5,6,7) else (
                'Rejected' if c.direction=='Incoming' and request=='decline' else
                'Uncertain' if not c.timing_complete and not c.answered else
                'Missed' if c.direction=='Incoming' and not c.answered else c.direction)
            self.history.save(c,result,stamp);self.contacts.touch(c.number,stamp)
            if result=='Missed':self.events.append(('Missed',key))
        self.journal(key,c)

    def lost(self,keys):
        for key in keys:
            c=self.calls.get(key)
            if c and c.state not in ('Ended','Failed','Uncertain'):
                stamp=self.clock()
                if c.active_since is not None:c.duration+=max(0,stamp-c.active_since);c.active_since=None
                c.state='Uncertain';c.requested='';self.history.save(c,'Uncertain',stamp)
                self.journal(key,c)
                self.failure='Call backend disappeared; termination and audio state are unconfirmed'

    def preflight(self,value,status):
        n=number(value)
        emergency=n in EMERGENCY_NUMBERS
        if not status.get('voice'):raise PhoneError('Cellular calling unavailable: no ModemManager Voice interface')
        # Emergency attempts bypass ordinary SIM/network checks. Never auto-dial.
        if not emergency:
            if not status.get('simReady'):raise PhoneError('The SIM is missing or locked')
            if not status.get('registered'):raise PhoneError('The modem is not registered on a network')
            if status.get('emergencyOnly'):raise PhoneError('The backend permits emergency attempts only')
        if any(c.state not in ('Ended','Failed','Uncertain') for c in self.calls.values()):
            raise PhoneError('A call already exists; additional outgoing calls are unverified')
        return n

    def request(self,key,action):
        c=self.calls.get(key)
        if not c:raise PhoneError('Call is no longer available')
        if action=='answer' and c.state!='Incoming':raise PhoneError('Only a ringing incoming call can be answered')
        if action=='dtmf' and c.state!='Active':raise PhoneError('DTMF requires an observed active call')
        if c.state in ('Ended','Failed','Uncertain'):raise PhoneError('Call is no longer available')
        if action!='dtmf':c.requested=action
        return c

def diagnostic(status,audio,failure=''):
    # Explicit allowlist; never export numbers, contacts, call paths or modem IDs.
    return {'schema':1,'timestamp':time.time(),'backend':'ModemManager',
        'modem':bool(status.get('modem')),'voice':bool(status.get('voice')),
        'simReady':bool(status.get('simReady')),'registered':bool(status.get('registered')),
        'ims':'Not tested / unavailable from selected backend','volte':'Blocked',
        'audio':{'operational':bool(audio.get('operational')),'verified':False},
        'lastFailure':failure,'incoming':'Not verified','realCallVerified':False,
        'screenOffWake':'Not tested','emergency':EMERGENCY_WARNING}
