import importlib.util
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch
import struct

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from core import Files, Inventory, Registry, capabilities, redact, CATEGORIES


class HardwareTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.fs = Files(self.root)
        self.inv = Inventory(self.fs, run=lambda args, **kw: (127, ''))

    def tearDown(self):
        self.temp.cleanup()

    def write(self, path, text):
        p = self.fs.path(path)
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(text)
        return p

    def row(self, ident, category='wireless', details=None, state='Detected', reason='Detection only'):
        return self.inv.component(category, ident, ident, state=state, details=details, reason=reason)

    def test_goodix_detection_does_not_enable_authentication(self):
        self.write('/sys/bus/platform/devices/soc:goodix_fp/of_node/compatible', 'goodix,fingerprint\0')
        rows = self.inv.sensors()
        row = next(r for r in rows if r['id'] == 'fingerprint:goodix')
        self.assertEqual(row['status'], 'Detected')
        self.assertFalse(row['details']['operational'])
        self.assertFalse(row['details']['verificationSupported'])
        self.assertFalse(row['details']['enrollmentSupported'])

    def test_bound_builtin_not_in_lsmod(self):
        driver = self.root / 'sys/bus/platform/drivers/icnss'
        driver.mkdir(parents=True)
        p = self.root / 'sys/class/net/wlan0/device'
        p.mkdir(parents=True)
        (p / 'driver').symlink_to(driver, target_is_directory=True)
        self.write('/proc/modules', 'unrelated 100 0 - Live 0x0')
        self.assertEqual(self.inv.driver('/sys/class/net/wlan0')['kind'], 'built-in')
        self.assertEqual(self.inv.driver('/sys/class/net/wlan0')['name'], 'icnss')

    def test_loaded_module_is_not_working(self):
        self.write('/sys/class/net/wlan0/wireless/present', '')
        self.write('/sys/class/net/wlan0/operstate', 'up')
        self.write('/proc/modules', 'wlan 100 0 - Live 0x0')
        rows = self.inv.wireless()
        self.assertEqual(rows[0]['status'], 'Detected')
        cap = {x['id']: x for x in capabilities(rows)}['wifi.client']
        self.assertIsNone(cap['operational'])

    def test_absence_is_unknown_not_unsupported(self):
        cap = {x['id']: x for x in capabilities([])}
        self.assertIsNone(cap['camera.capture']['supported'])
        self.assertIsNone(cap['cellular.voice']['operational'])
        self.assertTrue(all(r['status'] == 'Not tested' for r in cap.values()))

    def test_qrtr_loc_advertisement_does_not_verify_fix(self):
        self.inv.run=lambda args,**kw:(0,'16 2 0 0 93 Location service\n') if args==['qrtr-lookup'] else (127,'')
        rows=self.inv.collect('sensors',diagnostic=True)
        cap={r['id']:r for r in capabilities(rows)}['sensors.gnss']
        self.assertTrue(cap['supported']);self.assertIsNone(cap['operational'])
        self.assertEqual(cap['backendProvider'],'com.etherneco.EtherLocation1')

    def test_sensor_framework_does_not_advertise_physical_derived_sensors(self):
        self.write('/usr/share/ethersensors/service.py', '# installed owner')
        rows=self.inv.sensors();cap={r['id']:r for r in capabilities(rows)}
        for kind in ('orientation','gravity','linear_acceleration','rotation_vector'):
            row=cap['sensors.'+kind]
            self.assertFalse(row['physical']);self.assertIsNone(row['supported']);self.assertIsNone(row['operational'])
            self.assertEqual(row['backendProvider'],'com.etherneco.EtherSensors1')

    def test_ambient_light_alias_is_detection_only(self):
        rows=[self.row('iio:fixture','sensors',{'channels':['in_illuminance_raw']})]
        cap={r['id']:r for r in capabilities(rows)}
        self.assertTrue(cap['sensors.ambient_light']['supported']);self.assertIsNone(cap['sensors.ambient_light']['operational'])
        self.assertEqual(cap['sensors.light']['operational'],cap['sensors.ambient_light']['operational'])

    def test_pcm_does_not_verify_physical_audio(self):
        self.write('/dev/snd/pcmC0D0c', '')
        self.write('/dev/snd/pcmC0D0p', '')
        cap = {x['id']: x for x in capabilities(self.inv.audio())}
        self.assertTrue(cap['audio.microphone']['supported'])
        self.assertIsNone(cap['audio.microphone']['operational'])
        self.assertIsNone(cap['audio.speaker']['operational'])

    def test_camera_codec_nodes_do_not_verify_capture(self):
        self.write('/sys/class/video4linux/video0/name', 'Qualcomm video decoder')
        cap = {x['id']: x for x in capabilities(self.inv.camera())}
        self.assertIsNone(cap['camera.capture']['supported'])

    def test_querycap_distinguishes_codec_from_capture_without_streaming(self):
        import fcntl
        for flags, expected in ((0x1, True), (0x1000 | 0x2000 | 0x4000, None)):
            row = self.row('v4l:video0', category='camera')
            def ioctl(fd, request, buffer, mutate):
                self.assertEqual(request, 0x80685600)
                struct.pack_into('=III', buffer, 80, 1, 0x80000000, flags)
            with patch('os.open', return_value=42), patch('os.close'), patch.object(fcntl, 'ioctl', ioctl):
                self.inv.camera_capabilities([row])
            self.assertIs(row['details']['capabilities']['camera.capture']['supported'], expected)
            self.assertIsNone(row['details']['capabilities']['camera.capture']['operational'])

    def test_vendor_profile_never_applies_to_unknown_hardware(self):
        self.write('/proc/device-tree/model', 'Different device')
        self.write('/proc/sys/kernel/osrelease', '4.14.117-perf')
        self.assertEqual(self.inv.vendor_firmware(), [])

    def test_quarantine_overrides_ap_advertisement(self):
        rows = [self.row('nm:wlan0', details={'capabilities': {'wifi.ap': {'supported': True, 'operational': None}}}),
                self.row('share.radio', details={'capabilities': {'wifi.ap': {'supported': None, 'operational': False, 'reason': 'Quarantined'}}}, state='Driver loaded but not operational')]
        cap = {x['id']: x for x in capabilities(rows)}['wifi.ap']
        self.assertFalse(cap['operational'])
        self.assertTrue(cap['supported'])
        self.assertEqual(cap['failureReason'], 'Quarantined')

    def test_redaction_nested_identifiers_paths_and_credentials(self):
        data = redact({'IMEI': '123456789012345', 'nested': [{'token': 'test-secret',
            'evidence': 'aa:bb:cc:dd:ee:ff /home/mobian/private/file password=foo 123456789012345'}]})
        text = json.dumps(data)
        for sensitive in ('123456789012345', 'test-secret', 'aa:bb:cc:dd:ee:ff', 'mobian', 'password=foo'):
            self.assertNotIn(sensitive, text)

    def test_memory_counters_and_cpu_delta(self):
        self.write('/proc/meminfo', 'MemTotal: 8000 kB\nMemAvailable: 3000 kB\nSwapTotal: 2000 kB\nSwapFree: 1000 kB')
        self.assertEqual(self.inv.memory()[0]['details']['totalBytes'], 8192000)
        self.write('/proc/stat', 'cpu 10 0 0 90 0 0 0 0')
        self.assertIsNone(self.inv.processor()[0]['details']['utilisationPercent'])
        self.write('/proc/stat', 'cpu 20 0 0 100 0 0 0 0')
        self.assertEqual(self.inv.processor()[0]['details']['utilisationPercent'], 50)

    def test_firmware_absence_needs_failed_request(self):
        row = self.row('wifi:wlan0')
        row['driver'] = {'module': 'wlan'}
        def run(args, **kw):
            if args[0] == 'modinfo':
                return 0, 'vendor/fw.bin\n'
            return 0, 'Direct firmware load for vendor/fw.bin failed with error -2'
        self.inv.run = run
        self.inv.firmware([row])
        self.assertEqual(row['status'], 'Firmware missing')
        self.write('/lib/firmware/vendor/fw.bin', 'exists')
        row['status'] = 'Detected'
        self.inv.firmware([row])
        self.assertEqual(row['status'], 'Detected')
        self.inv.run = lambda args, **kw: (0, 'vendor/absent.bin') if args[0] == 'modinfo' else (0, '')
        self.inv.firmware([row])
        self.assertNotEqual(row['status'], 'Firmware missing')

    def test_history_removal_restart_and_bound(self):
        reg = Registry(self.root / 'state', self.inv)
        self.inv.wireless = lambda: [self.row('wifi:wlan0')]
        reg.refresh(['wireless'])
        reg.refresh(['wireless'])
        self.assertEqual(len(reg.history()), 1)
        self.inv.wireless = lambda: []
        reg.refresh(['wireless'])
        self.assertEqual(reg.history()[0]['current'], 'Removed')
        reg.db.executemany('INSERT INTO events(timestamp,component,previous,current,reason,metadata) VALUES(?,?,?,?,?,?)',
            [('time', 'sensor', 'A', 'B', 'No personal data', '{}')] * 1100)
        reg.refresh(['wireless'])
        self.assertEqual(reg.db.execute('SELECT COUNT(*) FROM events').fetchone()[0], 1000)
        reg.db.close()
        restarted = Registry(self.root / 'state', self.inv)
        self.assertFalse(restarted.snapshot()['ready'])
        self.assertEqual(restarted.snapshot()['components'], [])
        self.assertTrue(restarted.history('personal', 'sensor'))
        restarted.clear()
        self.assertEqual(restarted.history(), [])
        restarted.db.close()

    def test_all_collectors_tolerate_missing_interfaces(self):
        reg = Registry(self.root / 'state', self.inv)
        report = reg.refresh()
        self.assertEqual(len(report['categories']), len(CATEGORIES))
        self.assertTrue(json.loads(reg.report())['ready'])
        self.assertIn('support report', reg.report('text'))
        with self.assertRaises(ValueError):
            reg.refresh(['not-a-category'])
        with self.assertRaises(ValueError):
            reg.history('x' * 129)
        reg.db.close()


if __name__ == '__main__':
    unittest.main()
