from pathlib import Path
import sys
import unittest
from unittest.mock import patch
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import repair


class RepairTests(unittest.TestCase):
    def fake(self, args, **kw):
        if args[0] == 'dpkg':
            return 0, 'arm64'
        if args[0] == 'dpkg-query':
            return 0, '13.8+deb13u2'
        if args[0] == 'apt-cache':
            return 0, self.policy
        return 0, self.simulation

    def setUp(self):
        self.policy = 'iw:\n  Installed: (none)\n  Candidate: 6.9-1\n  Version table:\n     6.9-1 500\n        500 http://deb.debian.org/debian trixie/main arm64 Packages\n'
        self.simulation = 'Inst iw (6.9-1 Debian:13.7/stable [arm64])\n'
        self.patcher = patch.object(repair, 'command', self.fake)
        self.patcher.start()

    def tearDown(self):
        self.patcher.stop()

    def test_reviewed_debian_plan(self):
        self.assertEqual(repair.plan('iw')['transaction'], [{'package': 'iw', 'version': '6.9-1'}])

    def test_reject_arbitrary_package_or_options(self):
        for package in ('linux-image-arm64', 'firmware-qcom-soc', '../iw', '--allow-unauthenticated', 'iw;id'):
            with self.assertRaises(ValueError):
                repair.plan(package)

    def test_reject_third_party_candidate_even_with_older_debian_version(self):
        self.policy = self.policy.replace('deb.debian.org/debian', 'example.invalid/debian') + '     6.8-1 500\n        500 http://deb.debian.org/debian trixie/main arm64 Packages\n'
        with self.assertRaises(ValueError):
            repair.plan('iw')

    def test_reject_upgrades_removals_and_unreviewed_dependencies(self):
        for text in ('Inst bluez [1] (2 Debian [arm64])', 'Remv iw [6.8-1]',
                     'Inst linux-image-arm64 (1 Debian [arm64])', 'Inst iw [6.8-1] (6.9-1 Debian [arm64])'):
            self.simulation = text
            with self.assertRaises(ValueError):
                repair.plan('iw')
