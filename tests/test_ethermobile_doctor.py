import importlib.util
import unittest
from pathlib import Path

spec=importlib.util.spec_from_file_location('doctor',Path(__file__).resolve().parents[1]/'scripts/ethermobile-doctor.py')
doctor=importlib.util.module_from_spec(spec)
spec.loader.exec_module(doctor)

class DoctorTest(unittest.TestCase):
    def test_sensitive_fields(self):
        value=doctor.redact('androidboot.serialno=secret ICCID: 8944123456789012345 IMEI=123456789012345 64:a2:f9:fa:d3:43 PIN=1234')
        for secret in ['secret','8944123456789012345','123456789012345','64:a2:f9:fa:d3:43','1234']:
            self.assertNotIn(secret,value)

    def test_no_atr_is_not_success(self):
        evidence={'qmi':{'revision':{'exit':0},'card':{'output':"Card state: 'error: no-atr-received (3)'"},'registration':{'output':"Registration state: 'not-registered-searching'"}},
                  'hardware':{},'kernel':{},'subsystems':[],'cellular_interfaces':[],'ipa_firmware':[], 'qrtr':{},'links':{},'addresses':{},'routes':{}}
        stages=doctor.stages(evidence)
        by_name={s['stage']:s for s in stages}
        self.assertEqual(len(stages),12)
        self.assertEqual(by_name['SIM detection']['status'],'Blocked')
        self.assertEqual(by_name['Network registration']['status'],'Blocked')
        self.assertEqual(by_name['End-to-end cellular connectivity']['status'],'Blocked')

    def test_missing_command_is_not_hardware_failure(self):
        result=doctor.run(['ethermobile-command-that-does-not-exist'])
        self.assertEqual(result['status'],'Missing')
        self.assertIsNone(result['exit'])

if __name__=='__main__':unittest.main()
