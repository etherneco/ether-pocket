import ast
import importlib.util
from pathlib import Path
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('fingerprint_core', ROOT/'core.py')
core = importlib.util.module_from_spec(spec)
spec.loader.exec_module(core)


class SecurityTests(unittest.TestCase):
    def test_missing_hardware_never_grants_capabilities(self):
        with tempfile.TemporaryDirectory() as folder:
            p = core.DiagnosticProvider(folder)
            s = p.status()
            self.assertEqual(s['state'], 'Not tested')
            self.assertFalse(s['detected'])
            self.assertIsNone(s['enrolledCount'])
            self.assertIsNone(s['enrollments'])
            self.assertFalse(s['canList'])
            self.assertTrue(s['securityPolicy']['primaryCredentialRequired'])
            self.assertFalse(s['securityPolicy']['fingerprintUnlockAvailable'])
            for field in ['operational','enabled','canEnroll','canVerify','canManage','illuminationSupported']:
                self.assertIs(s[field], False)

    def test_presence_is_not_authentication(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            device = root/'sys/bus/platform/devices/soc:goodix_fp/of_node'
            device.mkdir(parents=True)
            (device/'compatible').write_bytes(b'goodix,fingerprint\0')
            (root/'dev').mkdir()
            (root/'dev/goodix_fp').touch()
            (root/'dev/qseecom').touch()
            p = core.DiagnosticProvider(folder)
            s = p.status()
            self.assertTrue(s['detected'])
            self.assertTrue(s['secureTransportNodePresent'])
            self.assertFalse(s['secureServiceAvailable'])
            self.assertFalse(s['canVerify'])
            self.assertEqual(s['state'], 'Blocked')
            for operation in (p.enroll, p.verify, p.manage):
                for request in ({}, {'match':True,'nonce':'replayed','uid':0}):
                    with self.assertRaises(core.BackendUnavailable):
                        operation(**request)
            self.assertIsNone(p.cancel())

    def test_dbus_has_no_mutation_or_success_surface(self):
        tree = ast.parse((ROOT/'service.py').read_text())
        exposed = []
        for node in ast.walk(tree):
            if isinstance(node, ast.FunctionDef):
                for decorator in node.decorator_list:
                    if isinstance(decorator, ast.Call) and isinstance(decorator.func, ast.Attribute):
                        self.assertNotEqual(decorator.func.attr, 'signal')
                        if decorator.func.attr == 'method': exposed.append(node.name)
        self.assertEqual(sorted(exposed), ['GetCapabilities','GetState'])


if __name__ == '__main__':
    unittest.main()
