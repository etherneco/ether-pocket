from pathlib import Path
import copy,json,sys,tempfile,time,unittest
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from power import Power,PowerError,Store,DEFAULTS,validate_config,Files


class PowerTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.root=Path(self.temp.name);self.fs=Files(self.root/'linux')
        self.write('/proc/device-tree/model','SDX50M MTP 18827 15');self.write('/proc/sys/kernel/osrelease','4.14.117-perf')
        for ident,maximum in [('policy0',1800000),('policy4',2400000),('policy7',2800000)]:
            p='/sys/devices/system/cpu/cpufreq/'+ident+'/'
            for k,v in {'related_cpus':'0 1','scaling_governor':'performance','scaling_available_governors':'schedutil conservative performance',
                'scaling_available_frequencies':f'300000 600000 900000 1200000 {maximum}',
                'scaling_min_freq':300000,'scaling_max_freq':maximum,'scaling_cur_freq':maximum}.items():self.write(p+k,v)
        gpu='/sys/class/devfreq/2c00000.qcom,kgsl-3d0/'
        for k,v in {'governor':'msm-adreno-tz','available_frequencies':'257000000 345000000 585000000','min_freq':257000000,'max_freq':585000000,'cur_freq':257000000}.items():self.write(gpu+k,v)
        for k,v in {'type':'Battery','status':'Full','capacity':100,'health':'Good','temp':307,'voltage_now':4301000,'current_now':0,'charge_full':3734,'charge_full_design':-22,'cycle_count':0}.items():self.write('/sys/class/power_supply/battery/'+k,v)
        for k,v in {'type':'USB_PD','real_type':'USB','present':1,'online':0,'pd_active':0,'voltage_now':4865,'input_current_now':350670}.items():self.write('/sys/class/power_supply/usb/'+k,v)
        self.write('/sys/power/state','freeze mem');self.write('/sys/power/mem_sleep','s2idle [deep]')
        self.power=Power(self.root/'state',self.fs,run=lambda args,**kw:(0,''))

    def tearDown(self):self.power.store.db.close();self.temp.cleanup()
    def write(self,path,value):
        p=self.fs.path(path);p.parent.mkdir(parents=True,exist_ok=True);p.write_text(str(value));return p

    def test_real_units_and_separate_power_scopes(self):
        d=self.power.telemetry();self.assertEqual(d['voltageV'],4.301);self.assertEqual(d['batteryTemperatureC'],30.7)
        self.assertAlmostEqual(d['usbInputPowerW'],4.865*.350670);self.assertEqual(d['batteryPowerW'],0)
        self.assertIsNone(d['totalDevicePowerW']);self.assertEqual(d['fullCapacityAh'],3.734)
        self.assertIsNone(d['designCapacityAh']);self.assertIsNone(d['healthPercent'])

    def test_vendor_usb_online_false_does_not_mean_disconnected_or_pd(self):
        d=self.power.telemetry();self.assertTrue(d['externalPower']);self.assertFalse(d['supplies'][0]['pdNegotiated'])

    def test_charge_control_limit_is_never_percentage_control(self):
        self.write('/sys/class/power_supply/battery/charge_control_limit',0)
        self.assertFalse(self.power.telemetry()['chargeLimit']['supported'])
        with self.assertRaises(PowerError):self.power.write('/sys/class/power_supply/battery/charge_control_limit',80)

    def test_current_sign_and_charging_power(self):
        self.write('/sys/class/power_supply/battery/status','Charging');self.write('/sys/class/power_supply/battery/current_now',-500000)
        d=self.power.telemetry();self.assertEqual(d['currentA'],-.5);self.assertAlmostEqual(d['batteryChargingPowerW'],2.1505)

    def test_unknown_board_units_remain_unknown(self):
        self.power.board=False;d=self.power.telemetry();self.assertIsNone(d['currentA']);self.assertIsNone(d['fullCapacityAh'])
        with self.assertRaises(PowerError):self.power.apply('balanced')
        with self.assertRaises(PowerError):self.power.restore_original()

    def test_unknown_thermal_zone_is_not_cpu_temperature(self):
        self.write('/sys/class/thermal/thermal_zone0/type','pm8150l-vph-lvl1');self.write('/sys/class/thermal/thermal_zone0/temp',274000)
        self.write('/sys/class/thermal/thermal_zone1/type','cpu-0-1-usr');self.write('/sys/class/thermal/thermal_zone1/temp',45000)
        d=self.power.telemetry();self.assertEqual(d['cpuTemperatureC'],45);self.assertIsNone(d['thermalZones'][0]['temperatureC'])

    def test_runtime_requires_battery_only_stable_samples(self):
        d=self.power.telemetry();self.assertIsNone(self.power.estimate(d,0)['current'])
        d.update(status='Discharging',externalPower=False,currentA=.2,capacity=50)
        self.assertIsNone(self.power.estimate(d,0)['current']);self.assertIsNone(self.power.estimate(d,60)['current'])
        self.assertEqual(self.power.estimate(d,120)['current']['minutes'],560)
        d['externalPower']=True;self.assertIsNone(self.power.estimate(d,180)['current']);self.assertEqual(self.power.runtime_samples,[])

    def test_three_profiles_apply_supported_values_and_restore_original(self):
        for mode,governor in [('balanced','schedutil'),('power-saver','conservative'),('performance','performance')]:
            self.power.apply(mode);self.assertTrue(all(p['governor']==governor for p in self.power.controls()['cpu']))
            self.assertEqual(self.power.effective_name(self.power.controls()),mode)
        self.power.restore_original();self.assertIsNone(self.power.store.config['requestedProfile'])
        self.assertEqual(self.power.controls()['gpu']['governor'],'msm-adreno-tz')

    def test_profile_failure_restores_every_prior_value(self):
        before=self.power.controls();write=self.power.write;failed=[False]
        def fail(path,value):
            if 'policy4/scaling_governor' in path and not failed[0]:failed[0]=True;raise PowerError('Injected rejection')
            write(path,value)
        self.power.write=fail
        with self.assertRaises(PowerError):self.power.apply('balanced')
        self.assertEqual(self.power.controls(),before);self.assertIsNone(self.power.store.config['requestedProfile'])

    def test_custom_rejects_paths_unlisted_frequencies_and_overclock(self):
        for custom in ({'cpu':{'../../etc/passwd':{}}},{'cpu':{'policy0':{'maxKHz':999999}}},
                       {'gpuMaxHz':999999999},{'cpu':{'policy0':{'governor':'fake'}}},[],{'command':'reboot'}):
            with self.assertRaises(PowerError):self.power.apply('custom',custom)

    def test_readback_detects_external_policy_changes(self):
        self.power.apply('balanced');self.write('/sys/devices/system/cpu/cpufreq/policy0/scaling_governor','performance')
        d=self.power.refresh();self.assertEqual(d['profileState']['requested'],'balanced');self.assertEqual(d['profileState']['effective'],'externally-modified')

    def test_threshold_order_and_unsafe_config_rejected(self):
        for changes in ({'thresholds':{'low':5,'critical':10,'emergency':20}},{'batteryTimeout':17},
                        {'thermalWarningC':200},{'suspendPolicy':'force'},{'command':'sh'},{'requestedProfile':'performance'}):
            with self.assertRaises(PowerError):self.power.configure(changes)

    def test_warning_only_on_transition_and_no_forced_shutdown(self):
        self.write('/sys/class/power_supply/usb/present',0);self.write('/sys/class/power_supply/battery/status','Discharging')
        self.write('/sys/class/power_supply/battery/capacity',9)
        self.power.refresh();self.power.refresh();self.assertEqual([e['kind'] for e in self.power.events],['BatteryCritical'])
        self.power.configure({'emergencyAction':'request-shutdown'});self.write('/sys/class/power_supply/battery/capacity',4)
        self.power.refresh();self.assertIn('ShutdownRequested',[e['kind'] for e in self.power.events])

    def test_suspend_advertisement_never_bypasses_wake_gate(self):
        d=self.power.suspend();self.assertFalse(d['verified']);self.assertEqual(d['effective'],'blocked');self.assertIn('No RTC wakealarm',d['error'])
        self.assertIn('Not polled',d['current']['wakeupCount'])

    def test_configuration_and_original_controls_survive_restart(self):
        self.power.apply('power-saver');self.power.configure({'batteryTimeout':30})
        self.power.store.db.close();self.power=Power(self.root/'state',self.fs)
        self.assertEqual(self.power.requested,'power-saver');self.assertEqual(self.power.store.config['batteryTimeout'],30)
        self.assertEqual(self.power.original['cpu'][0]['governor'],'performance')

    def test_history_is_compact_aggregated_bounded_and_persistent(self):
        sample=self.power.telemetry();sample['hugeTechnicalDocument']='x'*100000
        for i in range(300):self.power.store.record(sample,time.time()-10000+i)
        stored=self.power.store.db.execute('SELECT document FROM samples LIMIT 1').fetchone()[0]
        self.assertNotIn('hugeTechnicalDocument',stored);self.assertLess(len(stored),1000)
        self.assertLessEqual(len(self.power.store.history(24)),240)
        self.power.store.record(sample,time.time()-31*86400);self.power.store.record(sample)
        self.assertEqual(self.power.store.db.execute('SELECT COUNT(*) FROM samples WHERE timestamp<?',(time.time()-30*86400,)).fetchone()[0],0)
        with self.assertRaises(PowerError):self.power.store.history(3)

    def test_no_controls_write_charging_thermal_or_cpu_online(self):
        for path in ('/sys/power/state','/sys/class/thermal/thermal_zone0/mode','/sys/devices/system/cpu/cpu7/online','/dev/ipa','/boot/x'):
            with self.assertRaises(PowerError):self.power.write(path,1)

    def test_competing_owner_blocks_both_manual_and_automatic_changes(self):
        def block():raise PowerError('Another policy owner is active')
        self.power.guard=block;before=self.power.controls()
        with self.assertRaises(PowerError):self.power.apply('balanced')
        self.power.configure({'lowBatteryAction':'power-saver'})
        self.write('/sys/class/power_supply/usb/present',0);self.write('/sys/class/power_supply/battery/capacity',15)
        d=self.power.refresh();self.assertTrue(d['ready']);self.assertEqual(before,self.power.controls())
        self.assertIn('PolicyBlocked',[e['kind'] for e in self.power.events])

    def test_process_impact_is_lazy_and_has_no_energy_model(self):
        d=self.power.process_impact(99999);self.assertTrue(d['ready']);self.assertEqual(d['processes'],[])
        self.assertIn('not measured electrical energy',d['scope'])


if __name__=='__main__':unittest.main()
