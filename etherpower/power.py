"""EtherPower policy, telemetry and transactional controls. No charging/safety writes."""
import copy
import datetime as dt
import hashlib
import json
import math
import os
from pathlib import Path
import re
import sqlite3
import sys
import time

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'etherhardware'))
from core import Files, command, redact

PROFILES = ('balanced', 'power-saver', 'performance', 'custom')
TIMEOUTS = (0, 15, 30, 60, 120, 300)
DEFAULTS = dict(schemaVersion=1, requestedProfile=None, thresholds={'low': 20, 'critical': 10, 'emergency': 5},
    lowBatteryAction='notify', emergencyAction='notify', batteryTimeout=60, externalTimeout=300,
    saverBrightness=25, externalDisplayPolicy='preserve-session', monitorSeconds=60,
    thermalWarningC=80, batteryWarningC=45, thermalAction='notify',
    powerButton='short-blank-long-menu', suspendPolicy='verified-only', custom={})


class PowerError(Exception):
    pass


def utc():
    return dt.datetime.now(dt.timezone.utc).isoformat()


def number(value, minimum=None, maximum=None):
    try:
        result = float(value)
        if not math.isfinite(result) or minimum is not None and result < minimum or maximum is not None and result > maximum:
            return None
        return result
    except (TypeError, ValueError):
        return None


def feature(supported, current=None, requested=None, effective=None, error=None):
    return {'supported': supported, 'state': 'Supported' if supported is True else 'Unsupported' if supported is False else 'Not tested',
            'current': current, 'requested': requested, 'effective': effective, 'error': error}


class Store:
    def __init__(self, directory):
        self.root = Path(directory)
        self.root.mkdir(parents=True, exist_ok=True)
        self.config = copy.deepcopy(DEFAULTS)
        self.migration = None
        path = self.root / 'config.json'
        if path.exists():
            try:
                raw = json.loads(path.read_text())
                if raw.get('schemaVersion', 0) not in (0, 1):
                    raise PowerError('Unknown configuration schema; automatic writes disabled')
                if raw.get('schemaVersion', 0) == 0:
                    self.migration = 'Migrated legacy preferences to schema 1'
                    raw['schemaVersion'] = 1
                self.config.update(raw)
                validate_config(self.config)
            except (ValueError, OSError) as e:
                raise PowerError('Power configuration is invalid; preserved for recovery') from e
        self.db = sqlite3.connect(self.root / 'history.sqlite', check_same_thread=False)
        self.db.execute('CREATE TABLE IF NOT EXISTS samples (timestamp REAL PRIMARY KEY, document TEXT NOT NULL)')
        self.db.execute('CREATE TABLE IF NOT EXISTS events (id INTEGER PRIMARY KEY, timestamp REAL, kind TEXT, document TEXT)')

    def save(self, document):
        validate_config(document)
        temp = self.root / 'config.json.new'
        with temp.open('w', encoding='utf-8') as f:
            json.dump(document, f, indent=2)
            f.flush()
            os.fsync(f.fileno())
        if json.loads(temp.read_text()) != document:
            raise PowerError('Configuration verification failed')
        temp.replace(self.root / 'config.json')
        self.config = copy.deepcopy(document)

    def record(self, sample, stamp=None):
        stamp = time.time() if stamp is None else stamp
        fields = ('capacity', 'status', 'externalPower', 'batteryPowerW', 'usbInputPowerW', 'batteryTemperatureC',
                  'cpuTemperatureC', 'gpuTemperatureC', 'cpuUtilisationPercent', 'brightnessPercent', 'profile',
                  'currentA', 'fullCapacityAh')
        document = {k: sample.get(k) for k in fields}
        self.db.execute('INSERT OR REPLACE INTO samples VALUES(?,?)', (stamp, json.dumps(redact(document))))
        self.db.execute('DELETE FROM samples WHERE timestamp<?', (stamp - 30 * 86400,))
        self.db.execute('DELETE FROM samples WHERE timestamp < (SELECT timestamp FROM samples ORDER BY timestamp DESC LIMIT 1 OFFSET 86399)')
        self.db.commit()

    def event(self, kind, data):
        self.db.execute('INSERT INTO events(timestamp,kind,document) VALUES(?,?,?)', (time.time(), kind, json.dumps(redact(data))))
        self.db.execute('DELETE FROM events WHERE id NOT IN (SELECT id FROM events ORDER BY id DESC LIMIT 1000)')
        self.db.commit()

    def history(self, hours):
        if hours not in (1, 24, 168, 720):
            raise PowerError('History range must be 1, 24, 168 or 720 hours')
        rows = self.db.execute('SELECT timestamp,document FROM samples WHERE timestamp>=? ORDER BY timestamp', (time.time() - hours * 3600,)).fetchall()
        # Bin, rather than discard, samples for bounded rendering over long ranges.
        stride = max(1, math.ceil(len(rows) / 240))
        results = []
        for pos in range(0, len(rows), stride):
            group = rows[pos:pos + stride]
            values = [json.loads(r[1]) for r in group]
            row = {'timestamp': group[-1][0], 'samples': len(group)}
            for key in ('capacity', 'batteryPowerW', 'usbInputPowerW', 'batteryTemperatureC', 'cpuTemperatureC', 'gpuTemperatureC', 'cpuUtilisationPercent', 'brightnessPercent'):
                available = [v[key] for v in values if isinstance(v.get(key), (int, float))]
                row[key] = sum(available) / len(available) if available else None
            row['profile'] = values[-1].get('profile')
            row['powerScope'] = 'Battery terminal power and USB input estimate are separate; no total-device watts'
            results.append(row)
        return results


def validate_config(config):
    if set(config) != set(DEFAULTS) or config['schemaVersion'] != 1:
        raise PowerError('Unknown configuration keys or schema')
    if config['requestedProfile'] not in (None, *PROFILES):
        raise PowerError('Invalid profile')
    t = config['thresholds']
    if not isinstance(t, dict) or set(t) != {'low', 'critical', 'emergency'} or not all(type(v) is int for v in t.values()) or not 1 <= t['emergency'] < t['critical'] < t['low'] <= 90:
        raise PowerError('Thresholds must satisfy 1 <= emergency < critical < low <= 90')
    if config['lowBatteryAction'] not in ('notify', 'power-saver') or config['emergencyAction'] not in ('notify', 'request-shutdown'):
        raise PowerError('Invalid battery action')
    if config['batteryTimeout'] not in TIMEOUTS or config['externalTimeout'] not in TIMEOUTS:
        raise PowerError('Unsupported screen timeout')
    if type(config['saverBrightness']) is not int or not 5 <= config['saverBrightness'] <= 100:
        raise PowerError('Brightness must be 5–100%')
    if type(config['monitorSeconds']) is not int or not 30 <= config['monitorSeconds'] <= 300:
        raise PowerError('Monitoring interval must be 30–300 seconds')
    for key, low, high in [('thermalWarningC', 60, 95), ('batteryWarningC', 35, 50)]:
        if type(config[key]) is not int or not low <= config[key] <= high:
            raise PowerError('Thermal warning is outside the conservative configurable range')
    if config['thermalAction'] not in ('notify', 'power-saver') or config['externalDisplayPolicy'] not in ('preserve-session', 'allow-blank'):
        raise PowerError('Invalid thermal or external-display policy')
    if config['powerButton'] != 'short-blank-long-menu' or config['suspendPolicy'] != 'verified-only':
        raise PowerError('Unverified button/suspend policies are unavailable')
    if not isinstance(config['custom'], dict) or set(config['custom']) - {'cpu', 'gpuMaxHz'}:
        raise PowerError('Unsupported custom profile fields')


class Power:
    def __init__(self, directory, files=None, run=command):
        self.fs = files or Files()
        self.run = run
        self.store = Store(directory)
        self.board = (self.fs.read('/proc/device-tree/model') == 'SDX50M MTP 18827 15' and
                      self.fs.read('/proc/sys/kernel/osrelease') == '4.14.117-perf')
        self.original = None
        self.error = None
        self.guard = lambda: None
        self.applied = None
        self.requested = self.store.config['requestedProfile']
        self.events = []
        self.last_alert = None
        self.thermal_alert = False
        self.last_external = None
        self.last_charging = None
        self.cpu_sample = None
        self.network_sample = None
        self.runtime_samples = []
        self.process_samples = {}
        self.data = {}
        self.registry = {'ready': False, 'capabilities': []}
        self.last_history = 0
        baseline = self.store.root / 'original-controls.json'
        fingerprint = {'model': self.fs.read('/proc/device-tree/model'), 'kernel': self.fs.read('/proc/sys/kernel/osrelease')}
        if baseline.exists():
            document = json.loads(baseline.read_text())
            if document.get('fingerprint') == fingerprint:
                self.original = document['controls']
            else:
                raise PowerError('Control baseline belongs to another kernel/device; maintenance required')
        else:
            self.original = self.controls()
            baseline.write_text(json.dumps({'fingerprint': fingerprint, 'controls': self.original}, indent=2))

    def controls(self):
        f = self.fs
        cpu = []
        for p in f.glob('/sys/devices/system/cpu/cpufreq/policy*'):
            cpu.append(dict(id=p.rsplit('/', 1)[1], path=p,
                cores=f.read(p + '/related_cpus'), governor=f.read(p + '/scaling_governor'),
                governors=f.read(p + '/scaling_available_governors').split(),
                frequenciesKHz=[int(v) for v in f.read(p + '/scaling_available_frequencies').split() if v.isdigit()],
                minKHz=number(f.read(p + '/scaling_min_freq'), 0), maxKHz=number(f.read(p + '/scaling_max_freq'), 0),
                currentKHz=number(f.read(p + '/scaling_cur_freq'), 0)))
        gpu = None
        for p in f.glob('/sys/class/devfreq/*kgsl-3d0'):
            gpu = dict(path=p, governor=f.read(p + '/governor'),
                frequenciesHz=[int(v) for v in f.read(p + '/available_frequencies').split() if v.isdigit()],
                minHz=number(f.read(p + '/min_freq'), 0), maxHz=number(f.read(p + '/max_freq'), 0),
                currentHz=number(f.read(p + '/cur_freq'), 0),
                utilisation=f.read('/sys/class/kgsl/kgsl-3d0/gpubusy') or None)
        return {'cpu': cpu, 'gpu': gpu}

    def telemetry(self):
        f = self.fs
        base = '/sys/class/power_supply/battery/'
        read = lambda key: f.read(base + key)
        status = read('status') or None
        capacity = number(read('capacity'), 0, 100)
        voltage = number(read('voltage_now'), 0)
        current = number(read('current_now'))
        # Error sentinels are not electrical readings. Negative current may be real.
        if current in (-22, -61, -5):
            current = None
        voltage = voltage / 1e6 if voltage is not None else None
        amperes = current / 1e6 if self.board and current is not None else None
        temperature = number(read('temp'), -300, 800)
        temperature = temperature / 10 if temperature is not None else None
        full = number(read('charge_full'), 1)
        design = number(read('charge_full_design'), 1)
        # External BQ gauge reports full capacity in mAh on the matched kernel.
        full_ah = full / 1000 if self.board and full is not None else None
        design_ah = design / 1e6 if design is not None else None
        supplies = []
        for p in f.glob('/sys/class/power_supply/*'):
            if f.read(p + '/type') in ('Battery', 'BMS'):
                continue
            r = {key: f.read(p + '/' + key) or None for key in ('type', 'present', 'online', 'status', 'real_type',
                'voltage_now', 'current_now', 'input_current_now', 'current_max', 'pd_active', 'typec_mode', 'typec_power_role', 'health', 'connector_health', 'moisture_detected')}
            r['name'] = p.rsplit('/', 1)[1]
            uv = number(r['voltage_now'], 0)
            r['voltageV'] = uv / (1000 if self.board and r['name'] == 'usb' else 1e6) if uv is not None else None
            ua = number(r['input_current_now'], 0)
            r['inputCurrentA'] = ua / 1e6 if ua is not None else None
            r['estimatedInputPowerW'] = r['voltageV'] * r['inputCurrentA'] if r['voltageV'] is not None and ua is not None else None
            r['pdNegotiated'] = r['pd_active'] == '1' if r['pd_active'] in ('0', '1') else None
            supplies.append(r)
        external = any(r['present'] == '1' or r['online'] == '1' for r in supplies)
        usb = next((r for r in supplies if r['name'] == 'usb'), {})
        zones, cpu_temps, gpu_temps = [], [], []
        for p in f.glob('/sys/class/thermal/thermal_zone*'):
            kind = f.read(p + '/type')
            raw = number(f.read(p + '/temp'))
            mapped = self.board and (bool(re.fullmatch(r'cpu-[0-9]+-[0-9]+-(?:usr|step)', kind)) or kind == 'gpuss-max-step')
            celsius = raw / 1000 if mapped and raw is not None and -30000 <= raw <= 125000 else None
            zones.append({'id': p.rsplit('/', 1)[1], 'label': kind, 'raw': raw,
                          'temperatureC': celsius, 'mapping': 'Matched sm8150-thermal.dtsi TSENS zone' if mapped else 'Unmapped; raw value is not necessarily a temperature'})
            if celsius is not None:
                (gpu_temps if kind == 'gpuss-max-step' else cpu_temps).append(celsius)
        cooling = [{k: f.read(p + '/' + k) for k in ('type', 'cur_state', 'max_state')} for p in f.glob('/sys/class/thermal/cooling_device*')]
        counters = f.read('/proc/stat').splitlines()
        sample = [int(v) for v in counters[0].split()[1:9]] if counters and counters[0].startswith('cpu ') else None
        utilisation = None
        if sample and self.cpu_sample:
            total = sum(sample) - sum(self.cpu_sample)
            if total > 0:
                utilisation = round(100 * (1 - (sample[3] + sample[4] - self.cpu_sample[3] - self.cpu_sample[4]) / total), 2)
        self.cpu_sample = sample
        brightness = number(f.read('/sys/class/backlight/panel0-backlight/brightness'), 0)
        maximum = number(f.read('/sys/class/backlight/panel0-backlight/max_brightness'), 1)
        battery_power = voltage * amperes if voltage is not None and amperes is not None else None
        return dict(timestamp=utc(), capacity=capacity, status=status, externalPower=external,
            voltageV=voltage, currentA=amperes, currentSign='Positive discharge / negative charging on matched BQ driver' if self.board else 'Unverified',
            batteryPowerW=battery_power, batteryChargingPowerW=-battery_power if status == 'Charging' and battery_power is not None and battery_power < 0 else None,
            usbInputPowerW=usb.get('estimatedInputPowerW'), totalDevicePowerW=None,
            powerExplanation='Battery terminal power and USB input estimate are separate; current=0 while USB-powered is not zero device consumption',
            batteryTemperatureC=temperature, health=read('health') or None,
            fullCapacityAh=full_ah, designCapacityAh=design_ah,
            healthPercent=None, healthNote='No validated matching design/full-capacity calibration basis for a wear percentage',
            chargeCounterRaw=number(read('charge_counter'), 0),
            cycleCount=number(read('cycle_count'), 0), cycleCountNote='Driver-reported value; calibration and cycle accounting are not independently validated',
            supplies=supplies, chargerTemperatureC=(number(read('charger_temp'), 0, 900) / 10 if number(read('charger_temp'), 0, 900) is not None else None),
            chargingRestriction=read('chg_protect_status') or None,
            chargingDiagnostics={
                'enabled':read('charging_enabled')=='1' if read('charging_enabled') in ('0','1') else None,
                'inputSuspended':read('input_suspend')=='1' if read('input_suspend') in ('0','1') else None,
                'thermalMitigationLevel':number(read('charge_control_limit'),0),
                'thermalMitigationMaximum':number(read('charge_control_limit_max'),0),
                'dieHealth':read('die_health') or None,
                'protectionStatus':read('chg_protect_status') or None,
                'scope':'Read-only driver flags; no unverified fault cause or percent charge limit is inferred'},
            cpuTemperatureC=max(cpu_temps) if cpu_temps else None, gpuTemperatureC=max(gpu_temps) if gpu_temps else None,
            thermalZones=zones, coolingDevices=cooling, cpuUtilisationPercent=utilisation,
            brightnessPercent=round(100 * brightness / maximum) if brightness is not None and maximum else None,
            chargeLimit=feature(False, error='This driver uses charge_control_limit for thermal levels, not a charge percentage; no charging control is written'),
            automaticBrightness=feature(None, error='No verified ambient-light provider'),
            profile=self.applied)

    def estimate(self, data, stamp):
        if data['status'] != 'Discharging' or data['externalPower'] or not data['currentA'] or data['currentA'] <= .02:
            self.runtime_samples.clear()
            return feature(None, error='Insufficient stable battery-only discharge measurements')
        self.runtime_samples.append((stamp, data['currentA']))
        self.runtime_samples = self.runtime_samples[-20:]
        if len(self.runtime_samples) < 3 or stamp - self.runtime_samples[0][0] < 120 or not data['fullCapacityAh'] or data['capacity'] is None:
            return feature(None, error='At least three discharge samples spanning two minutes and a verified capacity are required')
        average = sum(a for t, a in self.runtime_samples) / len(self.runtime_samples)
        minutes = 60 * data['fullCapacityAh'] * data['capacity'] / 100 / average
        return feature(True, current={'minutes': round(minutes), 'samples': len(self.runtime_samples),
            'scope': 'Smoothed estimate from reported SOC, full capacity and battery current; workload changes affect runtime'})

    def suspend(self):
        states = self.fs.read('/sys/power/state').split()
        rtc = self.fs.glob('/sys/class/rtc/rtc*/wakealarm')
        verified = False
        try:
            validation = json.loads(self.fs.read('/etc/etherpower/suspend-validation.json'))
            verified = (validation.get('verified') is True and validation.get('kernel') == self.fs.read('/proc/sys/kernel/osrelease')
                and validation.get('model') == self.fs.read('/proc/device-tree/model') and bool(validation.get('validationId'))
                and bool(validation.get('wakeSource')))
        except ValueError:
            pass
        reason = None if verified else ('No RTC wakealarm and no verified physical recovery/wake validation for this kernel' if not rtc else 'No verified suspend/resume record for this exact kernel and device')
        return dict(**feature(True if verified else None if states else False, current={'advertisedStates': states,
            'memSleep': self.fs.read('/sys/power/mem_sleep'), 'rtcAlarmInterfaces': rtc,
            'wakeSources': [{'device': p.rsplit('/power/', 1)[0], 'effective': self.fs.read(p)} for p in self.fs.glob('/sys/devices/platform/soc/*/power/wakeup')],
            'wakeupCount': 'Not polled: this kernel read may block'}, requested='verified-only', effective='available' if verified else 'blocked', error=reason),
            verified=verified)

    def refresh(self, persist=False):
        stamp = time.monotonic()
        data = self.telemetry()
        data['runtime'] = self.estimate(data, stamp)
        config = self.store.config
        if self.last_external is not None and data['externalPower'] != self.last_external:
            self.emit('ExternalPowerConnected' if data['externalPower'] else 'ExternalPowerDisconnected', {'status': data['status']})
        self.last_external = data['externalPower']
        charging = data['status'] == 'Charging'
        if self.last_charging is not None and charging != self.last_charging:
            self.emit('ChargingStarted' if charging else 'ChargingStopped', {'status': data['status']})
        self.last_charging = charging
        severity = None
        if not data['externalPower'] and data['capacity'] is not None:
            for level in ('emergency', 'critical', 'low'):
                if data['capacity'] <= config['thresholds'][level]:
                    severity = level
                    break
        if severity != self.last_alert:
            self.last_alert = severity
            if severity:
                self.emit('Battery' + severity.title(), {'capacity': data['capacity'], 'level': severity})
                if config['lowBatteryAction'] == 'power-saver':
                    self.automatic_saver('low battery')
                if severity == 'emergency' and config['emergencyAction'] == 'request-shutdown':
                    # User confirmation and logind inhibitors remain mandatory.
                    self.emit('ShutdownRequested', {'reason': 'Configured emergency policy requests confirmation; no forced shutdown'})
        hot = (data['cpuTemperatureC'] is not None and data['cpuTemperatureC'] >= config['thermalWarningC'] or
               data['batteryTemperatureC'] is not None and data['batteryTemperatureC'] >= config['batteryWarningC'])
        if hot and not self.thermal_alert:
            self.emit('ThermalWarning', {'cpuC': data['cpuTemperatureC'], 'batteryC': data['batteryTemperatureC']})
            if config['thermalAction'] == 'power-saver':
                self.automatic_saver('thermal warning')
        self.thermal_alert = bool(hot)
        data['thermalWarning'] = bool(hot)
        data['batteryWarning'] = severity
        data['controls'] = self.controls()
        effective = self.effective_name(data['controls'])
        data['profileState'] = feature(bool(data['controls']['cpu']) and self.board, current=effective,
            requested=self.requested, effective=effective, error=self.error)
        data['suspend'] = self.suspend()
        data['config'] = copy.deepcopy(config)
        data['hardwareRegistry'] = self.registry
        data['displayPolicy'] = {'owner': 'Existing EtherShell Media/X11', 'requestedTimeout': config['externalTimeout'] if data['externalPower'] else config['batteryTimeout'],
            'externalPolicy': config['externalDisplayPolicy'], 'saverBrightness': config['saverBrightness'], 'effective': 'Reported by the connected graphical session',
            'screenBlanking': 'Software blank preserves the verified wake workaround; hardware panel power saving is not claimed'}
        data['schemaVersion'], data['ready'] = 1, True
        data['profile'] = effective
        if persist or stamp - self.last_history >= config['monitorSeconds']:
            self.store.record(data)
            self.last_history = stamp
        self.data = redact(data)
        return self.data

    def emit(self, kind, data):
        event = {'kind': kind, 'timestamp': utc(), 'data': data}
        self.events.append(event)
        self.store.event(kind, data)

    def automatic_saver(self,reason):
        try:self.apply('power-saver')
        except PowerError as error:
            self.error=str(error)
            self.emit('PolicyBlocked',{'reason':reason,'error':self.error,'servicesStopped':False})

    def effective_name(self, controls):
        if not self.applied:
            return 'unmanaged'
        try:
            plan = self.plan(self.applied)
            for path, value in plan:
                if self.fs.read(path) != str(value):
                    return 'externally-modified'
            return self.applied
        except PowerError:
            return 'unverified'

    def plan(self, profile, custom=None):
        if profile not in PROFILES or not self.board:
            raise PowerError('Profile controls are not verified for this device/kernel')
        current = self.controls()
        original = {p['id']: p for p in self.original['cpu']}
        custom = self.store.config['custom'] if custom is None else custom
        if not isinstance(custom, dict) or set(custom) - {'cpu', 'gpuMaxHz'}:
            raise PowerError('Custom profile must contain only CPU policies and GPU maximum')
        cpu_custom = custom.get('cpu', {})
        if not isinstance(cpu_custom, dict) or set(cpu_custom) - {p['id'] for p in current['cpu']}:
            raise PowerError('Unknown CPU policy in custom configuration')
        writes = []
        for p in current['cpu']:
            if p['id'] not in original or not p['frequenciesKHz']:
                raise PowerError('CPU policy/frequency inventory cannot be verified')
            initial = original[p['id']]
            governor = 'schedutil' if profile == 'balanced' else 'conservative' if profile == 'power-saver' else 'performance'
            maximum = int(initial['maxKHz'])
            if profile == 'power-saver':
                maximum = max(v for v in p['frequenciesKHz'] if v <= initial['maxKHz'] * .7)
            if profile == 'custom':
                row = cpu_custom.get(p['id'], {})
                if not isinstance(row, dict) or set(row) - {'governor', 'maxKHz'}:
                    raise PowerError('Custom CPU fields must be governor and maxKHz')
                governor = row.get('governor', 'schedutil')
                maximum = row.get('maxKHz', int(initial['maxKHz']))
            if governor not in p['governors'] or type(maximum) is not int or maximum not in p['frequenciesKHz'] or maximum < p['minKHz'] or maximum > initial['maxKHz']:
                raise PowerError('Unsupported governor/frequency or limit above the original maximum')
            writes.extend([(p['path'] + '/scaling_max_freq', maximum), (p['path'] + '/scaling_governor', governor)])
        gpu = current['gpu']
        if gpu and self.original['gpu']:
            maximum = int(self.original['gpu']['maxHz'])
            if profile == 'power-saver':
                maximum = max(v for v in gpu['frequenciesHz'] if v <= maximum * .7)
            if profile == 'custom':
                maximum = custom.get('gpuMaxHz', maximum)
            if type(maximum) is not int or maximum not in gpu['frequenciesHz'] or maximum < gpu['minHz'] or maximum > self.original['gpu']['maxHz']:
                raise PowerError('GPU maximum must be an advertised frequency within original bounds')
            writes.append((gpu['path'] + '/max_freq', maximum))
        if not writes:
            raise PowerError('No verified frequency policies')
        return writes

    def write(self, path, value):
        if not re.fullmatch(r'/sys/devices/system/cpu/cpufreq/policy[0-9]+/(?:scaling_governor|scaling_max_freq)', path) and not re.fullmatch(r'/sys/class/devfreq/[^/]*kgsl-3d0/max_freq', path):
            raise PowerError('Write target is not an allowed power interface')
        try:
            with self.fs.path(path).open('w') as f:
                f.write(str(value))
            if self.fs.read(path) != str(value):
                raise PowerError('Driver readback differs from the requested value')
        except OSError as e:
            raise PowerError('Power interface write denied or rejected') from e

    def apply(self, profile, custom=None, persist=True):
        if profile in PROFILES:self.requested=profile
        self.guard()
        writes = self.plan(profile, custom)
        before = [(path, self.fs.read(path)) for path, value in writes]
        previous_config = copy.deepcopy(self.store.config)
        try:
            for path, value in writes:
                self.write(path, value)
            if persist:
                config = copy.deepcopy(previous_config)
                config['requestedProfile'] = profile
                if custom is not None:
                    config['custom'] = custom
                self.store.save(config)
        except Exception as error:
            failures = []
            for path, value in reversed(before):
                try:
                    self.write(path, value)
                except PowerError:
                    failures.append(path)
            self.error = 'Profile failed; previous controls restored' if not failures else 'Profile failed; rollback could not be verified for all controls'
            self.store.event('ProfileFailed', {'reason': self.error, 'rollbackFailures': failures})
            raise PowerError(self.error) from error
        self.requested, self.applied, self.error = profile, profile, None
        self.emit('ProfileChanged', {'requested': profile, 'effective': profile})

    def configure(self, changes):
        if not isinstance(changes, dict) or set(changes) - (set(DEFAULTS) - {'schemaVersion', 'requestedProfile', 'custom'}):
            raise PowerError('Unknown or protected configuration fields')
        config = copy.deepcopy(self.store.config)
        config.update(changes)
        validate_config(config)
        self.store.save(config)
        self.emit('PreferencesChanged', {'keys': list(changes)})

    def process_impact(self, uid):
        """Lazy, caller-UID-only process resources; never a per-app energy model."""
        stamp=time.monotonic();previous=self.process_samples.get(uid,{})
        current={};rows=[];hz=os.sysconf('SC_CLK_TCK')
        for path in self.fs.glob('/proc/[0-9]*'):
            try:
                if self.fs.path(path).stat().st_uid!=uid:continue
                pid=int(path.rsplit('/',1)[1]);parts=self.fs.read(path+'/stat').rsplit(') ',1)[1].split()
                ticks=int(parts[11])+int(parts[12]);started=int(parts[19]);percent=None
                old=previous.get(pid)
                if old and old[0]==started and stamp-old[2]>=1:
                    percent=round(100*(ticks-old[1])/hz/(stamp-old[2]),2)
                current[pid]=(started,ticks,stamp)
                rss=re.search(r'^VmRSS:\s+(\d+) kB',self.fs.read(path+'/status'),re.M)
                io=dict(re.findall(r'^(read_bytes|write_bytes):\s+(\d+)',self.fs.read(path+'/io'),re.M))
                rows.append({'pid':pid,'name':self.fs.read(path+'/comm')[:64],
                    'cpuSeconds':round(ticks/hz,2),'cpuPercentOfOneCore':percent,
                    'rssBytes':int(rss.group(1))*1024 if rss else None,
                    'ioReadBytes':int(io['read_bytes']) if 'read_bytes' in io else None,
                    'ioWriteBytes':int(io['write_bytes']) if 'write_bytes' in io else None,'energyWh':None})
            except (OSError,ValueError,IndexError):continue
        self.process_samples[uid]=current
        return {'ready':True,'processes':sorted(rows,key=lambda r:r['rssBytes'] or 0,reverse=True)[:20],
            'scope':'Caller-owned processes; CPU/RSS/I/O resource impact, not measured electrical energy. CPU percentage requires two inspections.'}

    def restore_original(self):
        self.guard()
        if not self.board:raise PowerError('Original power controls are not verified for this kernel/device')
        writes = []
        for p in self.original['cpu']:
            writes += [(p['path'] + '/scaling_max_freq', int(p['maxKHz'])), (p['path'] + '/scaling_governor', p['governor'])]
        if self.original.get('gpu'):
            writes.append((self.original['gpu']['path'] + '/max_freq', int(self.original['gpu']['maxHz'])))
        before = [(p, self.fs.read(p)) for p, v in writes]
        try:
            for p, v in writes:
                self.write(p, v)
            config = copy.deepcopy(self.store.config)
            config['requestedProfile'] = None
            self.store.save(config)
        except Exception as e:
            for p, v in reversed(before):
                self.write(p, v)
            raise PowerError('Original controls could not be restored') from e
        self.applied = self.requested = None
        self.emit('ProfileChanged', {'effective': 'original', 'requested': None})
