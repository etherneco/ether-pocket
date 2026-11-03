"""Exercise teardown with failed modem replies, without touching hardware."""
import importlib.util
from pathlib import Path
import sys
import tempfile
import types
import unittest
from unittest.mock import MagicMock, patch


class CleanupTests(unittest.TestCase):
    def test_failed_qmi_stop_still_removes_link_and_releases_every_client(self):
        gi=types.ModuleType('gi');gi.require_version=lambda *args:None
        repo=types.ModuleType('gi.repository')
        repo.GLib=MagicMock();repo.Qmi=MagicMock();repo.Qrtr=MagicMock()
        spec=importlib.util.spec_from_file_location('data_under_test',Path(__file__).resolve().parents[1]/'scripts/ethermobile-ipa-data.py')
        module=importlib.util.module_from_spec(spec)
        with patch.dict(sys.modules,{'gi':gi,'gi.repository':repo}):spec.loader.exec_module(module)
        calls=[]
        clients=[MagicMock() for _ in range(3)];device=MagicMock()
        def invoke(*args):
            calls.append('qmi')
            raise RuntimeError('simulated disconnected bearer')
        with tempfile.TemporaryDirectory() as folder:
            state=Path(folder)/'state.json';state.write_text('{}')
            with patch.object(module.subprocess,'run',side_effect=lambda args,**kwargs:calls.append(args)),patch.object(module,'call',side_effect=invoke):
                module.cleanup_data(state,True,123,*clients,device)
            self.assertFalse(state.exists())
        self.assertIn(['ip','link','delete','epcell0'],calls)
        self.assertLess(calls.index(['ip','link','delete','epcell0']),calls.index('qmi'))
        self.assertEqual(calls.count('qmi'),4)

    def test_foreign_interface_is_not_removed(self):
        gi=types.ModuleType('gi');gi.require_version=lambda *args:None
        repo=types.ModuleType('gi.repository');repo.GLib=MagicMock();repo.Qmi=MagicMock();repo.Qrtr=MagicMock()
        spec=importlib.util.spec_from_file_location('data_under_test',Path(__file__).resolve().parents[1]/'scripts/ethermobile-ipa-data.py')
        m=importlib.util.module_from_spec(spec)
        with patch.dict(sys.modules,{'gi':gi,'gi.repository':repo}):spec.loader.exec_module(m)
        with tempfile.TemporaryDirectory() as folder,patch.object(m.subprocess,'run') as run,patch.object(m,'call'):
            m.cleanup_data(Path(folder)/'missing',False,None,MagicMock(),MagicMock(),MagicMock(),MagicMock())
        self.assertFalse(any('delete' in c.args[0] for c in run.call_args_list))


if __name__=='__main__':unittest.main()
