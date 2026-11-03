"""Restic adapter. Encryption and repository format are owned entirely by Restic."""
import json
import os
from pathlib import Path
import selectors
import subprocess
import time
from security import BackupError, credential

class Restic:
    def __init__(self,config,cache,options=(),progress=None,binary='/usr/bin/restic'):
        self.config=config;self.cache=str(cache);self.options=list(options);self.progress=progress or (lambda p:None);self.binary=binary

    def command(self,args):
        return [self.binary,'--repo',self.config['repository'],'--password-file',credential(self.config['passwordFile']),
                '--cache-dir',self.cache,'--compression','auto','--limit-upload',str(self.config.get('uploadKiB',2048)),*self.options,*args]

    def run(self,args,timeout=3600,output=None):
        env={'PATH':'/usr/sbin:/usr/bin:/sbin:/bin','LANG':'C.UTF-8','HOME':'/root','GOMAXPROCS':'2','GOGC':'50','GODEBUG':'asyncpreemptoff=1'}
        start=time.monotonic();records=[];pending=b'';total=0
        with subprocess.Popen(self.command(args),stdout=output or subprocess.PIPE,stderr=subprocess.DEVNULL,env=env,start_new_session=True) as p:
            try:
                if output:
                    while p.poll() is None:
                        if time.monotonic()-start>timeout:raise BackupError('Backup engine timed out')
                        self.progress({})
                        try:p.wait(timeout=1)
                        except subprocess.TimeoutExpired:pass
                else:
                    selector=selectors.DefaultSelector();selector.register(p.stdout,selectors.EVENT_READ)
                    try:
                        while selector.get_map():
                            self.progress({})
                            if time.monotonic()-start>timeout:raise BackupError('Backup engine timed out')
                            for key,_ in selector.select(1):
                                data=os.read(key.fileobj.fileno(),65536)
                                if not data:selector.unregister(key.fileobj);continue
                                total+=len(data)
                                if total>64*1024**2:raise BackupError('Repository response exceeds limit')
                                pending+=data
                                if len(pending)>4*1024**2:raise BackupError('Repository record exceeds limit')
                                while b'\n' in pending:
                                    line,pending=pending.split(b'\n',1)
                                    try:doc=json.loads(line)
                                    except ValueError:continue
                                    if isinstance(doc,dict) and doc.get('message_type')=='status':
                                        self.progress({k:doc[k] for k in ('percent_done','files_done','total_files','bytes_done','total_bytes','seconds_elapsed') if k in doc})
                                    else:records.append(doc)
                        if pending.strip():records.append(json.loads(pending))
                    finally:selector.close()
                    p.wait(timeout=10)
                if p.returncode:raise BackupError('Restic operation failed; verify destination, credentials and repository (no automatic unlock)')
            except BaseException:
                import signal
                os.killpg(p.pid,signal.SIGKILL) if p.poll() is None else None
                p.wait();raise
        return records

    def init(self):self.run(['init','--repository-version','2'],120)
    def snapshots(self):
        rows=self.run(['snapshots','--json'],120)
        return rows[0] if rows else []
    def backup(self,stage,tags):
        docs=self.run(['backup','--json','--host','etherpocket','--tag',','.join(tags),'--',str(stage)])
        summary=next((r for r in docs if isinstance(r,dict) and r.get('message_type')=='summary'),None)
        if not summary or not summary.get('snapshot_id'):raise BackupError('Snapshot was not committed')
        return summary
    def check(self,full=False):self.run(['check']+(['--read-data'] if full else []),7200)
    def dump(self,snapshot,path,output):self.run(['dump',snapshot,path],output=output)
    def forget(self,ids):
        if ids:self.run(['forget',*ids],120)
    def prune(self):self.run(['prune','--max-unused','5%'],7200);self.check()
