import importlib.util
import json
from pathlib import Path
import sys
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

SCRIPTS = Path(__file__).resolve().parent.parent / 'scripts'
sys.path.insert(0, str(SCRIPTS))
import ethermobile_data_status as status


class StatusTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.boot = self.root/'boot'; self.boot.write_text('boot-a')
        self.patches = [patch.object(status, 'PATH', self.root/'status.json'), patch.object(status, 'BOOT', self.boot)]
        for p in self.patches: p.start(); self.addCleanup(p.stop)

    def test_progress_history_and_connection_preserved(self):
        status.update('registration', 'Czekam na sieć', reset=True)
        status.update('registration', 'Czekam na sieć')
        status.update('session', 'Zestawiam sesję')
        status.update('connected', 'Połączono', state='connected', pid=42)
        self.assertEqual(len(status.read()['history']), 3)
        self.assertEqual(status.read()['pid'], 42)
        self.assertEqual(status.read()['state'], 'connected')

    def test_failure_keeps_stage_but_never_raw_error_or_credentials(self):
        status.update('format', 'Uzgadniam QMAP', reset=True)
        status.failure(RuntimeError('password=supersecret IMSI=123456789'))
        data = status.read()
        self.assertEqual(data['stage'], 'format')
        self.assertEqual(data['state'], 'failed')
        self.assertNotIn('supersecret', json.dumps(data))
        self.assertNotIn('123456789', json.dumps(data))

    def test_qmi_code_and_safe_reason(self):
        error = RuntimeError('private request'); error.code = 14
        error.safe_detail = 'get_verbose_call_end_reason=3,1069'
        status.failure(error)
        self.assertEqual(status.read()['code'], 'QMI_14')
        self.assertIn('1069', status.read()['detail'])

    def test_previous_boot_is_not_an_active_connection(self):
        status.update('connected', 'Połączono', state='connected')
        self.boot.write_text('boot-b')
        self.assertEqual(status.read(), {})

    def test_cleanup_keeps_failure(self):
        status.update('session', 'Łączę', reset=True)
        status.failure(TimeoutError())
        before = status.read()
        with patch.dict('os.environ', {'SERVICE_RESULT':'exit-code'}): status.finish_unit()
        self.assertEqual(status.read(), before)

    def test_normal_stop_and_systemd_timeout(self):
        status.update('connected', 'Połączono', state='connected')
        with patch.dict('os.environ', {'SERVICE_RESULT':'success'}): status.finish_unit()
        self.assertEqual(status.read()['state'], 'disconnected')
        status.update('registration', 'Rejestracja', reset=True)
        with patch.dict('os.environ', {'SERVICE_RESULT':'timeout'}): status.finish_unit()
        self.assertEqual(status.read()['code'], 'SERVICE_TIMEOUT')

    def test_history_is_bounded(self):
        for i in range(35): status.update(str(i), str(i))
        self.assertEqual(len(status.read()['history']), 20)

    def waiter(self):
        spec=importlib.util.spec_from_file_location('data_wait',SCRIPTS/'ethermobile-data-wait.py')
        module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
        return module

    def test_sim_lock_produces_actionable_error_without_pin_attempt(self):
        wait=self.waiter()
        modem={'modem':{'generic':{'unlock-required':'sim-pin'},'3gpp':{}}}
        with patch.object(wait,'Path') as path,patch.object(wait.subprocess,'run',return_value=SimpleNamespace(returncode=0,stdout=json.dumps(modem))) as run:
            path.return_value.read_text.return_value='GM1920-548cb338-mobian-sda21'
            with self.assertRaises(wait.ConnectionFailure) as error:wait.main()
            self.assertEqual(error.exception.status_code,'SIM_LOCKED')
            self.assertEqual(run.call_count,1)
            self.assertIn('PIN',error.exception.safe_detail)

    def test_competing_network_owner_is_reported_at_timeout(self):
        wait=self.waiter()
        modem={'modem':{'generic':{},'3gpp':{'registration-state':'home','packet-service-state':'attached'}}}
        responses=[SimpleNamespace(returncode=0,stdout=json.dumps(modem)),SimpleNamespace(returncode=0,stdout='50 (connecting)')]
        with patch.object(wait,'Path') as path,patch.object(wait.subprocess,'run',side_effect=responses),patch.object(wait.time,'monotonic',side_effect=[0,0,121]),patch.object(wait.time,'sleep'):
            path.return_value.read_text.return_value='GM1920-548cb338-mobian-sda21'
            with self.assertRaises(wait.ConnectionFailure) as error:wait.main()
            self.assertIn('NetworkManager zajmuje modem',error.exception.safe_detail)
            self.assertEqual(status.read()['stage'],'network_owner')

    def test_roaming_is_rejected_without_starting_data(self):
        wait=self.waiter()
        modem={'modem':{'generic':{},'3gpp':{'registration-state':'roaming'}}}
        with patch.object(wait,'Path') as path,patch.object(wait.subprocess,'run',return_value=SimpleNamespace(returncode=0,stdout=json.dumps(modem))) as run:
            path.return_value.read_text.return_value='GM1920-548cb338-mobian-sda21'
            with self.assertRaises(wait.ConnectionFailure) as error:wait.main()
            self.assertEqual(error.exception.status_code,'ROAMING_BLOCKED')
            self.assertEqual(run.call_count,1)


if __name__ == '__main__': unittest.main()
