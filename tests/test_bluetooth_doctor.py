import importlib.util
from pathlib import Path
import unittest

spec = importlib.util.spec_from_file_location('doctor', Path(__file__).resolve().parents[1]/'scripts/etherbluetooth-doctor.py')
doctor = importlib.util.module_from_spec(spec)
spec.loader.exec_module(doctor)


class DoctorTests(unittest.TestCase):
    def checks(self, config=None, hci=None, rfkill=None):
        return {row['stage']: row for row in doctor.classify(config or {}, hci or [], {'output': 'active\n'}, rfkill or [])}

    def test_bluez_without_controller_is_not_ready(self):
        checks = self.checks({'CONFIG_BT': 'y', 'CONFIG_BT_HCIUART': 'n'})
        self.assertEqual(checks['BlueZ service']['status'], 'Working')
        self.assertEqual(checks['HCI registration']['status'], 'Missing')
        self.assertEqual(checks['Discovery test']['status'], 'Blocked')
        self.assertEqual(checks['Kernel transport']['status'], 'Missing')

    def test_unreadable_config_is_unknown(self):
        self.assertEqual(self.checks()['Kernel transport']['status'], 'Unknown')

    def test_built_in_driver_is_not_missing(self):
        self.assertNotEqual(self.checks({'CONFIG_BT_HCIUART': 'y'})['Kernel transport']['status'], 'Missing')

    def test_hardware_block(self):
        self.assertEqual(self.checks(rfkill=[{'soft': '0', 'hard': '1'}])['Bluetooth power']['status'], 'Blocked')

    def test_controller_presence_does_not_claim_discovery_test(self):
        self.assertEqual(self.checks(hci=['hci0'])['Discovery test']['status'], 'Unknown')

    def test_twelve_diagnostic_stages(self):
        self.assertEqual(len(self.checks()), 12)

    def test_external_driver_overrides_disabled_in_tree_transport(self):
        rows = doctor.classify({'CONFIG_BT_HCIUART': 'n'}, ['hci0'], {'output': 'active'}, [],
                              external={'loaded': True, 'runtime': {'host_firmware_uploaded': False}})
        checks = {row['stage']: row for row in rows}
        self.assertEqual(checks['Kernel transport']['status'], 'Working')
        self.assertEqual(checks['Firmware availability']['status'], 'Partially working')


if __name__ == '__main__':
    unittest.main()
