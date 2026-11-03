import sys
from pathlib import Path
import unittest
from unittest.mock import Mock,patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from backup import BackupCoordinator
from security import Rejected

class CoordinatorTests(unittest.TestCase):
 def test_missing_engine_and_unverified_snapshot_block_update(self):
  for response in (Mock(returncode=1,stdout=''),Mock(returncode=0,stdout='{"sampleVerified":false}')):
   with patch('backup.subprocess.run',return_value=response),self.assertRaises(Rejected):BackupCoordinator().request('tx','project')
  with patch('backup.subprocess.run',side_effect=FileNotFoundError()),self.assertRaises(Rejected):BackupCoordinator().request('tx','project')
 def test_only_verified_reference_is_returned(self):
  with patch('backup.subprocess.run',return_value=Mock(returncode=0,stdout='{"id":"point","snapshot":"hash","sampleVerified":true}')) as run:
   self.assertEqual(BackupCoordinator().request('tx','project')['id'],'point')
   self.assertEqual(run.call_args.args[0],['/usr/bin/etherbackup','pre-update','tx','project'])
 def test_outcome_failure_retains_recovery_protection(self):
  with patch('backup.subprocess.run',side_effect=FileNotFoundError()):self.assertFalse(BackupCoordinator().result('tx','healthy')['recorded'])
