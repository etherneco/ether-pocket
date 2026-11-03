"""Serialized backup, verification, retention and isolated restore orchestration."""
from contextlib import nullcontext
from datetime import datetime,timezone
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import tempfile
import time
import uuid
from adapter import Restic
from destinations import inspect
from security import BackupError, atomic, identifier, lock, private, relative
from sources import SourceRegistry, digest, validate_database

def now():return datetime.now(timezone.utc).isoformat()

def retention_candidates(rows,policy,stamp=None):
    """Keep protected/update points, newest verified per profile, and calendar buckets."""
    stamp=stamp or time.time();keep=set();groups={}
    for row in rows:
        if row.get('protected') or (row.get('updateTransaction') and row.get('updateResult')!='healthy') or row.get('holdUntil',0)>stamp:keep.add(row['id'])
        groups.setdefault(row['profile'],[]).append(row)
    for items in groups.values():
        items.sort(key=lambda x:x['created'],reverse=True)
        verified=next((r for r in items if r.get('sampleVerified')),None)
        if verified:keep.add(verified['id'])
        for unit,count in [('daily',policy.get('daily',7)),('weekly',policy.get('weekly',4)),('monthly',policy.get('monthly',6))]:
            buckets=set()
            for r in items:
                dt=datetime.fromisoformat(r['created'])
                bucket=dt.strftime({'daily':'%Y-%m-%d','weekly':'%G-%V','monthly':'%Y-%m'}[unit])
                if bucket not in buckets and len(buckets)<max(1,int(count)):
                    buckets.add(bucket);keep.add(r['id'])
    return [r['id'] for r in rows if r['id'] not in keep]

class Core:
    def __init__(self,directory,config,engine_factory=Restic,safety=None,inhibit=None,metadata=None,notify=None):
        self.directory=private(directory);self.config=config;self.registry=SourceRegistry(config);self.engine_factory=engine_factory
        self.safety=safety or (lambda:dict(allowed=False,reason='Power state unavailable'))
        self.inhibit=inhibit or nullcontext;self.metadata=metadata or (lambda:{})
        self.notify=notify or (lambda event:None);self.progress={}
        self.last_guard=0
        for name in ('cache','work','restores'):private(self.directory/name)
        self.index=self.directory/'index.json';self.statefile=self.directory/'state.json'
        if not self.index.exists():atomic(self.index,dict(schema=1,points=[]))
        if not self.statefile.exists():atomic(self.statefile,dict(status='Recovery not tested'))

    def records(self):return json.loads(self.index.read_text())['points']
    def save(self,rows):atomic(self.index,dict(schema=1,points=rows))
    def point(self,ident):
        identifier(ident)
        row=next((r for r in self.records() if r['id']==ident and not r.get('deleted')),None)
        if not row:raise BackupError('Unknown recovery point')
        return row
    def engine(self,name, reserve=64*1024**2):
        identifier(name)
        if name not in self.config['destinations']:raise BackupError('Destination not commissioned')
        config=self.config['destinations'][name];status=inspect(config,reserve)
        def progress(p):
            self.guard();self.progress.update(p)
        return self.engine_factory(config,self.directory/'cache',status['options'],progress),status

    def guard(self):
        if time.monotonic()-self.last_guard<10:return
        safety=self.safety()
        if not safety.get('allowed'):raise BackupError(safety.get('reason','Backup deferred by power policy'))
        self.last_guard=time.monotonic()

    def status(self,details=False):
        state=json.loads(self.statefile.read_text());rows=self.records();live=[r for r in rows if not r.get('deleted')]
        verified=[r for r in live if r.get('sampleVerified')];last=verified[-1] if verified else None
        status=state.get('status','Recovery not tested');destinations=[]
        for name,config in self.config['destinations'].items():
            try:_,d=self.engine(name);available=True
            except Exception:d={};available=False
            destinations.append(dict(id=name,kind=config['kind'],available=available,independent=bool(d.get('independent') and d.get('independenceVerified')),
                                     warning='Keep an independent recovery password; same-device backups cannot survive storage failure' if config['kind']=='local' else 'Test removal/reconnect and recovery from a trusted host'))
        if last and status not in ('Backup failed','Verification failed','Backup running','Restore running','Deferred'):
            dest=next((d for d in destinations if d['id']==last['destination']),{})
            status='Destination unavailable' if not dest.get('available') else 'Backup overdue' if time.time()-datetime.fromisoformat(last['created']).timestamp()>self.config.get('overdueSeconds',172800) else 'Protected' if dest.get('independent') and last.get('independentKeyConfirmed') else 'Recovery not tested'
        if not last and live and status not in ('Backup failed','Verification failed'):status='Verification required'
        result=dict(ready=True,status=status,engine='restic',encrypted=True,fullSystemRecoveryTested=False,
                    lastSuccessfulBackup=live[-1]['created'] if live else None,lastVerifiedBackup=last.get('verifiedAt') if last else None,
                    schedule=self.config.get('schedule',{}),destinations=destinations,profiles=list(self.config['profiles']),progress=self.progress)
        if details:result.update(history=live[-100:][::-1],retention=self.config.get('retention',{}),lastOperation=state,
                                 estimatedProtectedBytes=last.get('bytes',0) if last else 0)
        return result

    def backup(self,profile,destination,components=None,update=None):
        with lock(self.directory/'job.lock'),self.inhibit():
            started=time.monotonic();self.last_guard=0;self.guard();engine,dest=self.engine(destination)
            atomic(self.statefile,dict(status='Backup running',started=now()));self.progress={}
            stage=self.directory/'work'/'stage'
            if stage.exists():shutil.rmtree(stage)
            stage.mkdir(mode=0o700)
            try:
                inventory=self.registry.stage(profile,stage,components,self.guard)
                if not self.config['destinations'][destination]['kind']=='sftp':
                    self.engine(destination,inventory['bytes']+64*1024**2)
                manifest=dict(schema=1,toolVersion='0.1.0',created=now(),profile=profile,inventory=inventory,
                    platform=self.metadata(),restoreOrder=['compatible-signed-releases-via-EtherUpdate','configuration-review','offline-database-restore','personal-data'],
                    encryption='Restic; independent password required',bareMetalRecoveryTested=False)
                atomic(stage/'manifest.json',manifest)
                self.guard();summary=engine.backup(stage,['etherbackup',profile]+(['pre-update'] if update else []))
                snapshot=summary['snapshot_id']
                if not re.fullmatch(r'[0-9a-f]{64}',snapshot):raise BackupError('Invalid committed snapshot identity')
                row=dict(id=uuid.uuid4().hex,snapshot=snapshot,destination=destination,profile=profile,created=manifest['created'],
                         bytes=inventory['bytes'],storedBytes=summary.get('data_added_packed'),durationSeconds=time.monotonic()-started,
                         sampleVerified=False,protected=bool(update),updateTransaction=update,holdUntil=0,
                         manifestPath=str(stage/'manifest.json'),filesPath=str(stage/'files'),manifestSha256=digest(stage/'manifest.json'),
                         missingSources=len(inventory['missing']),skippedSymlinks=len(inventory['skippedSymlinks']),
                         independent=dest['independent'],independentKeyConfirmed=bool(self.config['destinations'][destination].get('independentKeyConfirmed')))
                rows=self.records();rows.append(row);self.save(rows)
                self._verify(row,engine,'sample')
                atomic(self.statefile,dict(status='Verified sample restore',finished=now(),point=row['id']))
                self.notify('recovery-point-created' if update else 'backup-completed')
                return self.point(row['id'])
            except Exception:
                atomic(self.statefile,dict(status='Backup failed',finished=now()));self.notify('backup-failed');raise
            finally:
                shutil.rmtree(stage,ignore_errors=True);self.progress={}

    def _manifest(self,row,engine):
        with tempfile.TemporaryFile() as out:
            engine.dump(row['snapshot'],row['manifestPath'],out)
            if out.tell()>64*1024**2:raise BackupError('Recovery manifest exceeds limit')
            out.seek(0);raw=out.read()
        if hashlib.sha256(raw).hexdigest()!=row['manifestSha256']:raise BackupError('Recovery manifest digest mismatch')
        doc=json.loads(raw)
        if doc.get('schema')!=1 or not isinstance(doc.get('inventory',{}).get('files'),dict):raise BackupError('Unsupported recovery manifest')
        for name,entry in doc['inventory']['files'].items():
            relative(name)
            if not re.fullmatch('[0-9a-f]{64}',entry.get('sha256','')) or type(entry.get('size')) is not int or entry['size']<0:
                raise BackupError('Invalid recovery file metadata')
        return doc

    def _restore_file(self,row,engine,name,entry,target):
        target.parent.mkdir(parents=True,exist_ok=True,mode=0o700)
        # target belongs to a newly created private sandbox; never follows archive links.
        with target.open('xb') as out:engine.dump(row['snapshot'],row['filesPath']+'/'+name,out)
        if target.stat().st_size!=entry['size'] or digest(target)!=entry['sha256']:raise BackupError('Restored file checksum differs')
        if entry.get('sqlite') and not validate_database(target):raise BackupError('Restored database format differs')
        # Isolated output stays private and non-executable until reviewed by an administrator.
        target.chmod(0o600)
        os.utime(target,ns=(entry['mtimeNs'],entry['mtimeNs']))

    def _verify(self,row,engine,level):
        if level not in ('metadata','integrity','sample','drill'):raise BackupError('Unsupported verification level')
        try:
            if not any(s.get('id')==row['snapshot'] for s in engine.snapshots()):raise BackupError('Snapshot missing from repository')
            manifest=self._manifest(row,engine)
            if level!='metadata':engine.check(full=level in ('sample','drill'))
            names=list(manifest['inventory']['files'])
            if level=='sample':
                # Include representative files from every application and every SQLite DB.
                selected=set(n for n,e in manifest['inventory']['files'].items() if e.get('sqlite'))
                contracts={}
                for n,e in manifest['inventory']['files'].items():contracts.setdefault(e['contract'],n)
                selected.update(contracts.values());names=sorted(selected)
            if level in ('sample','drill'):
                with tempfile.TemporaryDirectory(prefix='verify-',dir=self.directory/'work') as folder:
                    for name in names:self._restore_file(row,engine,name,manifest['inventory']['files'][name],Path(folder)/name)
            rows=self.records()
            for item in rows:
                if item['id']==row['id']:
                    item.update(verificationLevel=level,verificationResult='passed',verificationTimestamp=now())
                    if level in ('sample','drill'):item.update(sampleVerified=True,verifiedAt=now(),verifiedFiles=len(names))
                    if level=='drill':item['isolatedFileDrillAt']=now()
            self.save(rows);return dict(passed=True,level=level,restoredFiles=len(names) if level in ('sample','drill') else 0,bareMetal=False)
        except Exception:
            rows=self.records()
            for item in rows:
                if item['id']==row['id']:item.update(sampleVerified=False,verificationResult='failed',verificationTimestamp=now())
            self.save(rows);atomic(self.statefile,dict(status='Verification failed',finished=now()));self.notify('verification-failed');raise

    def verify(self,ident,level='sample'):
        with lock(self.directory/'job.lock'),self.inhibit():
            row=self.point(ident);engine,_=self.engine(row['destination'])
            result=self._verify(row,engine,level)
            atomic(self.statefile,dict(status='Verification completed',finished=now(),point=ident));return result

    def preview(self,ident,prefix=''):
        with lock(self.directory/'job.lock'):
            row=self.point(ident);engine,_=self.engine(row['destination']);manifest=self._manifest(row,engine)
            if prefix:relative(prefix)
            files={n:e for n,e in manifest['inventory']['files'].items() if not prefix or n==prefix or n.startswith(prefix+'/')}
            if not files:raise BackupError('No files match the selection')
            return dict(point=ident,selection=prefix,files=files,totalBytes=sum(e['size'] for e in files.values()),
                        mode='Isolated private destination only; original files are never overwritten',bareMetal=False)

    def restore(self,ident,prefix,confirmed=False):
        if not confirmed:raise BackupError('Explicit restore confirmation required')
        preview=self.preview(ident,prefix)
        with lock(self.directory/'job.lock'),self.inhibit():
            row=self.point(ident);engine,_=self.engine(row['destination'])
            if shutil.disk_usage(self.directory).free<preview['totalBytes']+64*1024**2:raise BackupError('Insufficient restore space')
            folder=private(self.directory/'restores'/uuid.uuid4().hex)
            atomic(self.statefile,dict(status='Restore running',started=now(),point=ident))
            try:
                for name,entry in preview['files'].items():self._restore_file(row,engine,name,entry,folder/name)
                atomic(folder/'restore-report.json',dict(point=ident,finished=now(),files=preview['files'],originalsOverwritten=False))
                atomic(self.statefile,dict(status='Restore completed',finished=now(),point=ident));self.notify('restore-completed')
                return dict(destination=str(folder),files=len(preview['files']),validated=True,originalsOverwritten=False)
            except Exception:
                atomic(self.statefile,dict(status='Restore failed',finished=now(),point=ident));raise

    def protect(self,ident,protected=True):
        with lock(self.directory/'job.lock'):
            self.point(ident);rows=self.records()
            for row in rows:
                if row['id']==ident:row['protected']=bool(protected)
            self.save(rows)

    def retain(self,destination):
        with lock(self.directory/'job.lock'),self.inhibit():
            self.guard();rows=self.records();active=[r for r in rows if r['destination']==destination and not r.get('deleted')]
            if not active or not active[-1].get('sampleVerified'):raise BackupError('Newest backup must pass sample restore before cleanup')
            engine,_=self.engine(destination);self._verify(active[-1],engine,'sample')
            ids=retention_candidates(active,self.config.get('retention',{}));byid={r['id']:r for r in active}
            engine.forget([byid[i]['snapshot'] for i in ids])
            rows=self.records()
            for r in rows:
                if r['id'] in ids:r['deleted']=now()
            self.save(rows)
            if ids:engine.prune()
            return dict(removed=len(ids),lastVerifiedPreserved=True)

    def update_result(self,transaction,result):
        if result not in ('healthy','failed','rolled-back'):raise BackupError('Unknown update result')
        with lock(self.directory/'job.lock'):
            rows=self.records();found=False
            for r in rows:
                if r.get('updateTransaction')==transaction:
                    found=True;r['updateResult']=result
                    if result=='healthy':r.update(protected=False,holdUntil=time.time()+self.config.get('updateSafetySeconds',30*86400))
                    else:r['protected']=True
            if not found:raise BackupError('No recovery point for update')
            self.save(rows)
        return dict(recorded=True,automaticDatabaseRollback=False)

    def recovery_info(self,ident):
        with lock(self.directory/'job.lock'):
            row=self.point(ident);engine,_=self.engine(row['destination']);doc=self._manifest(row,engine)
            return dict(point=row,manifest=doc,instructions='Use independent Restic password and trusted Linux host. Restore to empty private directory. Validate checksums and SQLite integrity. Review schema compatibility with EtherUpdate before applying data. No bootable image or tested bare-metal recovery is provided.')
