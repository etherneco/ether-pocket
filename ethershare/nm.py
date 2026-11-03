"""NetworkManager owns Wi-Fi/Ethernet profiles; no credentials in argv/logs."""
import socket
import struct
import time
import dbus

from core import ShareError

BUS = 'org.freedesktop.NetworkManager'
ROOT = '/org/freedesktop/NetworkManager'


class NetworkManager:
    def __init__(self):
        # Constructed in the worker: all NM requests are serialized off the UI bus.
        self.bus = dbus.SystemBus(private=True)
        self.root = self.bus.get_object(BUS, ROOT, follow_name_owner_changes=True)
        self.nm = dbus.Interface(self.root, BUS)

    def props(self, path, interface):
        return dict(dbus.Interface(self.bus.get_object(BUS, path), 'org.freedesktop.DBus.Properties').GetAll(interface, timeout=8))

    def devices(self):
        result = {}
        for path in self.nm.GetDevices(timeout=8):
            p = self.props(path, BUS + '.Device')
            name = str(p['Interface'])
            data = dict(path=str(path), type=int(p['DeviceType']), managed=bool(p['Managed']), connection='')
            if str(p['ActiveConnection']) != '/':
                a = self.props(p['ActiveConnection'], BUS + '.Connection.Active')
                data['connection'] = str(a.get('Uuid', ''))
            if str(p['Ip4Config']) != '/':
                ip = self.props(p['Ip4Config'], BUS + '.IP4Config')
                data['dns'] = [str(x['address']) for x in ip.get('NameserverData', []) if ':' not in str(x['address'])]
            try:
                if data['type'] == 2:
                    wifi = self.props(path, BUS + '.Device.Wireless')
                    data['ap'] = bool(int(wifi['WirelessCapabilities']) & 0x40)
                    if str(wifi['ActiveAccessPoint']) != '/':
                        ap = self.props(wifi['ActiveAccessPoint'], BUS + '.AccessPoint')
                        data['signal'] = int(ap['Strength'])
                    data['speedMbps'] = int(wifi.get('Bitrate', 0)) / 1000
                elif data['type'] == 1:
                    data['speedMbps'] = int(self.props(path, BUS + '.Device.Wired').get('Speed', 0))
            except dbus.DBusException:
                pass
            result[name] = data
        return result

    def has_vpn(self):
        try:
            return any(bool(self.props(p, BUS + '.Connection.Active').get('Vpn', False))
                       for p in self.props(ROOT, BUS).get('ActiveConnections', []))
        except dbus.DBusException:
            # Failure to inspect VPNs must block a new start.
            raise ShareError('Cannot determine VPN state')

    def settings(self):
        return dbus.Interface(self.bus.get_object(BUS, ROOT + '/Settings'), BUS + '.Settings')

    def profile(self, uuid):
        for path in self.settings().ListConnections(timeout=8):
            obj = dbus.Interface(self.bus.get_object(BUS, path), BUS + '.Settings.Connection')
            s = obj.GetSettings(timeout=8)
            if str(s['connection']['uuid']) == uuid:
                return path, obj, s
        return None

    def activate_downstream(self, j, c):
        devices = self.devices()
        device = devices[j['interface']]
        hotspot = j['method'] == 'hotspot'
        if hotspot and not device.get('ap'):
            raise ShareError('NetworkManager reports no AP capability')
        connection_type = '802-11-wireless' if hotspot else '802-3-ethernet'
        s = {'connection': {'id': 'EtherShare ' + j['method'], 'uuid': j['profile'],
                            'type': connection_type, 'interface-name': j['interface'],
                            'autoconnect': dbus.Boolean(False)},
             'ipv4': {'method': 'manual', 'never-default': dbus.Boolean(True),
                      'address-data': dbus.Array([dbus.Dictionary({'address': j['gateway'], 'prefix': dbus.UInt32(24)}, signature='sv')], signature='a{sv}')},
             'ipv6': {'method': 'disabled'}}
        if hotspot:
            s['802-11-wireless'] = {'ssid': dbus.ByteArray(c['ssid'].encode()), 'mode': 'ap',
                                   'band': c['band'], 'channel': dbus.UInt32(c['channel']),
                                   'hidden': dbus.Boolean(c['hidden'])}
            s['802-11-wireless-security'] = {'key-mgmt': 'wpa-psk', 'psk': c['password'],
                                           'proto': dbus.Array(['rsn'], signature='s'),
                                           'pairwise': dbus.Array(['ccmp'], signature='s'),
                                           'group': dbus.Array(['ccmp'], signature='s')}
        else:
            s['802-3-ethernet'] = dbus.Dictionary({}, signature='sv')
        settings = dbus.Dictionary({k: dbus.Dictionary(v, signature='sv') for k, v in s.items()}, signature='sa{sv}')
        path = self.settings().AddConnection(settings, timeout=10)
        active = self.nm.ActivateConnection(path, dbus.ObjectPath(device['path']), dbus.ObjectPath('/'), timeout=10)
        for _ in range(80):
            state = int(self.props(active, BUS + '.Connection.Active')['State'])
            if state == 2:
                return
            if state == 4:
                break
            time.sleep(.25)
        raise ShareError('NetworkManager could not activate the downstream profile')

    def remove_downstream(self, j):
        profile = self.profile(j['profile'])
        if profile:
            path, obj, settings = profile
            if str(settings['connection'].get('id', '')) != 'EtherShare ' + j['method']:
                raise ShareError('Profile ownership changed; not deleting it')
            for active in self.props(ROOT, BUS).get('ActiveConnections', []):
                if str(self.props(active, BUS + '.Connection.Active').get('Uuid', '')) == j['profile']:
                    self.nm.DeactivateConnection(active, timeout=10)
            obj.Delete(timeout=8)
        if j.get('previous'):
            previous = self.profile(j['previous'])
            device = self.devices().get(j['interface'])
            if previous and device:
                self.nm.ActivateConnection(previous[0], dbus.ObjectPath(device['path']), dbus.ObjectPath('/'), timeout=10)
