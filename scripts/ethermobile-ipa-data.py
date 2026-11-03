#!/usr/bin/python3
"""Downstream IPA data-path bring-up; no firmware/subsystem resets.

Uses a dedicated WDS client only when ModemManager has no active bearer.
The process owns the client for the lifetime of the connection. Startup and
explicit GUI actions use ethermobile-data.service; failures are not retried.
"""
import ctypes
import fcntl
import ipaddress
import json
from pathlib import Path
import signal
import socket
import struct
import subprocess
import sys
import os
import ethermobile_data_status as status

import gi
gi.require_version('Qmi', '1.0')
gi.require_version('Qrtr', '1.0')
from gi.repository import GLib, Qmi, Qrtr


def call(start, finish, *args):
    loop = GLib.MainLoop()
    result = []
    def done(source, response, *unused):
        try:
            result.append((True, finish(response)))
        except Exception as error:
            result.append((False, error))
        loop.quit()
    start(*args, None, done, None)
    loop.run()
    ok, value = result[0]
    if not ok:
        raise value
    return value


def run(*args):
    return subprocess.check_output(args, text=True).strip()


def ioctl(operation, payload=b''):
    # Exact ARM64 msm_rmnet.h ABI: extended ioctl is uint32 + 20-byte union;
    # ifreq has a 16-byte name and a 24-byte union containing the data pointer.
    data = ctypes.create_string_buffer(struct.pack('=I', operation) + payload.ljust(20, b'\0'), 24)
    request = struct.pack('16sP', b'rmnet_ipa0', ctypes.addressof(data)).ljust(40, b'\0')
    with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sock:
        fcntl.ioctl(sock, 0x89FD, request)
    return data.raw[4:]


def cleanup_data(state_file, created, handle, wds, wda, dpm, device):
    state_file.unlink(missing_ok=True)
    subprocess.run(['resolvectl', 'revert', 'epcell0'], capture_output=True)
    # Linux cleanup must not depend on a successful QMI reply. In particular,
    # an already-disconnected bearer can reject StopNetwork while the stale
    # netdev would prevent every later attempt to reconnect.
    if created:
        subprocess.run(['ip', 'link', 'delete', 'epcell0'], capture_output=True)
    if handle is not None:
        try:
            stop = Qmi.MessageWdsStopNetworkInput.new()
            stop.set_packet_data_handle(handle)
            call(wds.stop_network, wds.stop_network_finish, stop, 15).get_result()
        except Exception as error:
            print('WDS stop confirmation unavailable: '+type(error).__name__, file=sys.stderr, flush=True)
    for client in (wds, wda, dpm):
        try:
            call(device.release_client, device.release_client_finish, client, Qmi.DeviceReleaseClientFlags.RELEASE_CID, 10)
        except Exception as error:
            print('Client release confirmation unavailable: '+type(error).__name__, file=sys.stderr, flush=True)


def main():
    status.update('packet_path', 'Sprawdzam interfejs rmnet_ipa0 i blokadę właściciela danych…')
    assert Path('/etc/etherpocket/disk-identity').read_text().strip() == 'GM1920-548cb338-mobian-sda21'
    assert Path('/sys/class/net/rmnet_ipa0/type').read_text().strip() == '519'
    lock = open('/run/ethermobile-ipa-data.lock', 'w')
    fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
    endpoint = struct.unpack('=I', ioctl(3)[:4])[0]
    pipes = struct.unpack('=II', ioctl(16)[:8])
    print(json.dumps({'endpoint': endpoint, 'consumer_producer_pipes': pipes}), flush=True)
    if '--connect' not in sys.argv:
        return
    state = run('nmcli', '-g', 'GENERAL.STATE', 'device', 'show', 'qrtr0')
    assert state.startswith('30 '), 'NetworkManager must be disconnected before direct WDS testing'
    status.update('qrtr', 'Łączę się z modemem przez QRTR/QMI…')
    bus = call(Qrtr.Bus.new, Qrtr.Bus.new_finish, 1000)
    node = bus.get_node(0)
    assert node is not None
    device = call(Qmi.Device.new_from_node, Qmi.Device.new_finish, node)
    call(device.open, device.open_finish, Qmi.DeviceOpenFlags.NONE, 10)
    status.update('dpm', 'Otwieram port danych modemu (DPM)…')
    dpm = call(device.allocate_client, device.allocate_client_finish, Qmi.Service.DPM, 0, 10)
    hardware = Qmi.MessageDpmOpenPortInputHardwareDataPortsElement()
    hardware.endpoint_type = Qmi.DataEndpointType.EMBEDDED
    hardware.interface_number = endpoint
    hardware.rx_endpoint_number = pipes[0]
    hardware.tx_endpoint_number = pipes[1]
    ports = Qmi.MessageDpmOpenPortInput.new()
    ports.set_hardware_data_ports([hardware])
    call(dpm.open_port, dpm.open_port_finish, ports, 10).get_result()
    print('DPM hardware data port opened', flush=True)
    status.update('format', 'Uzgadniam format pakietów QMAP z modemem…')
    wda = call(device.allocate_client, device.allocate_client_finish, Qmi.Service.WDA, 0, 10)
    data_format = Qmi.MessageWdaSetDataFormatInput.new()
    data_format.set_endpoint_info(Qmi.DataEndpointType.EMBEDDED, endpoint)
    data_format.set_link_layer_protocol(Qmi.WdaLinkLayerProtocol.RAW_IP)
    data_format.set_uplink_data_aggregation_protocol(Qmi.WdaDataAggregationProtocol.QMAP)
    data_format.set_downlink_data_aggregation_protocol(Qmi.WdaDataAggregationProtocol.QMAP)
    # Firmware leaves QMAP disabled unless the uplink size/count are supplied.
    data_format.set_uplink_data_aggregation_max_datagrams(1)
    data_format.set_uplink_data_aggregation_max_size(16384)
    data_format.set_downlink_data_aggregation_max_datagrams(32)
    data_format.set_downlink_data_aggregation_max_size(32768)
    applied = call(wda.set_data_format, wda.set_data_format_finish, data_format, 10)
    applied.get_result()
    assert applied.get_uplink_data_aggregation_protocol() == Qmi.WdaDataAggregationProtocol.QMAP
    assert applied.get_downlink_data_aggregation_protocol() == Qmi.WdaDataAggregationProtocol.QMAP
    # These IOCTLs allocate hardware pipes and must run only once per boot.
    status.update('pipes', 'Konfiguruję kanały sprzętowe IPA…')
    marker = Path('/run/ethermobile-ipa-pipes.json')
    configured = json.loads(marker.read_text()) if marker.exists() else {}
    for key, operation in [('egress', 6), ('ingress', 7)]:
        if key not in configured:
            ioctl(operation, struct.pack('=I', 14))
            configured[key] = 14
            marker.write_text(json.dumps(configured))
        assert configured[key] == 14
    status.update('wds', 'Przygotowuję sesję danych i kanał WDS…')
    wds = call(device.allocate_client, device.allocate_client_finish, Qmi.Service.WDS, 0, 10)
    bind = Qmi.MessageWdsBindMuxDataPortInput.new()
    bind.set_endpoint_info(Qmi.DataEndpointType.EMBEDDED, endpoint)
    bind.set_mux_id(1)
    bind.set_client_type(Qmi.WdsClientType.TETHERED)
    call(wds.bind_mux_data_port, wds.bind_mux_data_port_finish, bind, 10).get_result()
    print('WDS bound to embedded endpoint and mux 1', flush=True)
    family = Qmi.MessageWdsSetIpFamilyInput.new()
    family.set_preference(Qmi.WdsIpFamily.IPV4)
    call(wds.set_ip_family, wds.set_ip_family_finish, family, 10).get_result()
    # Do not adopt or delete a preexisting interface. The lifecycle below owns
    # only the child created after this check under the exclusive process lock.
    assert not Path('/sys/class/net/epcell0').exists()
    created = False
    start = Qmi.MessageWdsStartNetworkInput.new()
    start.set_apn('giffgaff.com')
    start.set_authentication_preference(Qmi.WdsAuthentication.PAP)
    start.set_username('gg')
    start.set_password('p')
    start.set_ip_family_preference(Qmi.WdsIpFamily.IPV4)
    handle = None
    state_file = Path('/run/ethermobile-data.json')
    try:
        run('ip', 'link', 'add', 'link', 'rmnet_ipa0', 'name', 'epcell0', 'type', 'rmnet', 'mux_id', '1')
        created = True
        ioctl(5, struct.pack('=I16s', 1, b'epcell0'))
        run('ip', 'link', 'set', 'rmnet_ipa0', 'up')
        status.update('session', 'Łączę z operatorem: zestawiam sesję APN giffgaff.com (do 45 s)…')
        output = call(wds.start_network, wds.start_network_finish, start, 45)
        try:
            output.get_result()
        except Exception as error:
            # A generic CallFailed hides whether the carrier rejected the call
            # or the packet path failed. These are protocol reason codes only;
            # never log credentials, subscriber identifiers or the request.
            reasons = []
            for name in ('get_call_end_reason', 'get_verbose_call_end_reason'):
                try:
                    value = getattr(output, name)()
                    codes = value if isinstance(value, tuple) else (value,)
                    print(name + ': ' + ','.join(str(int(x)) for x in codes),
                          file=sys.stderr, flush=True)
                    reasons.append(name + '=' + ','.join(str(int(x)) for x in codes))
                except Exception:
                    pass
            error.safe_detail = 'Operator/modem odrzucił sesję danych. ' + '; '.join(reasons)
            raise
        handle = output.get_packet_data_handle()
        status.update('address', 'Sesja przyjęta. Pobieram adres IP, bramę i DNS od operatora…')
        query = Qmi.MessageWdsGetCurrentSettingsInput.new()
        query.set_requested_settings(Qmi.WdsRequestedSettings.IP_ADDRESS | Qmi.WdsRequestedSettings.GATEWAY_INFO | Qmi.WdsRequestedSettings.DNS_ADDRESS | Qmi.WdsRequestedSettings.MTU)
        settings = call(wds.get_current_settings, wds.get_current_settings_finish, query, 10)
        settings.get_result()
        address = str(ipaddress.IPv4Address(settings.get_ipv4_address()))
        mask = str(ipaddress.IPv4Address(settings.get_ipv4_gateway_subnet_mask()))
        gateway = str(ipaddress.IPv4Address(settings.get_ipv4_gateway_address()))
        prefix = ipaddress.IPv4Network('0.0.0.0/' + mask).prefixlen
        run('ip', 'address', 'add', address + '/' + str(prefix), 'dev', 'epcell0')
        run('ip', 'link', 'set', 'epcell0', 'up')
        run('ip', 'route', 'add', 'default', 'via', gateway, 'dev', 'epcell0', 'metric', '900')
        dns = [str(ipaddress.IPv4Address(getattr(settings, name)())) for name in ['get_primary_ipv4_dns_address', 'get_secondary_ipv4_dns_address']]
        status.update('dns', 'Ustawiam adres IP, trasę internetową i serwery DNS…')
        run('resolvectl', 'dns', 'epcell0', *dns)
        run('resolvectl', 'default-route', 'epcell0', 'yes')
        observed = {'connected': True, 'interface': 'epcell0', 'address': address, 'gateway': gateway, 'dns': dns, 'pid': os.getpid(), 'provider': 'downstream-ipa-wds'}
        temporary = state_file.with_suffix('.new')
        temporary.write_text(json.dumps(observed)); temporary.replace(state_file)
        status.update('connected', 'Połączono z siecią komórkową. Adres IP i DNS są gotowe; dostęp do internetu wymaga osobnego testu.',
                      state='connected', interface='epcell0', address=address, gateway=gateway, dns=dns, pid=os.getpid(), apn='giffgaff.com')
        print(json.dumps(observed), flush=True)
        if '--probe' in sys.argv:
            dns = [str(ipaddress.IPv4Address(getattr(settings, name)())) for name in ['get_primary_ipv4_dns_address', 'get_secondary_ipv4_dns_address']]
            print(json.dumps({'dns': dns}), flush=True)
            ping = subprocess.run(['/var/tmp/ethermobile-iputils/usr/bin/ping', '-I', 'epcell0', '-c', '3', '-W', '2', '1.1.1.1'], capture_output=True, text=True)
            print(ping.stdout, flush=True)
            for destination in dns[:1]:
                with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sock:
                    sock.setsockopt(socket.SOL_SOCKET, socket.SO_BINDTODEVICE, b'epcell0\0')
                    sock.settimeout(3)
                    query = bytes.fromhex('123401000001000000000000') + b'\x08giffgaff\x03com\x00\x00\x01\x00\x01'
                    sock.sendto(query, (destination, 53))
                    try:
                        response = sock.recv(4096)
                        print(json.dumps({'dns_response_bytes': len(response)}), flush=True)
                    except TimeoutError:
                        print('Cellular DNS timed out', flush=True)
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
                sock.setsockopt(socket.SOL_SOCKET, socket.SO_BINDTODEVICE, b'epcell0\0')
                sock.settimeout(3)
                try:
                    sock.connect(('1.1.1.1', 80))
                    print('Cellular TCP connected', flush=True)
                except OSError as error:
                    print('Cellular TCP failed: ' + str(error), flush=True)
            query = Qmi.MessageWdsGetPacketStatisticsInput.new()
            query.set_mask(Qmi.WdsPacketStatisticsMaskFlag.TX_PACKETS_OK | Qmi.WdsPacketStatisticsMaskFlag.RX_PACKETS_OK | Qmi.WdsPacketStatisticsMaskFlag.TX_BYTES_OK | Qmi.WdsPacketStatisticsMaskFlag.RX_BYTES_OK)
            stats = call(wds.get_packet_statistics, wds.get_packet_statistics_finish, query, 10)
            stats.get_result()
            print(json.dumps({n: getattr(stats, 'get_' + n)() for n in ['tx_packets_ok', 'rx_packets_ok', 'tx_bytes_ok', 'rx_bytes_ok']}), flush=True)
            return
        loop = GLib.MainLoop()
        for signum in (signal.SIGTERM, signal.SIGINT):
            GLib.unix_signal_add(GLib.PRIORITY_DEFAULT, signum, lambda: (loop.quit(), False)[1])
        loop.run()
    finally:
        cleanup_data(state_file, created, handle, wds, wda, dpm, device)


if __name__ == '__main__':
    try:
        main()
    except Exception as error:
        print(status.failure(error), file=sys.stderr, flush=True)
        raise SystemExit(1)
