import json
import sqlite3
import time
import uuid
from security import Rejected

FLOW = ['Discovered','Available','Downloading','Downloaded','Verifying','Verified','Preparing','Installing','Health Checking','Completed']
FAILURES = ['Cancelled','Verification Failed','Installation Failed','Recovery Required','Rolled Back','Manual Intervention Required']
TERMINAL = ['Completed', *FAILURES]


class History:
    def __init__(self, path):
        self.db=sqlite3.connect(path)
        self.db.execute('PRAGMA journal_mode=WAL');self.db.execute('PRAGMA synchronous=FULL')
        self.db.execute('CREATE TABLE IF NOT EXISTS transactions(id TEXT PRIMARY KEY,state TEXT,document TEXT,updated REAL)')
        self.db.execute('CREATE TABLE IF NOT EXISTS events(id INTEGER PRIMARY KEY,tx TEXT,state TEXT,stamp REAL,error TEXT)')
        self.db.execute('CREATE TABLE IF NOT EXISTS settings(key TEXT PRIMARY KEY,document TEXT)')
        self.db.commit()

    def setting(self, key, default=None):
        row=self.db.execute('SELECT document FROM settings WHERE key=?',(key,)).fetchone()
        return json.loads(row[0]) if row else default

    def save_setting(self,key,value):
        with self.db:self.db.execute('INSERT OR REPLACE INTO settings VALUES (?,?)',(key,json.dumps(value)))

    def create(self, document):
        ident=uuid.uuid4().hex
        with self.db:
            self.db.execute('INSERT INTO transactions VALUES (?,?,?,?)',(ident,'Discovered',json.dumps(document),time.time()))
        return ident

    def get(self, ident):
        row=self.db.execute('SELECT state,document,updated FROM transactions WHERE id=?',(ident,)).fetchone()
        if not row:raise Rejected('Unknown transaction')
        return dict(id=ident,state=row[0],document=json.loads(row[1]),updated=row[2])

    def transition(self,ident,state,patch=None,error=''):
        old=self.get(ident)
        if state not in FAILURES and (old['state'] not in FLOW or FLOW.index(state)!=FLOW.index(old['state'])+1):
            raise Rejected('Invalid transaction transition')
        if old['state'] in TERMINAL:raise Rejected('Transaction already terminal')
        doc=old['document'];doc.update(patch or {})
        if error:doc['error']=error[:300]
        with self.db:
            self.db.execute('UPDATE transactions SET state=?,document=?,updated=? WHERE id=?',(state,json.dumps(doc),time.time(),ident))
            self.db.execute('INSERT INTO events(tx,state,stamp,error) VALUES (?,?,?,?)',(ident,state,time.time(),error[:300]))

    def patch(self,ident,patch):
        row=self.get(ident);doc=row['document'];doc.update(patch)
        with self.db:self.db.execute('UPDATE transactions SET document=?,updated=? WHERE id=?',(json.dumps(doc),time.time(),ident))

    def list(self):
        return [self.get(row[0]) for row in self.db.execute('SELECT id FROM transactions ORDER BY updated DESC LIMIT 100')]

    def interrupted(self):
        for tx in self.list():
            if tx['state'] in TERMINAL or tx['state'] in ('Available','Verified'):continue
            state='Recovery Required' if tx['state'] in ('Preparing','Installing','Health Checking') else 'Cancelled'
            self.transition(tx['id'],state,error='Agent restarted; no installation success assumed. Inspect recovery journal before retrying.')
