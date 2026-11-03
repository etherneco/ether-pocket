"""Measure a real disposable fixture and export its actual UI state, never keys."""
from pathlib import Path
import json,runpy
ROOT=Path(__file__).resolve().parent.parent
remote=runpy.run_path(str(ROOT/'scripts/verify-etherupdate-device.py'))['remote']
if __name__=='__main__':
 source=r'''
import json,os,pathlib,resource,sqlite3,subprocess,sys,tempfile,time
assert pathlib.Path('/etc/etherpocket/disk-identity').read_text().strip()=='GM1920-548cb338-mobian-sda21'
sys.path.insert(0,'/usr/share/etherbackup')
from core import Core
from platform_state import power,inhibit,capture
with tempfile.TemporaryDirectory(prefix='etherbackup-benchmark-',dir='/root') as folder:
 root=pathlib.Path(folder);source=root/'source';source.mkdir()
 (source/'personal-document.txt').write_text('EtherBackup isolated recovery benchmark\n')
 with (source/'media-sample.bin').open('wb') as f:f.write(os.urandom(8*1024**2))
 db=sqlite3.connect(source/'settings.sqlite');db.execute('CREATE TABLE settings(key TEXT,value TEXT)');db.execute("INSERT INTO settings VALUES ('theme','dark')");db.commit();db.close()
 key=root/'password';key.write_text(os.urandom(32).hex());key.chmod(0o600)
 contract=dict(paths=[str(source)],exclude=[],consistency='files-and-sqlite-online',secrets='explicit-paths-only',schemaVersions=[0])
 config=dict(profiles=dict(personal=['benchmark'],applications=['benchmark']),sources={'benchmark':contract},destinations={'isolated-local-test':dict(kind='local',repository=str(root/'repo'),passwordFile=str(key))})
 c=Core(root/'state',config,safety=power,inhibit=inhibit,metadata=capture)
 e,_=c.engine('isolated-local-test');e.init()
 before=power();start=time.monotonic();first=c.backup('personal','isolated-local-test');first_seconds=time.monotonic()-start
 (source/'personal-document.txt').write_text('Changed benchmark version\n')
 start=time.monotonic();second=c.backup('personal','isolated-local-test');incremental_seconds=time.monotonic()-start
 start=time.monotonic();restore=c.restore(first['id'],'',True);restore_seconds=time.monotonic()-start
 target=pathlib.Path(restore['destination'])/str(source).lstrip('/')
 assert (target/'personal-document.txt').read_text()=='EtherBackup isolated recovery benchmark\n'
 data=dict(fixtureBytes=first['bytes'],firstBackupAndFullVerificationSeconds=first_seconds,incrementalAndFullVerificationSeconds=incremental_seconds,
  restoreSeconds=restore_seconds,firstStoredBytes=first['storedBytes'],incrementalStoredBytes=second['storedBytes'],
  childPeakRSSKiB=resource.getrusage(resource.RUSAGE_CHILDREN).ru_maxrss,childUserCPUSeconds=resource.getrusage(resource.RUSAGE_CHILDREN).ru_utime,
  childSystemCPUSeconds=resource.getrusage(resource.RUSAGE_CHILDREN).ru_stime,chargingBefore=before.get('charging'),chargingAfter=power().get('charging'),
  batteryImpactMeasured=False,networkTransferMeasured=False,productionBackup=False,validationState=c.status(True))
 print(json.dumps(data))
'''
 result=json.loads(remote(source,timeout=180))
 (ROOT/'evidence/etherbackup-benchmark.json').write_text(json.dumps(result,indent=2)+'\n',encoding='utf-8')
 print(json.dumps({k:v for k,v in result.items() if k!='validationState'},indent=2))
