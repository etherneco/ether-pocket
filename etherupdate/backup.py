"""Mandatory verified pre-update data point via the independently usable backup CLI."""
import json
import subprocess
from security import Rejected

class BackupCoordinator:
    def request(self,transaction,project):
        try:
            p=subprocess.run(['/usr/bin/etherbackup','pre-update',transaction,project],capture_output=True,text=True,timeout=7200)
            if p.returncode:raise ValueError()
            point=json.loads(p.stdout)
            if not point.get('sampleVerified') or not point.get('id') or not point.get('snapshot'):raise ValueError()
            return point
        except (OSError,ValueError,subprocess.TimeoutExpired):
            raise Rejected('Verified EtherBackup recovery point required; commission the component contract and destination before installing') from None

    def result(self,transaction,result):
        try:
            p=subprocess.run(['/usr/bin/etherbackup','update-result',transaction,result],capture_output=True,text=True,timeout=30)
            return dict(recorded=p.returncode==0)
        except (OSError,subprocess.TimeoutExpired):return dict(recorded=False)
