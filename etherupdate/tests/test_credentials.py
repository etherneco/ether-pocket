import json
import os
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import Mock,patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from credentials import CredentialStore,read_descriptor,validate
from agent import Agent
from provider import ProviderError
from security import Rejected

# Deliberately invalid, synthetic test data; no live credential is used.
SAMPLE='synthetic_test_value_1234567890'


class CredentialTest(unittest.TestCase):
    def agent(self):
        a=object.__new__(Agent);a.provider=Mock();a.provider.token='previous_test_value'
        a.plans={'approval':{}};a.credential_validated_at=None;a.history=Mock()
        return a

    def test_reject_url_whitespace_and_oversize_without_echo(self):
        for value in ('https://example.invalid?token='+SAMPLE,SAMPLE+'\n','short','x'*4097):
            with self.assertRaises(Rejected) as context:validate(value)
            self.assertNotIn(value,str(context.exception))

    @unittest.skipUnless(os.name=='posix','Unix FD transfer')
    def test_pipe_input_and_empty_pipe_never_block(self):
        reader,writer=os.pipe()
        try:
            with self.assertRaises(Rejected):read_descriptor(reader)
            os.write(writer,SAMPLE.encode());os.close(writer);writer=None
            self.assertEqual(read_descriptor(reader),SAMPLE)
        finally:
            os.close(reader)
            if writer is not None:os.close(writer)

    def test_authentication_failure_preserves_previous_credential(self):
        a=self.agent();store=Mock();candidate=Mock();candidate.json.side_effect=ProviderError('Authentication failed')
        with patch('agent.Provider',return_value=candidate),self.assertRaises(Rejected) as context:a.set_credential(SAMPLE,store)
        store.save.assert_not_called();self.assertEqual(a.provider.token,'previous_test_value')
        self.assertNotIn(SAMPLE,str(context.exception))

    def test_success_updates_only_after_validation_and_storage(self):
        a=self.agent();store=Mock();candidate=Mock();candidate.json.return_value={'data':[]}
        with patch('agent.Provider',return_value=candidate):result=a.set_credential(SAMPLE,store)
        candidate.json.assert_called_once_with('/api/manage/projects?page=1');store.save.assert_called_once_with(SAMPLE)
        self.assertEqual(a.provider.token,SAMPLE);self.assertEqual(a.plans,{})
        self.assertNotIn(SAMPLE,json.dumps(result))

    def test_failed_storage_preserves_running_credential(self):
        a=self.agent();store=Mock();store.save.side_effect=OSError('Disk full');candidate=Mock();candidate.json.return_value={'data':[]}
        with patch('agent.Provider',return_value=candidate),self.assertRaises(OSError):a.set_credential(SAMPLE,store)
        self.assertEqual(a.provider.token,'previous_test_value')

    def test_remove_writes_disable_override(self):
        a=self.agent();store=Mock();result=a.remove_credential(store)
        store.save.assert_called_once_with('');self.assertEqual(a.provider.token,'');self.assertEqual(a.plans,{})
        self.assertEqual(result,{'removed':True})

    @unittest.skipUnless(os.name=='posix' and os.geteuid()==0,'Root-owned Linux credential store')
    def test_store_permissions_restart_removal_and_symlink_refusal(self):
        # Use a protected root under /var/tmp: /tmp itself is world writable and
        # is correctly rejected by the production parent-directory policy.
        with tempfile.TemporaryDirectory(prefix='etherupdate-credential-',dir='/root') as folder:
            store=CredentialStore(Path(folder)/'credentials')
            self.assertIsNone(store.load());store.save(SAMPLE)
            self.assertEqual(store.path.stat().st_mode & 0o777,0o600)
            self.assertEqual(store.directory.stat().st_mode & 0o777,0o700)
            self.assertEqual(CredentialStore(store.directory).load(),SAMPLE)
            store.save('');self.assertEqual(store.load(),'')
            store.path.unlink();store.path.symlink_to('/etc/passwd')
            with self.assertRaises(OSError):store.load()
