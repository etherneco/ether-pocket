import json
import pathlib
import sys
import tempfile
import unittest
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))
from core import DEFAULTS, CHECKS, LockState, Events, policy, accepted, locker_environment


class SecurityTests(unittest.TestCase):
    def test_enable_requires_every_gate(self):
        for check in CHECKS:
            evidence = dict.fromkeys(CHECKS, True); evidence[check] = False
            self.assertFalse(accepted(evidence))
        with self.assertRaises(ValueError): policy(DEFAULTS, {'enabled': True})
        self.assertTrue(policy(DEFAULTS, {'enabled': True}, True)['enabled'])

    def test_policy_rejects_bypass_fields_and_invalid_types(self):
        for patch in ({'unlock': True}, {'timeout': True}, {'timeout': -1}, {'timeout': 86401},
                      {'enabled': 'yes'}, {'privacy': 'invalid'}, {'lockOnScreenOff': 0}):
            with self.assertRaises(ValueError): policy(DEFAULTS, patch, True)

    def test_supported_timeouts(self):
        for timeout in (0, 15, 30, 60, 300, 777):
            self.assertEqual(policy(DEFAULTS, {'timeout': timeout})['timeout'], timeout)

    def test_process_start_and_early_clean_exit_are_not_enforcement(self):
        state = LockState(); state.request()
        self.assertFalse(state.enforced); self.assertTrue(state.private)
        self.assertFalse(state.exited(0)); self.assertEqual(state.phase, 'fault')

    def test_locker_crash_never_reports_unlocked(self):
        for code in (-9, -11, 1, 2):
            state = LockState(); state.request(); state.ready()
            self.assertFalse(state.exited(code)); self.assertTrue(state.private)
            self.assertFalse(state.enforced)

    def test_success_requires_preceding_enforcement(self):
        state = LockState(); state.request(); state.ready()
        self.assertTrue(state.exited(0)); self.assertFalse(state.private)

    def test_restart_is_unknown_and_private(self):
        state = LockState(True)
        self.assertEqual(state.phase, 'unknown'); self.assertTrue(state.private)
        with self.assertRaises(ValueError): state.request()

    def test_environment_strips_auth_and_command_injection(self):
        env = locker_environment({'DISPLAY': ':0', 'LD_PRELOAD': 'evil',
            'XSECURELOCK_AUTH': '/tmp/true', 'XSECURELOCK_DEBUG_ALLOW_LOCKING_IF_INEFFECTIVE': '1',
            'XSECURELOCK_KEY_F1_COMMAND': 'evil', 'QT_PLUGIN_PATH': '/tmp'})
        self.assertEqual(env['DISPLAY'], ':0'); self.assertEqual(env['XSECURELOCK_AUTH'], '/usr/lib/etherlock/auth_etherlock')
        for k in ('LD_PRELOAD', 'XSECURELOCK_KEY_F1_COMMAND', 'QT_PLUGIN_PATH', 'XSECURELOCK_DEBUG_ALLOW_LOCKING_IF_INEFFECTIVE'):
            self.assertNotIn(k, env)

    def test_event_retention_and_redacted_export(self):
        with tempfile.TemporaryDirectory() as directory:
            store = Events(directory)
            for _ in range(1005): store.add('locked')
            self.assertEqual(len(store.export()), 1000)
            self.assertEqual(set(store.export()[0]), {'timestamp', 'event'})
            with self.assertRaises(ValueError): store.add('password=secret')


if __name__ == '__main__': unittest.main()
