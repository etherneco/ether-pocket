"""Read-only projections of the existing hardware owners. Never enumerate messages,
connections' settings, Bluetooth peers, subscriber identifiers or credentials.
"""
import json
import dbus

NM = 'org.freedesktop.NetworkManager'
MM = 'org.freedesktop.ModemManager1'


def plain(value):
    if isinstance(value, (dbus.Boolean, bool)):
        return bool(value)
    if isinstance(value, dict):
        return {str(k): plain(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [plain(x) for x in value]
    if isinstance(value, (dbus.Int16, dbus.UInt16, dbus.Int32, dbus.UInt32, dbus.Int64, dbus.UInt64, dbus.Byte)):
        return int(value)
    if isinstance(value, dbus.Double):
        return float(value)
    return str(value)


class Backends:
    def __init__(self):
        self.bus = dbus.SystemBus(private=True)

    def props(self, name, path, interface):
        obj = self.bus.get_object(name, path, introspect=False)
        return dbus.Interface(obj, 'org.freedesktop.DBus.Properties').GetAll(interface, timeout=3)

    def objects(self, name, path):
        obj = self.bus.get_object(name, path, introspect=False)
        return dbus.Interface(obj, 'org.freedesktop.DBus.ObjectManager').GetManagedObjects(timeout=4)

    def unit(self, unit):
        try:
            manager = dbus.Interface(self.bus.get_object('org.freedesktop.systemd1', '/org/freedesktop/systemd1', introspect=False), 'org.freedesktop.systemd1.Manager')
            path = manager.GetUnit(unit, timeout=3)
            p = self.props('org.freedesktop.systemd1', path, 'org.freedesktop.systemd1.Unit')
            return {k: plain(p.get(k, 'Unknown')) for k in ('ActiveState', 'SubState', 'LoadState')}
        except dbus.DBusException:
            return {'ActiveState': 'unknown'}

    def collect(self, category, inventory):
        self.i = inventory
        return getattr(self, category)()

    def missing(self, category, ident, title, service, error):
        denied = 'AccessDenied' in error.get_dbus_name()
        return self.i.component(category, ident, title, state='Permission denied' if denied else 'Service unavailable',
            service=service, reason='Read-only service query denied' if denied else 'Existing service has no readable owner or object')

    def wireless(self):
        rows = []
        try:
            root = '/org/freedesktop/NetworkManager'
            nm = dbus.Interface(self.bus.get_object(NM, root, introspect=False), NM)
            radio = self.props(NM, root, NM)
            for path in nm.GetDevices(timeout=3):
                p = self.props(NM, path, NM + '.Device')
                if int(p.get('DeviceType', 0)) != 2:
                    continue
                w = self.props(NM, path, NM + '.Device.Wireless')
                connected = int(p.get('State', 0)) == 100
                strength = None
                if str(w.get('ActiveAccessPoint', '/')) != '/':
                    strength = int(self.props(NM, w['ActiveAccessPoint'], NM + '.AccessPoint').get('Strength', 0))
                ap = bool(int(w.get('WirelessCapabilities', 0)) & 0x40)
                iface = str(p.get('Interface', 'unknown'))
                rows.append(self.i.component('wireless', 'nm:' + iface, 'Wi-Fi service · ' + iface,
                    '/sys/class/net/' + iface, state='Working' if connected else 'Detected', service=NM,
                    reason='NetworkManager reports an activated Wi-Fi link; internet is not tested' if connected else 'Adapter exists; no activated connection verified',
                    details={'interface': iface, 'connectionState': int(p.get('State', 0)),
                        'driver': str(p.get('Driver', '')), 'driverVersion': str(p.get('DriverVersion', '')),
                        'firmwareVersion': str(p.get('FirmwareVersion', '')),
                        'radioEnabled': bool(radio.get('WirelessEnabled', False)),
                        'hardwareRadioEnabled': bool(radio.get('WirelessHardwareEnabled', False)),
                        'signalPercent': strength, 'bitrateKbit': int(w.get('Bitrate', 0)),
                        'capabilities': {'wifi.client': {'supported': True, 'operational': connected},
                                         'wifi.ap': {'supported': ap, 'operational': None, 'reason': 'AP advertised by NetworkManager; activation is not tested'}}}))
        except dbus.DBusException as e:
            rows.append(self.missing('wireless', 'nm', 'NetworkManager', NM, e))
        try:
            for path, interfaces in self.objects('org.bluez', '/').items():
                if 'org.bluez.Adapter1' not in interfaces:
                    continue
                p = interfaces['org.bluez.Adapter1']
                powered = bool(p.get('Powered', False))
                uuids = {str(x).lower() for x in p.get('UUIDs', [])}
                audio = any(x.startswith(('0000110a-', '0000110b-', '0000111e-', '0000111f-')) for x in uuids)
                pan = any(x.startswith(('00001115-', '00001116-', '00001117-')) for x in uuids)
                runtime = {}
                try:
                    candidate = json.loads(self.i.fs.read('/run/etherbluetooth/controller.json'))
                    runtime = {k: candidate[k] for k in ('transport', 'rom', 'patch', 'host_firmware_uploaded') if k in candidate}
                except ValueError:
                    pass
                rows.append(self.i.component('wireless', 'bluez:' + str(path).rsplit('/', 1)[1], 'BlueZ controller',
                    '/sys/class/bluetooth/' + str(path).rsplit('/', 1)[1],
                    state='Working' if powered else 'Detected', service='org.bluez',
                    reason='BlueZ controller powered; discovery/pairing/audio have not been initiated' if powered else 'BlueZ controller is not powered',
                    details={'powered': powered, 'discovering': bool(p.get('Discovering', False)),
                        'existingTransportEvidence': runtime,
                        'capabilities': {'bluetooth.adapter': {'supported': True, 'operational': powered},
                            'bluetooth.audio': {'supported': True if audio else None, 'operational': None, 'reason': 'Profile advertisement only; no audio playback test'},
                            'bluetooth.pan': {'supported': True if pan else None, 'operational': None, 'reason': 'PAN needs a verified profile and kernel backend'}}}))
        except dbus.DBusException as e:
            rows.append(self.missing('wireless', 'bluez', 'BlueZ service', 'org.bluez', e))
        try:
            name = 'com.etherneco.EtherShare1'
            obj = dbus.Interface(self.bus.get_object(name, '/com/etherneco/EtherShare1', introspect=False), name)
            state = json.loads(str(obj.GetState(timeout=3)))
            warning = str(state.get('radioWarning', ''))
            if warning:
                rows.append(self.i.component('wireless', 'share.radio', 'EtherShare radio guard', state='Driver loaded but not operational',
                    service=name, reason=warning, details={'capabilities': {
                        'wifi.ap': {'supported': None, 'operational': False, 'reason': warning},
                        'wifi.concurrent': {'supported': None, 'operational': False, 'reason': warning}}}))
        except (dbus.DBusException, ValueError):
            pass
        return rows

    def cellular(self):
        rows = []
        owner = self.unit('ethermobile-data.service')
        try:
            for path, interfaces in self.objects(MM, '/org/freedesktop/ModemManager1').items():
                if MM + '.Modem' not in interfaces:
                    continue
                p = interfaces[MM + '.Modem']
                gpp = interfaces.get(MM + '.Modem.Modem3gpp', {})
                state = int(p.get('State', 0))
                sim = str(p.get('Sim', '/')) != '/'
                # PIN2/PUK2 restrict supplementary SIM functions, not registration.
                unlocked = int(p.get('UnlockRequired', 0)) in (1, 3, 5)
                registered = int(gpp.get('RegistrationState', 0)) in (1, 5)
                failed = owner['ActiveState'] == 'failed'
                data = state == 11 and not failed
                sms = interfaces.get(MM + '.Modem.Messaging', {})
                sms_supported = bool(sms.get('SupportedStorages', []))
                rows.append(self.i.component('cellular', 'mm:' + str(path).rsplit('/', 1)[1], 'Cellular modem',
                    state='Driver loaded but not operational' if failed else 'Working' if registered else 'Detected', service=MM,
                    reason='Existing EtherMobile data owner is failed; registration is not data connectivity' if failed else 'Registered; individual services require separate verification' if registered else 'Modem detected; registration not verified',
                    details={'manufacturer': str(p.get('Manufacturer', '')), 'model': str(p.get('Model', '')),
                        'firmwareRevision': str(p.get('Revision', '')), 'drivers': plain(p.get('Drivers', [])),
                        'ports': plain(p.get('Ports', [])), 'state': state, 'simPresent': sim,
                        'unlockRequired': int(p.get('UnlockRequired', 0)),
                        'registration': int(gpp.get('RegistrationState', 0)),
                        'dataOwner': owner, 'controlTransport': 'qrtr' if any('qrtr' in str(x) for x in p.get('Ports', [])) else 'See ports',
                        'capabilities': {'cellular.data': {'supported': True, 'operational': data, 'reason': 'No connected bearer verified' if not data else 'Connected bearer; internet not tested'},
                            'cellular.sms': {'supported': True if sms_supported else None, 'operational': None, 'reason': 'Messaging interface/storage only; no SMS is read or sent'},
                            'cellular.voice': {'supported': None, 'operational': None, 'reason': 'Voice interface presence does not verify calling or audio routing'},
                            'cellular.sim': {'supported': sim, 'operational': sim and unlocked, 'reason': 'SIM presence and unlock metadata; subscriber identifiers are never queried'}}}))
        except dbus.DBusException as e:
            rows.append(self.missing('cellular', 'mm', 'ModemManager', MM, e))
        if not rows:
            rows.append(self.i.component('cellular', 'mm.empty', 'Cellular modem', state='Not tested', service=MM,
                                        reason='ModemManager has no exposed modem object'))
        return rows

    def usb(self):
        return []

    def audio(self):
        return []  # The session audio owner is queried by the unprivileged GUI.

    def power(self):
        try:
            p = self.props('org.freedesktop.login1', '/org/freedesktop/login1', 'org.freedesktop.login1.Manager')
            return [self.i.component('power', 'logind', 'Power-management service', service='org.freedesktop.login1',
                details={'preparingForSleep': bool(p.get('PreparingForSleep', False))},
                reason='Existing logind service; no power action requested')]
        except dbus.DBusException as e:
            return [self.missing('power', 'logind', 'Power-management service', 'org.freedesktop.login1', e)]
