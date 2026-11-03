import pathlib
import sys
import tempfile
import unittest
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))
from core import Credentials, Denied


class Tests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.path = pathlib.Path(self.temp.name) / 'store'
        self.now = 1000
        self.primary_calls = []
        def primary(uid, proof):
            self.primary_calls.append(uid)
            return proof == 'system-proof'
        self.primary = primary
        self.store = Credentials(self.path, primary, lambda: self.now)

    def tearDown(self):
        self.store.db.close()
        self.temp.cleanup()

    def request(self, operation, kind='pin', proof='system-proof', **fields):
        return self.store.request(1000, dict(operation=operation, kind=kind, proof=proof, **fields))

    def enroll(self, kind='pin', secret='738194'):
        return self.request('set', kind, new=secret, confirmation=secret)

    def test_enroll_change_remove(self):
        self.enroll()
        self.request('prefer')
        self.request('verify', proof='738194')
        self.enroll(secret='916284')
        with self.assertRaises(Denied): self.request('verify', proof='738194')
        self.now += 301
        self.request('verify', proof='916284')
        self.assertEqual(self.request('remove')['preferred'], 'system')
        self.assertFalse(self.request('status')['pin'])

    def test_unauthorized_change_and_remove(self):
        self.enroll()
        for op in ['set', 'remove', 'prefer']:
            with self.assertRaises(Denied): self.request(op, proof='738194', new='123456', confirmation='123456')
            self.now += 301
        self.request('verify', proof='738194')

    def test_failed_enrollment_preserves_previous(self):
        self.enroll()
        with self.assertRaises(Denied): self.request('set', new='916284', confirmation='916285')
        self.request('verify', proof='738194')

    def test_persistent_delay_and_ui_restart(self):
        with self.assertRaises(Denied): self.request('verify', 'system', proof='wrong')
        self.store.db.close()
        self.store = Credentials(self.path, self.primary, lambda: self.now)
        with self.assertRaises(Denied): self.request('verify', 'system')
        self.assertEqual(len(self.primary_calls), 1)
        self.now += 301
        self.request('verify', 'system')
        self.assertEqual(self.request('status')['retryAfter'], 0)

    def test_crash_reservation(self):
        self.store.reserve(1000)
        self.store.db.close()
        self.store = Credentials(self.path, self.primary, lambda: self.now)
        with self.assertRaises(Denied): self.request('verify', 'system')

    def test_unicode_and_no_plaintext(self):
        secret = 'a long passphrase 東京 🔐'
        self.enroll('password', secret)
        self.request('verify', 'password', secret)
        self.assertNotIn(secret.encode(), self.path.read_bytes())
        encoded = self.store.row(1000)['password']
        self.assertTrue(encoded.startswith('$argon2id$'))

    def test_pin_policy_and_no_default(self):
        self.assertFalse(self.request('status')['pin'])
        for pin in ['12345', '１２３４５６', '12345x', '1'*33]:
            with self.assertRaises(Denied): self.enroll(secret=pin)

    def test_method_does_not_delete_credential(self):
        self.enroll()
        self.request('prefer', 'system')
        self.assertTrue(self.request('status')['pin'])
        with self.assertRaises(Denied): self.request('prefer', 'password')
        with self.assertRaises(Denied): self.request('remove', 'system')

    def test_uid_isolation_and_invalid_methods(self):
        self.enroll()
        self.assertFalse(self.store.request(1001, dict(operation='status'))['pin'])
        with self.assertRaises(Denied): self.request('verify', 'fingerprint')
        with self.assertRaises(Denied): self.store.request(0, dict(operation='status'))

    def test_salts_differ(self):
        self.enroll()
        first = self.store.row(1000)['pin']
        self.enroll()
        self.assertNotEqual(first, self.store.row(1000)['pin'])


if __name__ == '__main__':
    unittest.main()
