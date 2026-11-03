"""Read-only Linux inventory. No radio scans, device writes or active media tests."""
import datetime as dt
import gzip
import hashlib
import json
import errno
import os
from pathlib import Path
import re
import sqlite3
import subprocess
import struct
import time

VERSION = 1
CATEGORIES = {
    'processor': 'CPU & GPU', 'memory': 'Memory', 'storage': 'Storage',
    'display': 'Display & Touch', 'wireless': 'Wi-Fi & Bluetooth',
    'cellular': 'Cellular Modem', 'usb': 'USB & Connectivity', 'audio': 'Audio',
    'camera': 'Cameras', 'sensors': 'Sensors', 'power': 'Battery & Power',
    'drivers': 'Drivers & Firmware',
}
STATES = ('Working', 'Detected', 'Driver missing', 'Firmware missing',
          'Driver loaded but not operational', 'Service unavailable',
          'Permission denied', 'Unsupported', 'Not tested')


def now():
    return dt.datetime.now(dt.timezone.utc).isoformat()


def redact(value):
    """Defense in depth; inventory itself only collects allowlisted properties."""
    if isinstance(value, dict):
        return {k: ('[redacted]' if re.search(
            r'serial|imei|imsi|iccid|mac(?:address)?|password|secret|token|credential|ssid|username', k, re.I)
            else redact(v)) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [redact(v) for v in value]
    if isinstance(value, str):
        value = re.sub(r'(?i)(?:[0-9a-f]{2}:){5}[0-9a-f]{2}', '[address redacted]', value)
        value = re.sub(r'\b\d{14,22}\b', '[identifier redacted]', value)
        value = re.sub(r'/(?:home|Users)/[^/\s]+(?:/[^\s,;]*)?', '[personal path redacted]', value)
        value = re.sub(r'(?i)(password|token|secret|ssid|imei|imsi|iccid)\s*[=:]\s*[^\s,;]+', r'\1=[redacted]', value)
    return value


def command(argv, timeout=5):
    """Only internal callers supply argv; never a shell or user command string."""
    try:
        p = subprocess.run(argv, capture_output=True, text=True, timeout=timeout,
                           env=dict(os.environ, LC_ALL='C', LANG='C'))
        return p.returncode, p.stdout[:262144]
    except FileNotFoundError:
        return 127, ''
    except (OSError, subprocess.TimeoutExpired):
        return 126, ''


class Files:
    def __init__(self, root='/'):
        self.root = Path(root)
        self.denied = set()

    def path(self, name):
        return self.root / name.lstrip('/')

    def read(self, name):
        try:
            with self.path(str(name)).open('rb') as f:
                return f.read(65536).decode(errors='replace').replace('\0', '').strip()
        except PermissionError:
            self.denied.add(str(name))
        except OSError:
            pass
        return ''

    def glob(self, pattern):
        try:
            return sorted('/' + p.relative_to(self.root).as_posix() for p in self.root.glob(pattern.lstrip('/')))
        except (OSError, ValueError):
            return []

    def exists(self, name):
        return self.path(name).exists()

    def link(self, name):
        p = self.path(name)
        try:
            return p.resolve(strict=True).name if p.is_symlink() else ''
        except (OSError, RuntimeError):
            return ''


class Inventory:
    def __init__(self, files=None, backend=None, run=command):
        self.fs = files or Files()
        self.backend = backend
        self.run = run
        self.previous_cpu = None
        self.config = None

    def kernel_config(self):
        if self.config is None:
            text = ''
            try:
                with gzip.open(self.fs.path('/proc/config.gz'), 'rt') as f:
                    text = f.read(2 * 1024 * 1024)
            except (OSError, EOFError):
                text = self.fs.read('/boot/config-' + self.fs.read('/proc/sys/kernel/osrelease'))
            self.config = dict(re.findall(r'^(CONFIG_\w+)=(.+)$', text, re.M))
        return self.config

    def driver(self, path):
        f = self.fs
        driver = f.link(path + '/device/driver') or f.link(path + '/driver')
        module = f.link(path + '/device/driver/module') or f.link(path + '/driver/module')
        loaded = {s.split()[0] for s in f.read('/proc/modules').splitlines() if s.split()}
        alias = f.read(path + '/device/modalias') or f.read(path + '/modalias')
        # A binding without a module symlink is evidence for a built-in driver.
        kind = ('loadable' if module in loaded else 'built-in' if driver and not module
                else 'present; linkage unverified' if module else 'unknown')
        return {'name': driver or module or 'Unknown', 'module': module or None,
                'binding': 'bound' if driver else 'not exposed', 'kind': kind,
                'hardwareId': alias or f.read(path + '/device/of_node/compatible') or None,
                'firmware': {'dependencies': [], 'state': 'Not tested',
                             'reason': 'Firmware presence does not prove successful loading'}}

    def component(self, category, ident, title, path='', state='Detected', details=None,
                  reason='', nodes=(), service=None):
        assert state in STATES
        f = self.fs
        permissions = [{'node': n, 'exists': f.exists(n),
                        'readable': os.access(f.path(n), os.R_OK),
                        'writable': os.access(f.path(n), os.W_OK)} for n in nodes]
        return dict(id=ident, category=category, title=title, status=state,
                    reason=reason, path=path, driver=self.driver(path) if path else {},
                    nodes=permissions, service=service, details=details or {}, verifiedAt=now())

    def collect(self, category, diagnostic=False):
        self.fs.denied.clear()
        rows = getattr(self, category)()
        if diagnostic and category == 'wireless':
            for path in self.fs.glob('/sys/class/ieee80211/*'):
                phy = path.rsplit('/', 1)[1]
                if not re.fullmatch(r'phy[0-9]+', phy):
                    continue
                code, out = self.run(['iw', 'phy', phy, 'info'])
                modes = []
                match = re.search(r'Supported interface modes:\n((?:\s+\*[^\n]+\n)+)', out)
                if match:
                    modes = re.findall(r'\*\s+([^\n]+)', match.group(1))
                rows.append(self.component('wireless', 'phy:' + phy, 'Wireless driver capabilities', path,
                    state='Detected' if not code else 'Permission denied' if code == 1 else 'Not tested',
                    reason='Read-only nl80211 capability query; no interface or radio mode changed' if not code else 'iw query unavailable; inspect permissions or install the diagnostic tool',
                    details={'modes': modes, 'concurrency': 'Advertised combinations do not prove stable concurrent operation',
                        'capabilities': {'wifi.ap': {'supported': 'AP' in modes if modes else None,
                                                    'operational': None, 'reason': 'Driver mode advertisement only'}}}))
        if diagnostic and category == 'camera':
            self.camera_capabilities(rows)
        if diagnostic and category == 'sensors':
            code,out=self.run(['qrtr-lookup'])
            detected=not code and any(re.match(r'^\s*16\s+2\s+',line) for line in out.splitlines())
            if detected:
                rows.append(self.component('sensors','gnss:qualcomm-loc','GNSS',state='Detected',service='com.etherneco.EtherLocation1',
                    reason='QMI LOC v2 advertised over QRTR; a session start or service advertisement does not verify a real position fix',
                    details={'transport':'QRTR','capabilities':{'sensors.gnss':{'supported':True,'operational':None,'reason':'Real position fix not verified by hardware inventory; use controlled EtherLocation diagnostics'}}}))
        if diagnostic and category == 'drivers':
            rows += self.vendor_firmware()
        if self.backend and category in ('wireless', 'cellular', 'usb', 'audio', 'power'):
            try:
                rows += self.backend.collect(category, self)
            except Exception as e:
                state = 'Permission denied' if 'AccessDenied' in type(e).__name__ else 'Service unavailable'
                rows.append(self.component(category, category + '.backend', 'System service evidence', state=state,
                    reason='Read-only backend query failed; no hardware state was changed'))
        if diagnostic:
            self.firmware(rows)
        for path in sorted(self.fs.denied):
            rows.append(self.component(category, 'permission:' + path, 'Restricted hardware interface', path,
                'Permission denied', reason='Discovery user cannot read this interface'))
        return redact(rows)

    def vendor_firmware(self):
        """Reuse reviewed EtherMobile metadata; never open Android partitions."""
        try:
            profile = json.loads((Path(__file__).parent / 'vendor-profile.json').read_text())
        except (OSError, ValueError):
            return []
        if (self.fs.read('/proc/device-tree/model') != profile['deviceTreeModel'] or
            self.fs.read('/proc/sys/kernel/osrelease') != profile['kernel']):
            return []
        records = []
        for name, metadata in profile['firmware'].items():
            if not re.fullmatch(r'ipa_(?:fws|uc)\.(?:mdt|b[0-9]{2})', name):
                continue
            present = self.fs.exists('/lib/firmware/' + name)
            verified = None
            try:
                with self.fs.path('/lib/firmware/' + name).open('rb') as f:
                    blob = f.read(1024 * 1024)
                verified = len(blob) == metadata['bytes'] and hashlib.sha256(blob).hexdigest() == metadata['sha256']
            except OSError:
                pass
            records.append({'file': name, 'available': present, 'matchesReviewedVendorFile': verified})
        missing = any(not r['available'] for r in records)
        return [self.component('drivers', 'vendor.ipa-firmware', 'Qualcomm IPA firmware dependencies',
            state='Firmware missing' if missing else 'Detected',
            reason='Required vendor firmware file is absent' if missing else 'Vendor files inspected; availability and hashes do not prove successful runtime loading',
            details={'files': records, 'loadStatus': 'Not tested', 'metadataSource': profile['source'],
                     'compatibleDebianFirmwarePackage': None,
                     'maintenance': 'No verified Debian replacement for these device-specific vendor files; use separate maintenance'})]

    def camera_capabilities(self, rows):
        """VIDIOC_QUERYCAP only: never configure controls, buffers or streaming."""
        import fcntl
        for row in rows:
            name = row['id'].removeprefix('v4l:')
            if not re.fullmatch(r'video[0-9]+', name):
                continue
            try:
                fd = os.open(self.fs.path('/dev/' + name), os.O_RDONLY | os.O_NONBLOCK)
                try:
                    buf = bytearray(104)
                    fcntl.ioctl(fd, 0x80685600, buf, True)
                finally:
                    os.close(fd)
                version, caps, device_caps = struct.unpack_from('=III', buf, 80)
                flags = device_caps if caps & 0x80000000 else caps
                capture = bool(flags & (0x1 | 0x1000)) and not bool(flags & (0x2 | 0x2000 | 0x4000 | 0x8000))
                row['details'].update(querycapDriver=bytes(buf[:16]).split(b'\0')[0].decode(errors='replace'),
                    deviceCapabilities=flags, captureOnly=capture,
                    capabilities={'camera.capture': {'supported': True if capture else None,
                        'operational': None, 'reason': 'Capture-only device advertised; no image is captured' if capture else 'Codec or non-capture node; camera support unverified'}})
                row['details']['cameraRole'] = 'capture-candidate' if capture else 'codec-or-non-capture'
                for capability in ('camera.preview', 'camera.photo', 'camera.video'):
                    row['details']['capabilities'][capability] = {
                        'supported': None, 'operational': None,
                        'reason': 'EtherCamera physical-frame acceptance required; device-node presence is insufficient'}
            except OSError as e:
                if e.errno in (errno.EACCES, errno.EPERM):
                    row['status'] = 'Permission denied'
                row['reason'] = 'Read-only V4L2 capability query unavailable; no capture attempted'

    def processor(self):
        f = self.fs
        cpu = f.read('/proc/cpuinfo')
        model = next((line.split(':', 1)[1].strip() for line in cpu.splitlines()
                      if line.lower().startswith(('model name', 'hardware'))), '')
        cores = f.glob('/sys/devices/system/cpu/cpu[0-9]*')
        fields = f.read('/proc/stat').splitlines()
        sample = [int(x) for x in fields[0].split()[1:9]] if fields and fields[0].startswith('cpu ') else []
        usage = None
        if self.previous_cpu and sample:
            delta = sum(sample) - sum(self.previous_cpu)
            if delta > 0:
                usage = round(100 * (1 - ((sample[3] + sample[4]) -
                              (self.previous_cpu[3] + self.previous_cpu[4])) / delta), 2)
        self.previous_cpu = sample or None
        policies = []
        for p in f.glob('/sys/devices/system/cpu/cpufreq/policy*'):
            policies.append({k: f.read(p + '/' + k) or None for k in
                ('affected_cpus', 'scaling_cur_freq', 'scaling_min_freq', 'scaling_max_freq',
                 'cpuinfo_max_freq', 'scaling_governor', 'scaling_available_governors', 'stats/time_in_state')})
        thermal = [{k: f.read(p + '/' + k) or None for k in ('type', 'temp', 'mode')}
                   for p in f.glob('/sys/class/thermal/thermal_zone*')]
        cooling = [{k: f.read(p + '/' + k) or None for k in ('type', 'cur_state', 'max_state')}
                   for p in f.glob('/sys/class/thermal/cooling_device*')]
        rows = [self.component('processor', 'cpu', model or 'Processor', state='Working' if sample else 'Not tested',
            details={'architecture': self.run(['uname', '-m'])[1].strip() or None,
                     'cores': len(cores) or None, 'utilisationPercent': usage,
                     'frequenciesKHz': policies, 'thermalZones': thermal, 'coolingDevices': cooling,
                     'throttling': 'Cooling state is an indicator; reduced frequency alone is not proof'},
            reason='CPU time counters readable' if sample else 'CPU counters unavailable')]
        for p in f.glob('/sys/class/kgsl/kgsl-3d0') + f.glob('/sys/class/drm/renderD*'):
            rows.append(self.component('processor', 'gpu:' + p.rsplit('/', 1)[1],
                f.read(p + '/gpu_model') or 'GPU render device', p, details={
                    'clockHz': f.read(p + '/gpuclk') or None, 'busy': f.read(p + '/gpubusy') or None,
                    'throttling': f.read(p + '/throttling') or None,
                    'acceleration': 'Not tested; inspect rendering in the logged-in session'},
                nodes=('/dev/dri/' + p.rsplit('/', 1)[1],) if '/drm/' in p else ('/dev/kgsl-3d0',)))
        return rows

    def memory(self):
        f = self.fs
        info = {k: int(v) * 1024 for k, v in re.findall(r'^(\w+):\s+(\d+) kB', f.read('/proc/meminfo'), re.M)}
        return [self.component('memory', 'memory', 'System memory', state='Working' if info else 'Not tested',
            details={'totalBytes': info.get('MemTotal'), 'availableBytes': info.get('MemAvailable'),
                     'swapTotalBytes': info.get('SwapTotal'), 'swapFreeBytes': info.get('SwapFree'),
                     'pressure': f.read('/proc/pressure/memory') or None,
                     'oomKills': dict(re.findall(r'^(oom_kill) (\d+)$', f.read('/proc/vmstat'), re.M)).get('oom_kill'),
                     'oomEvidence': 'Counter unavailable on older kernels' if not f.exists('/proc/pressure/memory') else 'Kernel counters only'})]

    def storage(self):
        f = self.fs
        rows = []
        mounts = []
        for line in f.read('/proc/self/mountinfo').splitlines():
            parts = line.split()
            if ' - ' not in line or len(parts) < 7:
                continue
            extra = line.split(' - ', 1)[1].split()
            if extra and extra[0] in ('ext4', 'f2fs', 'vfat', 'btrfs', 'xfs', 'ntfs', 'exfat'):
                point = parts[4].replace('\\040', ' ')
                capacity = {}
                try:
                    stat = os.statvfs(f.path(point))
                    capacity = {'totalBytes': stat.f_blocks * stat.f_frsize,
                                'availableBytes': stat.f_bavail * stat.f_frsize}
                except (OSError, AttributeError):
                    pass
                mounts.append(dict(mount=point, filesystem=extra[0], device=extra[1], **capacity))
        for p in f.glob('/sys/class/block/*'):
            name = p.rsplit('/', 1)[1]
            if name.startswith(('loop', 'ram')):
                continue
            sectors = f.read(p + '/size')
            rows.append(self.component('storage', 'block:' + name, name, p, details={
                'capacityBytes': int(sectors) * 512 if sectors.isdigit() else None,
                'partition': f.read(p + '/partition') or None, 'readOnly': f.read(p + '/ro'),
                'ioCounters': f.read(p + '/stat'), 'health': 'Not tested; no destructive storage test is run'},
                nodes=('/dev/' + name,)))
        rows.insert(0, self.component('storage', 'filesystems', 'Mounted filesystems',
                                    state='Working' if mounts else 'Not tested', details={'mounts': mounts}))
        return rows

    def display(self):
        f = self.fs
        rows = []
        for p in f.glob('/sys/class/drm/card*-*'):
            status = f.read(p + '/status')
            if not status:
                continue
            rows.append(self.component('display', 'display:' + p.rsplit('/', 1)[1], p.rsplit('/', 1)[1], p,
                details={'connection': status, 'enabled': f.read(p + '/enabled'),
                         'modes': f.read(p + '/modes').splitlines(),
                         'currentMode': None, 'refreshHz': None, 'scale': None, 'rotation': None,
                         'verification': 'Connector state; current mode/refresh/scale require session inspection'}))
        for p in f.glob('/sys/class/input/event*'):
            props = f.read(p + '/device/properties')
            name = f.read(p + '/device/name')
            direct = bool(props and re.fullmatch(r'[0-9a-fA-F ]+', props) and int(props.split()[-1], 16) & 2)
            rows.append(self.component('display', 'input:' + p.rsplit('/', 1)[1], name or 'Input device', p,
                details={'touchscreen': direct, 'properties': props}, nodes=('/dev/input/' + p.rsplit('/', 1)[1],)))
        for p in f.glob('/sys/class/backlight/*'):
            rows.append(self.component('display', 'backlight:' + p.rsplit('/', 1)[1], 'Backlight', p,
                details={k: f.read(p + '/' + k) for k in ('brightness', 'actual_brightness', 'max_brightness')}))
        return rows or [self.component('display', 'display', 'Display interfaces', state='Not tested', reason='No readable DRM interfaces')]

    def wireless(self):
        f = self.fs
        rows = []
        for p in f.glob('/sys/class/net/*'):
            if not (f.exists(p + '/wireless') or f.exists(p + '/phy80211')):
                continue
            name = p.rsplit('/', 1)[1]
            rows.append(self.component('wireless', 'wifi:' + name, 'Wi-Fi ' + name, p,
                details={'interface': name, 'operstate': f.read(p + '/operstate'),
                         'radio': [{k: f.read(r + '/' + k) for k in ('type', 'soft', 'hard')}
                                   for r in f.glob('/sys/class/rfkill/*')],
                         'signalCounters': f.read('/proc/net/wireless')}, service='org.freedesktop.NetworkManager'))
        for p in f.glob('/sys/class/bluetooth/hci*'):
            rows.append(self.component('wireless', 'bluetooth:' + p.rsplit('/', 1)[1], 'Bluetooth adapter', p,
                service='org.bluez', reason='Controller enumeration; discovery has not been started'))
        return rows or [self.component('wireless', 'wireless', 'Wireless interfaces', state='Not tested', reason='No adapter exposed to discovery')]

    def cellular(self):
        f = self.fs
        rows = []
        for p in f.glob('/sys/class/net/rmnet*') + f.glob('/sys/class/wwan/*') + f.glob('/sys/bus/qrtr/devices/*'):
            rows.append(self.component('cellular', 'modem-transport:' + p.rsplit('/', 1)[1], 'Modem transport', p,
                details={'transport': p.rsplit('/', 1)[1]}, service='org.freedesktop.ModemManager1'))
        return rows

    def usb(self):
        f = self.fs
        rows = []
        for p in f.glob('/sys/class/udc/*'):
            rows.append(self.component('usb', 'udc:' + p.rsplit('/', 1)[1], 'USB gadget controller', p,
                state='Working' if f.read(p + '/state') == 'configured' else 'Detected',
                details={k: f.read(p + '/' + k) or None for k in ('state', 'current_speed', 'maximum_speed')},
                reason='Host has configured the gadget' if f.read(p + '/state') == 'configured' else 'No configured host verified'))
        for p in f.glob('/sys/class/dual_role_usb/*') + f.glob('/sys/class/typec/port[0-9]'):
            rows.append(self.component('usb', 'role:' + p.rsplit('/', 1)[1], 'USB-C roles', p,
                details={k: f.read(p + '/' + k) or None for k in ('mode', 'data_role', 'power_role', 'supported_modes', 'power_operation_mode')}))
        for p in f.glob('/sys/bus/usb/devices/*'):
            vendor = f.read(p + '/idVendor')
            if vendor:
                rows.append(self.component('usb', 'usb:' + p.rsplit('/', 1)[1], f.read(p + '/product') or 'USB device', p,
                    details={k: f.read(p + '/' + k) for k in ('idVendor', 'idProduct', 'bDeviceClass', 'speed', 'authorized')}))
        for p in f.glob('/sys/class/net/*'):
            name = p.rsplit('/', 1)[1]
            if name != 'lo' and f.read(p + '/type') == '1':
                rows.append(self.component('usb', 'ethernet:' + name, 'Network interface ' + name, p,
                    details={'interface': name, 'operstate': f.read(p + '/operstate'),
                             'usb': '/usb' in str(f.path(p).resolve()) or name.startswith(('usb', 'rndis'))}))
        return rows

    def audio(self):
        f = self.fs
        return [self.component('audio', 'alsa', 'ALSA audio devices', state='Detected' if f.read('/proc/asound/cards') else 'Not tested',
            details={'cards': f.read('/proc/asound/cards'), 'pcm': f.read('/proc/asound/pcm'),
                     'cardIds': [f.read(p + '/id') for p in f.glob('/sys/class/sound/card[0-9]*')],
                     'usbCards': [p for p in f.glob('/sys/class/sound/card[0-9]*') if '/usb' in str(f.path(p).resolve())],
                     'captureNodes': f.glob('/dev/snd/pcm*c'), 'playbackNodes': f.glob('/dev/snd/pcm*p'),
                     'physicalTest': 'Not tested; microphone and speaker tests require explicit user interaction'},
            nodes=f.glob('/dev/snd/controlC*') + f.glob('/dev/snd/pcm*c') + f.glob('/dev/snd/pcm*p'))]

    def camera(self):
        f = self.fs
        rows = []
        for p in f.glob('/sys/class/video4linux/*'):
            name = p.rsplit('/', 1)[1]
            rows.append(self.component('camera', 'v4l:' + name, f.read(p + '/name') or name, p,
                details={'kind': 'subdevice' if name.startswith('v4l-subdev') else 'video node',
                         'capture': 'Not tested; video nodes may be codecs rather than cameras'}, nodes=('/dev/' + name,)))
        for p in f.glob('/dev/media*'):
            rows.append(self.component('camera', 'media:' + p.rsplit('/', 1)[1], 'Media controller', nodes=(p,)))
        return rows or [self.component('camera', 'camera', 'Camera capture', state='Not tested', reason='No standard camera interface exposed')]

    def sensors(self):
        f = self.fs
        rows = []
        fp = '/sys/bus/platform/devices/soc:goodix_fp'
        if 'goodix,fingerprint' in f.read(fp + '/of_node/compatible'):
            rows.append(self.component('sensors', 'fingerprint:goodix', 'Goodix under-display fingerprint', fp,
                state='Driver loaded but not operational' if f.link(fp + '/driver') else 'Detected',
                nodes=('/dev/goodix_fp',), service='com.etherneco.EtherFingerprint1',
                reason='Secure enrollment, verification and display illumination not verified; PIN/password required',
                details={'vendor':'Goodix','firmwareStatus':'Not verified','backend':'Diagnostics only',
                    'enrollmentSupported':False,'verificationSupported':False,'operational':False,
                    'capabilities':{'fingerprint.authentication':{'supported':False,'operational':False,
                        'reason':'No verified trusted adapter'}}}))
        for p in f.glob('/sys/bus/iio/devices/iio:device*'):
            channels = [x.rsplit('/', 1)[1] for x in f.glob(p + '/in_*')]
            rows.append(self.component('sensors', 'iio:' + p.rsplit('/', 1)[1], f.read(p + '/name') or 'IIO sensor', p,
                details={'channels': channels, 'sampleTest': 'Not tested; no buffer or sensor is enabled'}))
        for pattern, label in [('/sys/class/ssc/*', 'Android sensor subsystem'),
                               ('/sys/class/leds/*vibr*', 'Haptics'), ('/sys/class/timed_output/vibrator', 'Haptics'),
                               ('/sys/class/gnss/*', 'GNSS')]:
            for p in f.glob(pattern):
                rows.append(self.component('sensors', 'sensor:' + p, label, p, reason='Vendor interface; functional test unavailable'))
        if f.exists('/usr/share/ethersensors/service.py'):
            rows.append(self.component('sensors', 'ethersensors', 'EtherSensors framework',
                state='Not tested', service='com.etherneco.EtherSensors1',
                reason='Session sensor owner; query its API for compatible providers and current measurements',
                details={'physical':False,'derivedSensorsArePhysical':False,
                    'capabilities':{'sensors.'+kind:{'supported':None,'operational':None,
                        'reason':'Use EtherSensors session API; hardware presence and physical response remain independently verified'}
                        for kind in ('orientation','gravity','linear_acceleration','rotation_vector')}}))
        return rows or [self.component('sensors', 'sensors', 'Sensors', state='Not tested', reason='No sensor interface exposed')]

    def power(self):
        f = self.fs
        rows = []
        for p in f.glob('/sys/class/power_supply/*'):
            details = {k: f.read(p + '/' + k) or None for k in (
                'type', 'present', 'status', 'capacity', 'temp', 'voltage_now', 'current_now',
                'charge_full', 'charge_full_design', 'online', 'usb_type', 'voltage_max', 'current_max')}
            good = details['type'] == 'Battery' and details['capacity'] is not None
            rows.append(self.component('power', 'power:' + p.rsplit('/', 1)[1], p.rsplit('/', 1)[1], p,
                state='Working' if good else 'Detected', details=details,
                reason='Battery telemetry readable' if good else 'Supply enumerated'))
        rows.append(self.component('power', 'suspend', 'Suspend controls', details={
            'states': f.read('/sys/power/state').split(), 'memSleep': f.read('/sys/power/mem_sleep') or None,
            'wakeSources': f.read('/sys/kernel/debug/wakeup_sources') or None},
            reason='No suspend test is performed; existing EtherPower remains the owner'))
        return rows

    def drivers(self):
        config = self.kernel_config()
        selected = {k: v for k, v in config.items() if re.match(
            r'CONFIG_(?:ARM64$|MODULES$|FW_LOADER|CFG80211|BT|DRM|SND|USB|IIO|VIDEO|MEDIA|QCOM|MSM|KGSL|RMNET)', k)}
        rows = [self.component('drivers', 'kernel', 'Kernel compatibility', details={
            'kernel': self.fs.read('/proc/sys/kernel/osrelease'), 'configAvailable': bool(config),
            'config': selected, 'loadedModules': [s.split()[0] for s in self.fs.read('/proc/modules').splitlines() if s.split()],
            'builtInEvidence': 'Use driver bindings without a module link and CONFIG_*=y; lsmod is insufficient',
            'maintenance': 'Kernel/vendor firmware/boot changes require separate maintenance'})]
        for name in [s.split()[0] for s in self.fs.read('/proc/modules').splitlines() if s.split()]:
            row = self.component('drivers', 'module:' + name, 'Kernel module ' + name, '/sys/module/' + name,
                                 reason='Loaded module; no functional success is inferred')
            row['driver'].update(name=name, module=name, kind='loadable', binding='module loaded; device binding separate')
            rows.append(row)
        return rows

    def firmware(self, rows):
        """On-demand metadata only. Do not probe firmware by loading a driver."""
        log_code, log = self.run(['journalctl', '-k', '-b', '-n', '300', '--no-pager', '-o', 'cat'], timeout=5)
        missing = set(re.findall(r'Direct firmware load for\s+([\w./-]+) failed with error -2\b', log)) if not log_code else set()
        if not log_code:
            missing.update(re.findall(r'firmware: failed to load\s+([\w./-]+)\s+\(-2\)', log))
        for row in rows:
            driver = row.get('driver', {})
            module = driver.get('module')
            deps = []
            if module and re.fullmatch(r'[\w-]{1,80}', module):
                code, out = self.run(['modinfo', '-F', 'firmware', module])
                if not code:
                    deps = [v for v in out.splitlines() if re.fullmatch(r'[\w./*-]{1,180}', v) and '..' not in v.split('/')]
            records = []
            for dep in deps:
                found = any(self.fs.glob(base + dep + suffix) for base in ('/lib/firmware/', '/usr/lib/firmware/') for suffix in ('', '.xz', '.zst'))
                failed = dep in missing
                records.append({'file': dep, 'available': found, 'loadFailedThisBoot': failed,
                                'state': 'Firmware missing' if failed and not found else 'Not tested'})
            if driver:
                driver['firmware'] = {'dependencies': records, 'state': 'Firmware missing' if any(x['state'] == 'Firmware missing' for x in records) else 'Not tested',
                    'reason': 'Bound driver metadata and bounded current-boot journal; vendor dependencies may not be exposed',
                    'journalAccessible': log_code == 0}
                if driver['firmware']['state'] == 'Firmware missing':
                    row['status'] = 'Firmware missing'
                    row['reason'] = 'Firmware request failed and named file is absent'


CAPABILITY_IDS = ('wifi.client', 'wifi.ap', 'wifi.concurrent', 'bluetooth.adapter',
    'bluetooth.audio', 'bluetooth.pan', 'cellular.data', 'cellular.sms', 'cellular.voice',
    'cellular.sim', 'usb.gadget', 'usb.host', 'usb.network', 'ethernet.interface',
    'display.external', 'display.touch', 'audio.microphone', 'audio.speaker',
    'audio.playback', 'audio.capture', 'audio.earpiece', 'audio.usb', 'audio.bluetooth',
    'audio.voice-call', 'audio.hardware-volume', 'camera.capture',
    'camera.rear.main', 'camera.rear.ultrawide', 'camera.rear.telephoto', 'camera.front',
    'camera.preview', 'camera.photo', 'camera.video', 'camera.autofocus', 'camera.flash', 'camera.qr', 'camera.barcode',
    'power.battery', 'power.suspend', 'sensors.accelerometer', 'sensors.gyroscope',
    'sensors.proximity', 'sensors.light', 'sensors.ambient_light', 'sensors.barometer',
    'sensors.orientation', 'sensors.gravity', 'sensors.linear_acceleration', 'sensors.rotation_vector',
    'sensors.magnetometer', 'sensors.gnss', 'sensors.haptics')


def capabilities(components):
    result = {ident: dict(id=ident, hardwareProvider=None, backendProvider=None, supported=None,
        operational=None, status='Not tested', lastVerification=None, evidence=[],
        failureReason='No verification evidence available') for ident in CAPABILITY_IDS}
    def put(ident, row, supported=True, operational=None, reason=None):
        old = result[ident]
        if old['operational'] is True and operational is not True:
            return
        if supported is None:
            supported = old['supported']
        provider = row['id'] if row.get('path') else old['hardwareProvider'] or row['id']
        result[ident] = dict(id=ident, hardwareProvider=provider, backendProvider=row.get('service') or 'Linux sysfs/proc',
            supported=supported, operational=operational,
            status='Working' if operational is True else row['status'], lastVerification=row['verifiedAt'],
            evidence=old['evidence'] + [{'component': row['id'], 'status': row['status'], 'reason': row['reason']}],
            failureReason=reason or (None if operational is True else row['reason'] or 'Functional test has not been run'))
    for row in components:
        ident, data = row['id'], row['details']
        for cap, evidence in data.get('capabilities', {}).items():
            if cap in result:
                put(cap, row, evidence.get('supported'), evidence.get('operational'), evidence.get('reason'))
        if ident.startswith('wifi:') and result['wifi.client']['supported'] is None:
            put('wifi.client', row)
        if ident.startswith('bluetooth:') and result['bluetooth.adapter']['supported'] is None:
            put('bluetooth.adapter', row)
        if ident.startswith('udc:'):
            put('usb.gadget', row, operational=data.get('state') == 'configured')
        if ident.startswith('role:') and 'host' in str(data.get('supported_modes')):
            put('usb.host', row, operational=None)
        if ident.startswith('ethernet:'):
            put('ethernet.interface', row)
            if data.get('usb'):
                put('usb.network', row, operational=None, reason='Interface exists; end-to-end traffic is not tested')
        if ident.startswith('display:') and '-DP-' in ident or ident.startswith('display:') and '-HDMI-' in ident:
            put('display.external', row, operational=None, reason='DRM connector found; session output and physical display need verification')
        if ident.startswith('input:') and data.get('touchscreen'):
            put('display.touch', row)
        if ident == 'alsa':
            if data.get('captureNodes'):
                put('audio.microphone', row, reason='ALSA capture exists; microphone recording requires user action')
                put('audio.capture', row, reason='Capture PCM detected; endpoint and acoustic verification remain separate')
            if data.get('playbackNodes'):
                put('audio.speaker', row, reason='ALSA playback exists; physical speaker routing requires user action')
                put('audio.playback', row, reason='Playback PCM detected; a PCM does not certify physical output')
            if data.get('usbCards'):
                put('audio.usb', row, reason='USB ALSA card detected; compatible input/output needs endpoint tests')
            if any('tavil' in str(c).lower() for c in data.get('cardIds', [])):
                put('audio.voice-call', row, supported=None, operational=False,
                    reason='Blocked: Qualcomm modem voice-session routing and a real cellular call are not validated')
                put('audio.earpiece', row, supported=None,
                    reason='No validated native UCM earpiece path; speaker playback is not evidence')
        if result['bluetooth.audio']['supported'] is not None and result['audio.bluetooth']['supported'] is None:
            result['audio.bluetooth'] = dict(result['bluetooth.audio'], id='audio.bluetooth')
        if ident.startswith('power:') and data.get('type') == 'Battery':
            put('power.battery', row, operational=row['status'] == 'Working')
        if ident == 'suspend' and data.get('states'):
            put('power.suspend', row, reason='Kernel advertises suspend states; suspend/resume is not tested')
        if ident.startswith('iio:'):
            for cap, pattern in [('accelerometer', 'accel'), ('gyroscope', 'anglvel'), ('proximity', 'proximity'), ('light', 'illuminance'), ('ambient_light', 'illuminance'), ('magnetometer', 'magn'), ('barometer','pressure')]:
                if any(pattern in x for x in data.get('channels', [])):
                    put('sensors.' + cap, row)
        if row['title'] == 'GNSS':
            put('sensors.gnss', row)
        if row['title'] == 'Haptics':
            put('sensors.haptics', row)
    for ident, capability in result.items():
        if ident in ('sensors.orientation','sensors.gravity','sensors.linear_acceleration','sensors.rotation_vector'):
            capability['physical'] = False
        if ident.startswith('audio.'):
            capability.update(detected=capability['hardwareProvider'] is not None,
                              verified=capability['operational'] is True,
                              unsupported=capability['supported'] is False,
                              blocked='Blocked:' in str(capability.get('failureReason')))
    return list(result.values())


class Registry:
    """Bounded, redacted state history. Previous boot state is never current proof."""
    def __init__(self, directory, inventory):
        self.directory = Path(directory)
        self.directory.mkdir(parents=True, exist_ok=True)
        self.db = sqlite3.connect(self.directory / 'history.sqlite', check_same_thread=False)
        self.db.execute('CREATE TABLE IF NOT EXISTS events (id INTEGER PRIMARY KEY, timestamp TEXT, component TEXT, previous TEXT, current TEXT, reason TEXT, metadata TEXT)')
        self.inventory = inventory
        self.groups = {}
        self.generation = 0
        self.last = None
        self.last_error = None

    def refresh(self, categories=None, diagnostic=False):
        selected = list(categories or CATEGORIES)
        if any(c not in CATEGORIES for c in selected):
            raise ValueError('Unknown hardware category')
        before = {r['id']: r for rows in self.groups.values() for r in rows}
        for category in selected:
            try:
                self.groups[category] = self.inventory.collect(category, diagnostic)
            except Exception:
                self.groups[category] = [self.inventory.component(category, category + '.error', CATEGORIES[category],
                    state='Not tested', reason='Read-only collection failed; previous evidence invalidated')]
        rows = [r for group in self.groups.values() for r in group]
        after = {r['id']: r for r in rows}
        for ident in before.keys() | after.keys():
            a, b = before.get(ident), after.get(ident)
            old = a['status'] if a else 'Unknown'
            new = b['status'] if b else 'Removed'
            signature = lambda r: (r['status'], r['reason'], r['details'].get('capabilities', {})) if r else None
            if signature(a) != signature(b):
                self.db.execute('INSERT INTO events(timestamp,component,previous,current,reason,metadata) VALUES(?,?,?,?,?,?)',
                    (now(), ident, old, new, b['reason'] if b else 'Interface removed', json.dumps(redact({'category': (b or a)['category'], 'capabilities': (b or a)['details'].get('capabilities', {})}))))
        self.db.execute('DELETE FROM events WHERE id NOT IN (SELECT id FROM events ORDER BY id DESC LIMIT 1000)')
        self.db.commit()
        self.generation += 1
        self.last = now()
        snapshot = self.snapshot()
        temp = self.directory / 'registry.json.new'
        temp.write_text(json.dumps(snapshot), encoding='utf-8')
        temp.replace(self.directory / 'registry.json')
        return snapshot

    def snapshot(self):
        rows = [r for group in self.groups.values() for r in group]
        f = self.inventory.fs
        return redact(dict(schemaVersion=VERSION, available=True, ready=bool(self.groups), generation=self.generation,
            verifiedAt=self.last, message=self.last_error or 'Read-only inventory; unknown is not a failed functional test',
            system={'device': f.read('/proc/device-tree/model') or 'Unknown',
                    'kernel': f.read('/proc/sys/kernel/osrelease'),
                    'os': dict(re.findall(r'^(PRETTY_NAME|DEBIAN_VERSION_FULL)="?([^"\n]+)', f.read('/etc/os-release'), re.M))},
            categories=[{'id': k, 'title': v, 'count': len(self.groups.get(k, []))} for k, v in CATEGORIES.items()],
            components=rows, capabilities=capabilities(rows),
            failedDiagnostics=[r['id'] for r in rows if r['status'] in STATES[2:7]],
            scope='Evidence is per component and timestamp; no active capture, playback, radio, suspend or storage-write tests'))

    def history(self, query='', component='', limit=200):
        if len(query) > 128 or len(component) > 256:
            raise ValueError('History filter too long')
        rows = self.db.execute('SELECT timestamp,component,previous,current,reason,metadata FROM events WHERE instr(lower(component||reason||current),lower(?))>0 AND (?="" OR component=?) ORDER BY id DESC LIMIT ?',
                               (query, component, component, max(1, min(1000, int(limit))))).fetchall()
        return [dict(timestamp=r[0], component=r[1], previous=r[2], current=r[3], reason=r[4], metadata=json.loads(r[5])) for r in rows]

    def clear(self):
        self.db.execute('DELETE FROM events')
        self.db.commit()

    def report(self, fmt='json'):
        if fmt not in ('json', 'text'):
            raise ValueError('Unsupported report format')
        data = self.snapshot()
        data['history'] = self.history()
        if fmt == 'json':
            return json.dumps(redact(data), indent=2)
        return 'EtherHardware support report (redacted)\n' + '\n'.join(
            f"{r['title']}: {r['status']} — {r['reason']}\n  {json.dumps(r['details'], ensure_ascii=False)}" for r in data['components']) + '\n\n' + json.dumps(data, indent=2)
