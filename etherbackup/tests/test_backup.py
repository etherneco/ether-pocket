"""Real encrypted engine integration tests; no production data or repositories."""
from contextlib import nullcontext
from datetime import datetime,timezone,timedelta
import copy
import json
import os
from pathlib import Path
import shutil
import sqlite3
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from adapter import Restic
from core import Core,retention_candidates
from destinations import inspect
from security import BackupError,atomic,credential,lock,open_source,relative
from sources import SourceRegistry,digest,validate_database

def contract(paths):return dict(paths=[str(p) for p in paths],exclude=[],consistency='files-and-sqlite-online',secrets='explicit-paths-only',schemaVersions=[1],prepare='sqlite-online',complete='close',restoreValidation='integrity')

@unittest.skipUnless(shutil.which('restic'),'Real Restic required')
class BackupTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp=tempfile.TemporaryDirectory(prefix='etherbackup-tests-',dir=Path.home());cls.root=Path(cls.temp.name)
        cls.key=cls.root/'password';cls.key.write_text(os.urandom(32).hex()+'\n');cls.key.chmod(0o600)
        cls.dest=dict(kind='local',repository=str(cls.root/'repo'),passwordFile=str(cls.key))
        cls.engine=Restic(cls.dest,cls.root/'cache',binary=shutil.which('restic'));cls.engine.init()
    @classmethod
    def tearDownClass(cls):cls.temp.cleanup()
    def setUp(self):
        self.work=Path(tempfile.mkdtemp(dir=self.root));self.source=self.work/'source';self.source.mkdir()
        self.file=self.source/'personal.txt';self.file.write_text('original data\n');self.file.chmod(0o640)
        self.config=dict(sources={'test-app':contract([self.source])},profiles=dict(personal=['test-app'],applications=['test-app']),
                         destinations={'test':self.dest},retention=dict(daily=7,weekly=4,monthly=6),
                         updateComponents={'test-project':['test-app']},updateDestination='test')
        self.core=Core(self.work/'state',self.config,safety=lambda:dict(allowed=True,charging=True),metadata=lambda:dict(kernel='test',bareMetalRecoveryTested=False))
    def point(self):return self.core.backup('personal','test')
    def test_encrypted_incremental_and_original_restore(self):
        old=self.point();self.file.write_text('changed\n');new=self.point()
        self.assertNotEqual(old['snapshot'],new['snapshot']);self.assertTrue(old['sampleVerified'])
        preview=self.core.preview(old['id'],str(self.file).lstrip('/'))
        self.assertEqual(len(preview['files']),1)
        restored=self.core.restore(old['id'],str(self.file).lstrip('/'),True)
        target=Path(restored['destination'])/str(self.file).lstrip('/')
        self.assertEqual(target.read_text(),'original data\n');self.assertEqual(self.file.read_text(),'changed\n')
        manifest=self.core.recovery_info(old['id'])['manifest']
        self.assertNotIn(self.key.read_text().strip(),json.dumps(manifest))
        self.assertEqual(target.stat().st_mtime_ns,preview['files'][str(self.file).lstrip('/')]['mtimeNs'])
        self.assertEqual(target.stat().st_mode&0o777,0o600)
        self.assertFalse(self.core.status()['status']=='Protected')
    def test_wal_online_backup_with_live_writer(self):
        db=sqlite3.connect(self.source/'active.unusual');self.addCleanup(db.close)
        db.execute('PRAGMA journal_mode=WAL');db.execute('CREATE TABLE records(value TEXT)');db.execute("INSERT INTO records VALUES ('committed')");db.commit()
        db.execute('BEGIN IMMEDIATE');db.execute("INSERT INTO records VALUES ('uncommitted')")
        row=self.point();result=self.core.restore(row['id'],'',True)
        target=Path(result['destination'])/str(self.source/'active.unusual').lstrip('/')
        with sqlite3.connect(target) as restored:self.assertEqual(restored.execute('SELECT * FROM records').fetchall(),[('committed',)])
        self.assertTrue(validate_database(target));db.rollback()
    def test_wrong_password_refused(self):
        key=self.work/'wrong';key.write_text(os.urandom(32).hex());key.chmod(0o600)
        adapter=Restic(dict(self.dest,passwordFile=str(key)),self.work/'cache',binary=shutil.which('restic'))
        with self.assertRaises(BackupError):adapter.snapshots()
    def test_explicit_confirmation_and_safe_paths(self):
        row=self.point()
        with self.assertRaises(BackupError):self.core.restore(row['id'],'',False)
        for path in ('../etc/shadow','/etc/passwd','a/../b','a//b','a\\b'):
            with self.subTest(path=path),self.assertRaises(BackupError):self.core.preview(row['id'],path)
    def test_symlinks_and_special_files_excluded(self):
        (self.source/'link').symlink_to('/etc/shadow');(self.source/'directory').symlink_to('/etc',target_is_directory=True)
        os.mkfifo(self.source/'fifo')
        row=self.point();files=self.core.preview(row['id'])['files']
        self.assertEqual(len(files),1);self.assertEqual(row['skippedSymlinks'],3)
    def test_parent_symlink_rejected(self):
        link=self.work/'alias';link.symlink_to(self.source,target_is_directory=True)
        self.config['sources']['test-app']['paths']=[str(link/'personal.txt')]
        with self.assertRaises(BackupError):self.point()
    def test_missing_sources_not_reported_operational(self):
        self.config['sources']['test-app']['paths']=[str(self.source/'absent')]
        with self.assertRaises(BackupError):self.point()
        self.assertFalse(any(r.get('sampleVerified') for r in self.core.records()))
    def test_corrupted_or_missing_pack_detected(self):
        # Independent repository so deliberate damage cannot affect other tests.
        repo=self.work/'damage-repo';self.config['destinations']['damage']=dict(self.dest,repository=str(repo))
        engine,_=self.core.engine('damage');engine.init();row=self.core.backup('personal','damage')
        packs=list((repo/'data').rglob('*'));pack=next(p for p in packs if p.is_file());pack.unlink()
        with self.assertRaises(BackupError):self.core.verify(row['id'],'sample')
        self.assertFalse(self.core.point(row['id'])['sampleVerified'])
        self.assertEqual(self.core.status()['status'],'Verification failed')
    def test_metadata_does_not_grant_sample_verification(self):
        row=self.point();records=self.core.records();records[0]['sampleVerified']=False;self.core.save(records)
        self.core.verify(row['id'],'metadata');self.assertFalse(self.core.point(row['id'])['sampleVerified'])
    def test_drill_restores_all_files_without_claiming_bare_metal(self):
        (self.source/'other').write_text('other')
        result=self.core.verify(self.point()['id'],'drill')
        self.assertEqual(result['restoredFiles'],2);self.assertFalse(result['bareMetal'])
    def test_preupdate_contract_and_safety_period(self):
        row=self.core.backup('applications','test',['test-project'],'transaction-123')
        self.assertTrue(row['protected']);self.assertTrue(row['sampleVerified'])
        self.core.update_result('transaction-123','healthy');row=self.core.point(row['id'])
        self.assertGreater(row['holdUntil'],__import__('time').time()+86400);self.assertFalse(row['protected'])
        with self.assertRaises(BackupError):self.core.backup('applications','test',['unmapped'],'tx')
    def test_power_failure_defers_before_snapshot(self):
        self.core.safety=lambda:dict(allowed=False,reason='Low battery')
        with self.assertRaisesRegex(BackupError,'Low battery'):self.point()
        self.assertEqual(self.core.records(),[])
    def test_overlap_rejected(self):
        with lock(self.core.directory/'job.lock'),self.assertRaises(BackupError):self.point()
    def test_manifest_tamper_rejected(self):
        row=self.point();rows=self.core.records();rows[0]['manifestSha256']='0'*64;self.core.save(rows)
        with self.assertRaises(BackupError):self.core.preview(row['id'])
    def test_retention_requires_fresh_sample_and_preserves_last_verified(self):
        row=self.point();self.assertEqual(self.core.retain('test')['removed'],0)
        rows=self.core.records();rows[-1]['sampleVerified']=False;self.core.save(rows)
        with self.assertRaises(BackupError):self.core.retain('test')
    def test_backup_size_limit(self):
        self.config['maxStageBytes']=2
        with self.assertRaises(BackupError):self.point()
    def test_repository_and_credential_inside_source_are_excluded(self):
        password=self.source/'private-password';password.write_text(os.urandom(32).hex());password.chmod(0o600)
        repo=self.source/'nested-repository'
        self.config['destinations']['nested']=dict(self.dest,repository=str(repo),passwordFile=str(password))
        engine,_=self.core.engine('nested');engine.init()
        row=self.core.backup('personal','nested');files=self.core.preview(row['id'])['files']
        self.assertEqual(list(files),[str(self.file).lstrip('/')])

class PolicyTests(unittest.TestCase):
    def test_usb_commission_requires_real_mounted_usb(self):
        from destinations import usb_configuration
        with patch('destinations.usb_candidates',return_value=[]),self.assertRaises(BackupError):usb_configuration('usb','/mnt/backup')
        with patch('destinations.usb_candidates',return_value=[dict(mounts=['/mnt/backup'],uuid='real-id')]),patch('destinations.os.path.ismount',return_value=True):
            result=usb_configuration('usb','/mnt/backup')
        self.assertEqual(result['uuid'],'real-id');self.assertFalse(result['independentKeyConfirmed'])
        with self.assertRaises(BackupError):usb_configuration('../bad','/mnt/backup')
    def test_calendar_retention_and_protected_point(self):
        start=datetime(2026,1,1,tzinfo=timezone.utc)
        rows=[dict(id=str(i),profile='personal',created=(start+timedelta(days=i)).isoformat(),sampleVerified=i==1,protected=i==0) for i in range(100)]
        ids=retention_candidates(rows,dict(daily=7,weekly=4,monthly=2))
        self.assertNotIn('0',ids);self.assertNotIn('1',ids);self.assertNotIn('99',ids);self.assertIn('2',ids)
    def test_disconnected_usb_does_not_use_root_disk(self):
        from unittest.mock import patch
        with patch('destinations.credential'),self.assertRaises(BackupError):inspect(dict(kind='usb',repository='/mnt/missing/repo',mount='/mnt/missing',passwordFile='/ignored',uuid='123'))
    def test_remote_requires_pinned_alias_and_host_key_config(self):
        with patch('destinations.credential'):
            for repo in ('https://autoupddate.etherneco.com','sftp:user@host:/repo','sftp:alias:/../repo'):
                with self.subTest(repo=repo),self.assertRaises(BackupError):inspect(dict(kind='sftp',repository=repo,passwordFile='/ignored'))
    def test_schedule_defers_and_checks_selected_wifi(self):
        from platform_state import scheduled_allowed
        with self.assertRaises(BackupError):scheduled_allowed({},dict(charging=True))
        with self.assertRaises(BackupError):scheduled_allowed(dict(schedule=dict(enabled=True,chargingOnly=True)),dict(charging=False))
        self.assertTrue(scheduled_allowed(dict(schedule=dict(enabled=True,chargingOnly=True)),dict(charging=True))['enabled'])
    def test_unknown_contract_consistency_fails_closed(self):
        config=dict(profiles=dict(personal=['app']),sources=dict(app=dict(consistency='blind-sqlite-copy')))
        with self.assertRaises(BackupError):SourceRegistry(config).contracts('personal')

if __name__=='__main__':unittest.main()
