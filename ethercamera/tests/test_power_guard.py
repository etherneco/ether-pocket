import datetime
from pathlib import Path
import sys
import unittest
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from power_guard import recording_guard

class RecordingPowerTests(unittest.TestCase):
    def state(self):
        return dict(ready=True,timestamp=datetime.datetime.now(datetime.timezone.utc).isoformat(),capacity=75.,cpuTemperatureC=40.,batteryTemperatureC=30.,gpuTemperatureC=35.)

    def test_normal_validated_power_and_missing_optional_gpu(self):
        state=self.state();self.assertEqual(recording_guard(state),'');state.pop('gpuTemperatureC');self.assertEqual(recording_guard(state),'')

    def test_temperature_and_battery_limits(self):
        for field,value,reason in [('cpuTemperatureC',85,'Thermal recording limit'),('gpuTemperatureC',85,'Thermal recording limit'),('batteryTemperatureC',45,'Thermal recording limit'),('capacity',5,'Battery recording limit')]:
            state=self.state();state[field]=value;self.assertEqual(recording_guard(state),reason)

    def test_stale_missing_and_malformed_values_fail_closed(self):
        state=self.state();now=datetime.datetime.now(datetime.timezone.utc)
        state['timestamp']=(now-datetime.timedelta(seconds=181)).isoformat();self.assertEqual(recording_guard(state,now),'Power telemetry stale')
        for field,value in [('ready',False),('capacity',True),('cpuTemperatureC',float('nan')),('timestamp','invalid'),('batteryTemperatureC',None),('gpuTemperatureC','unknown')]:
            state=self.state();state[field]=value;self.assertTrue(recording_guard(state))
        self.assertTrue(recording_guard({}));self.assertTrue(recording_guard(None))
