"""EtherShare policy and Linux networking core. No GUI or D-Bus dependency.

Only this service's journaled addresses, routes, chains and NM profiles are
modified. Existing USB gadget functions and recovery addresses are never edited.
"""
import copy
import ipaddress
import json
import os
from pathlib import Path
import re
import signal
import subprocess
import time
import uuid

STATE = Path('/var/lib/ethershare')
RUN = Path('/run/ethershare')
IPT = '/usr/sbin/iptables-legacy'
IP6T = '/usr/sbin/ip6tables-legacy'
DEFAULTS = dict(version=1, upstream='auto', priority=['ethernet', 'wifi', 'cellular'],
                failover=False, vpnPolicy='ask', autostart=False, timeoutMinutes=0,
                ssid='EtherPocket', password='', band='bg', channel=6, hidden=False,
                subnet='auto', dns=[], leaseMinutes=60, dhcpStart=20, dhcpEnd=200, clientNames={})


class ShareError(Exception):
    pass


def run(args, check=True, timeout=12, **kw):
    r = subprocess.run([str(x) for x in args], capture_output=True, text=True,
                       timeout=timeout, **kw)
    if check and r.returncode:
        # Command arguments can contain configuration. Never copy them to logs.
        raise ShareError(Path(str(args[0])).name + ' failed (' + str(r.returncode) + ')')
    return r.stdout.strip()


def atomic(path, data):
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    temporary = path.with_suffix('.new')
    fd = os.open(temporary, os.O_CREAT | os.O_TRUNC | os.O_WRONLY, 0o600)
    with os.fdopen(fd, 'w') as f:
        f.write(data)
        f.flush()
        os.fsync(f.fileno())
    temporary.replace(path)


def iface_name(value):
    if not isinstance(value, str) or not re.fullmatch(r'[a-zA-Z0-9_.-]{1,15}', value):
        raise ShareError('Invalid interface name')
    return value


def validated_config(update, current=None):
    c = copy.deepcopy(current or DEFAULTS)
    if not isinstance(update, dict) or set(update) - set(DEFAULTS):
        raise ShareError('Unknown configuration field')
    c.update(update)
    if c['version'] != 1:
        raise ShareError('Unsupported configuration version')
    if c['upstream'] != 'auto':
        iface_name(c['upstream'])
    if sorted(c['priority']) != ['cellular', 'ethernet', 'wifi']:
        raise ShareError('Priority must contain Ethernet, Wi-Fi and cellular once')
    if c['vpnPolicy'] not in ['ask', 'normal', 'vpn']:
        raise ShareError('Choose a VPN routing policy')
    for key in ['failover', 'autostart', 'hidden']:
        if type(c[key]) is not bool:
            raise ShareError('Invalid switch value')
    for key, low, high in [('timeoutMinutes', 0, 1440), ('leaseMinutes', 5, 1440), ('channel', 1, 11), ('dhcpStart', 2, 253), ('dhcpEnd', 2, 253)]:
        if type(c[key]) is not int or not low <= c[key] <= high:
            raise ShareError('Invalid ' + key)
    if c['dhcpStart'] > c['dhcpEnd']:
        raise ShareError('DHCP start must not exceed its end')
    if not isinstance(c['clientNames'],dict) or len(c['clientNames'])>128:
        raise ShareError('At most 128 local client names')
    for mac,name in c['clientNames'].items():
        if not re.fullmatch(r'(?:[0-9a-f]{2}:){5}[0-9a-f]{2}',mac) or not isinstance(name,str) or len(name)>64 or any(ord(x)<32 for x in name):
            raise ShareError('Invalid local client name')
    if c['band'] != 'bg':
        raise ShareError('Only verified 2.4 GHz channel selection is enabled')
    if not isinstance(c['ssid'], str) or not 1 <= len(c['ssid'].encode()) <= 32 or any(ord(x) < 32 for x in c['ssid']):
        raise ShareError('Network name must be 1–32 UTF-8 bytes without control characters')
    p = c['password']
    if not isinstance(p, str) or (p and (not 8 <= len(p) <= 63 or any(ord(x) < 32 or ord(x) > 126 for x in p))):
        raise ShareError('WPA2 password must be 8–63 printable ASCII characters')
    if c['subnet'] != 'auto':
        try:
            net = ipaddress.IPv4Network(c['subnet'], strict=True)
            if net.prefixlen != 24 or not any(net.subnet_of(ipaddress.ip_network(p)) for p in ['10.0.0.0/8', '172.16.0.0/12', '192.168.0.0/16']):
                raise ValueError()
        except (ValueError, TypeError):
            raise ShareError('Choose a private IPv4 /24 network')
    if not isinstance(c['dns'], list) or len(c['dns']) > 3:
        raise ShareError('At most three IPv4 DNS servers')
    try:
        for d in c['dns']:
            a = ipaddress.IPv4Address(d)
            if a.is_unspecified or a.is_loopback or a.is_multicast:
                raise ValueError()
    except (ValueError, TypeError):
        raise ShareError('Invalid DNS server')
    return c


def choose_subnet(routes, requested='auto', reserved=()):
    occupied = [ipaddress.ip_network(x['dst'], strict=False) for x in routes
                if x.get('dst') not in [None, 'default']]
    occupied += [ipaddress.ip_network(x) for x in reserved]
    choices = [requested] if requested != 'auto' else ['192.168.%s.0/24' % x for x in range(73, 254)]
    for candidate in choices:
        n = ipaddress.ip_network(candidate)
        if not any(n.overlaps(o) for o in occupied):
            return str(n)
    raise ShareError('Downstream subnet overlaps an existing network')


def firewall_rules(j):
    """Ordered rule plan, strict upstream and a deliberate USB recovery exception."""
    d, u, subnet, tag = j['interface'], j['upstream'], j['subnet'], j['tag']
    i, f, n = tag + 'I', tag + 'F', tag + 'N'
    rules = [(IPT, 'filter', i, ['-m', 'conntrack', '--ctstate', 'ESTABLISHED,RELATED', '-j', 'ACCEPT'])]
    if j['method'] == 'usb':
        rules.append((IPT, 'filter', i, ['-s', '10.77.0.1', '-p', 'tcp', '--dport', '22', '-j', 'ACCEPT']))
    for proto, ports in [('udp', '53,67'), ('tcp', '53')]:
        rules.append((IPT, 'filter', i, ['-p', proto, '-m', 'multiport', '--dports', ports, '-j', 'ACCEPT']))
    rules += [(IPT, 'filter', i, ['-p', 'icmp', '-j', 'ACCEPT']), (IPT, 'filter', i, ['-j', 'DROP'])]
    rules += [(IPT, 'filter', f, ['-i', u, '-o', d, '-d', subnet, '-m', 'conntrack', '--ctstate', 'ESTABLISHED,RELATED', '-j', 'ACCEPT'])]
    # Downstream clients cannot use sharing to reach other management LANs.
    for private in ['10.0.0.0/8', '172.16.0.0/12', '192.168.0.0/16', '169.254.0.0/16']:
        rules.append((IPT, 'filter', f, ['-i', d, '-d', private, '-j', 'DROP']))
    rules += [(IPT, 'filter', f, ['-i', d, '-o', u, '-s', subnet, '-j', 'ACCEPT']),
              (IPT, 'filter', f, ['-j', 'DROP']),
              (IPT, 'nat', n, ['-s', subnet, '-o', u, '-j', 'MASQUERADE']),
              (IP6T, 'filter', i, ['-p', 'ipv6-icmp', '-j', 'ACCEPT']),
              (IP6T, 'filter', i, ['-j', 'DROP']),
              (IP6T, 'filter', f, ['-j', 'DROP'])]
    hooks = [(IPT, 'filter', 'INPUT', ['-i', d, '-j', i]),
             (IPT, 'filter', 'FORWARD', ['-i', d, '-j', f]),
             (IPT, 'filter', 'FORWARD', ['-o', d, '-j', f]),
             (IPT, 'nat', 'POSTROUTING', ['-s', subnet, '-j', n]),
             (IP6T, 'filter', 'INPUT', ['-i', d, '-j', i]),
             (IP6T, 'filter', 'FORWARD', ['-i', d, '-j', f]),
             (IP6T, 'filter', 'FORWARD', ['-o', d, '-j', f])]
    return rules, hooks


class LinuxShare:
    def __init__(self, nm, state=STATE, runtime=RUN):
        self.nm, self.state, self.runtime = nm, state, runtime
        self.state.mkdir(mode=0o700, parents=True, exist_ok=True)
        self.runtime.mkdir(mode=0o700, parents=True, exist_ok=True)
        p = self.state / 'config.json'
        self.config = validated_config(json.loads(p.read_text()) if p.exists() else {})
        self.active = {}
        self.blocked = {}
        self.message = ''
        self.revision = 0
        self.probes = {}
        self.last_monitor = 0
        self.last_activity = time.monotonic()
        self.forward_before = None
        self.rates = {}
        self.events = []
        self.seen_clients = set()

    def save(self, changes):
        c = validated_config(changes, self.config)
        if self.active:
            raise ShareError('Stop sharing before changing its configuration')
        atomic(self.state / 'config.json', json.dumps(c))
        self.config = c
        self.message = 'Configuration saved; sharing remains off'
        self.revision += 1

    def journal(self):
        atomic(self.state / 'active.json', json.dumps(dict(active=self.active, blocked=self.blocked, forward_before=self.forward_before)))

    def rename_client(self, mac, name):
        names = dict(self.config['clientNames'])
        if mac == '*' and name == '':
            names = {}
        else:
            mac = mac.lower()
            if not re.fullmatch(r'(?:[0-9a-f]{2}:){5}[0-9a-f]{2}',mac):
                raise ShareError('Invalid client MAC address')
            if name:
                names[mac] = name
            else:
                names.pop(mac,None)
        c = validated_config({'clientNames':names},self.config)
        atomic(self.state/'config.json',json.dumps(c))
        self.config = c
        self.message = 'Local device names updated'

    def discover(self):
        addresses = json.loads(run(['ip', '-j', 'addr']))
        routes = json.loads(run(['ip', '-j', 'route']))
        devices = self.nm.devices()
        rows = []
        for a in addresses:
            name = a['ifname']
            if name == 'lo':
                continue
            info = devices.get(name, {})
            kind = ('wifi' if info.get('type') == 2 else 'cellular' if name.startswith(('epcell', 'wwan', 'rmnet')) else
                    'vpn' if info.get('type') in [16, 17, 29] or name.startswith(('tun', 'wg', 'tap')) else 'usb' if name.startswith(('usb', 'rndis')) else
                    'ethernet' if info.get('type') == 1 and Path('/sys/class/net', name, 'device').exists() else 'virtual')
            default = next((r for r in routes if r.get('dev') == name and r.get('dst') == 'default'), {})
            ipv4 = [x['local'] for x in a.get('addr_info', []) if x['family'] == 'inet' and x.get('scope') == 'global']
            rows.append(dict(interface=name, kind=kind, addresses=ipv4, gateway=default.get('gateway', ''),
                             default=bool(default), state=a.get('operstate', ''), managed=info.get('managed', False),
                             connection=info.get('connection', ''), dns=info.get('dns', []),
                             internet=self.probes.get(name, {}).get('ok', None),
                             connectivityDetail=self.probes.get(name, {}).get('detail', ''),
                             signal=info.get('signal'), speedMbps=info.get('speedMbps'),
                             downstream=any(j['interface'] == name for j in self.active.values())))
        return rows, routes

    def probe(self, interface, force=False):
        now = time.monotonic()
        p = self.probes.get(interface, {})
        if not force and now - p.get('time', -100) < 60:
            return p['ok']
        detail = ''
        try:
            # One small response, bound to the candidate interface. No identifiers.
            data = run(['curl', '-4', '--interface', interface, '--noproxy', '*', '--fail', '--silent',
                        '--max-time', '4', '--max-filesize', '4096', 'https://1.1.1.1/cdn-cgi/trace'], timeout=6)
            ok = '\nip=' in '\n' + data and '\nh=' in '\n' + data
            if not ok:
                detail = 'Unexpected connectivity-check response'
        except (ShareError, subprocess.TimeoutExpired) as error:
            ok = False
            detail = str(error) if isinstance(error, ShareError) else 'Connectivity check timed out'
        self.probes[interface] = dict(ok=ok, time=now, detail=detail)
        return ok

    def select(self, downstream, force=False):
        rows, _ = self.discover()
        vpn = self.nm.has_vpn() or any(x['kind'] == 'vpn' and x['state'] == 'UP' for x in rows)
        if vpn and self.config['vpnPolicy'] == 'ask':
            raise ShareError('A VPN is active. Explicitly choose normal or VPN sharing first')
        candidates = [x for x in rows if x['interface'] != downstream and not x['downstream'] and x['addresses'] and x['default']]
        if self.config['vpnPolicy'] == 'vpn':
            candidates = [x for x in candidates if x['kind'] == 'vpn']
        else:
            candidates = [x for x in candidates if x['kind'] in ['wifi', 'ethernet', 'cellular', 'usb']]
        if self.config['upstream'] != 'auto':
            candidates = [x for x in candidates if x['interface'] == self.config['upstream']]
        priorities = self.config['priority']
        candidates.sort(key=lambda x: priorities.index(x['kind']) if x['kind'] in priorities else 4)
        for candidate in candidates:
            if self.probe(candidate['interface'], force):
                return candidate
        raise ShareError('No verified internet source. Existing radios and roaming were not changed')

    def refresh_sources(self):
        rows,_=self.discover()
        vpn_active=self.nm.has_vpn() or any(x['kind']=='vpn' and x.get('state')=='UP' for x in rows)
        if vpn_active and self.config['vpnPolicy']=='ask':
            raise ShareError('Choose VPN routing policy before probing internet sources')
        for row in rows:
            if row['default'] and not row['downstream']:
                if self.config['vpnPolicy']=='vpn' and row['kind']!='vpn':
                    continue
                self.probe(row['interface'],force=True)
        self.last_monitor=0
        self.monitor()

    def dns(self, upstream):
        values = self.config['dns'] or upstream.get('dns', [])
        if not values and upstream['kind'] == 'cellular':
            p = Path('/run/ethermobile-data.json')
            if p.exists():
                data = json.loads(p.read_text())
                # The existing EtherMobile adapter reports effective DNS here.
                for key in ['dns', 'dns_servers', 'dns4']:
                    if isinstance(data.get(key), list):
                        values = data[key]
        if not values:
            raise ShareError('No upstream DNS reported; configure explicit IPv4 DNS servers')
        try:
            return [str(ipaddress.IPv4Address(v)) for v in values][:3]
        except ValueError:
            raise ShareError('Upstream DNS is not supported IPv4')

    def start(self, method, interface, replace_wifi=False):
        if method not in ['usb', 'hotspot', 'ethernet']:
            raise ShareError('Bluetooth PAN requires CONFIG_BT_BNEP; no PAN mode was started')
        if method=='hotspot' and (self.state/'radio-recovery-required').exists():
            raise ShareError('Hotspot disabled: the shared WLAN/IPA driver requires recovery')
        interface = iface_name(interface)
        if method in self.active:
            raise ShareError('This sharing method is already active')
        if len(self.active) >= 3:
            raise ShareError('At most three sharing interfaces')
        rows, routes = self.discover()
        target = next((x for x in rows if x['interface'] == interface), None)
        if not target or target['downstream']:
            raise ShareError('Downstream interface unavailable or already in use')
        if method == 'usb':
            if target['kind'] != 'usb' or '10.77.0.2' not in target['addresses']:
                raise ShareError('This release reuses the existing EtherPocket RNDIS recovery interface')
            if not Path('/run/etherpocket-dnsmasq.pid').exists():
                raise ShareError('USB recovery DHCP integration has not been installed; recovery remains unchanged')
        if method == 'hotspot':
            if target['kind'] != 'wifi' or not target['managed']:
                raise ShareError('Choose a NetworkManager Wi-Fi interface')
            if target['addresses'] and not replace_wifi:
                raise ShareError('Confirm replacing the current Wi-Fi connection before starting a hotspot')
            if not self.config['password']:
                raise ShareError('Set a WPA2 password before starting the hotspot')
        if method == 'ethernet' and (target['kind'] != 'ethernet' or target['addresses'] or target['default']):
            raise ShareError('Choose an unused physical Ethernet adapter; existing addresses are protected')
        # Verify the selected upstream before any network mutation.
        upstream = self.select(interface, force=True)
        dns = self.dns(upstream)
        subnet = '10.77.0.0/24' if method == 'usb' else choose_subnet(routes, self.config['subnet'], [j['subnet'] for j in self.active.values()])
        if interface == upstream['interface']:
            raise ShareError('Upstream and downstream must be different')
        number = next(x for x in range(3) if x not in [j['slot'] for j in self.active.values()])
        table = 24570 + number
        if run(['ip', 'route', 'show', 'table', str(table)], check=False) or re.search(r'^%d:' % table, run(['ip', 'rule']), re.M):
            raise ShareError('Reserved policy routing slot is in use; no foreign routes changed')
        gateway = '10.77.0.2' if method == 'usb' else str(ipaddress.ip_network(subnet).network_address + 1)
        j = dict(method=method, interface=interface, upstream=upstream['interface'], subnet=subnet,
                 gateway=gateway, dns=dns, tag='ESH%d' % number, table=table, slot=number,
                 profile='', previous=target['connection'], started=time.time(), health='Starting',
                 address_added=False, counters=self.counters(interface))
        if not self.active:
            self.forward_before = Path('/proc/sys/net/ipv4/ip_forward').read_text().strip()
        self.active[method] = j
        self.journal()  # journal before mutation; cleanup is idempotent after a crash
        try:
            self.install_firewall(j)
            self.routing(j, upstream)
            if method != 'usb':
                j['profile'] = str(uuid.uuid4())
                self.journal()
                self.nm.activate_downstream(j, self.config)
            self.start_dns(j)
            Path('/proc/sys/net/ipv4/ip_forward').write_text('1\n')
            self.clear_stop_guard(interface)
            j['health'] = 'Sharing configured; waiting for client traffic'
            self.journal()
            self.message = 'Sharing started. Switching upstream can interrupt existing TCP connections.'
            self.revision += 1
        except Exception:
            self.stop(method)
            raise

    def start_concurrent_hotspot(self, parent):
        if (self.state/'radio-recovery-required').exists():
            raise ShareError('Hotspot disabled: the shared WLAN/IPA driver requires recovery')
        parent = iface_name(parent)
        if 'hotspot' in self.active:
            raise ShareError('A hotspot is already active')
        if not self.config['password']:
            raise ShareError('Set a WPA2 password before starting the hotspot')
        phy = Path('/sys/class/net', parent, 'phy80211')
        if not phy.exists():
            raise ShareError('Parent Wi-Fi radio unavailable')
        self.select('eshap0', force=True)
        marker=self.state/'virtual.json'
        reuse=False
        if Path('/sys/class/net/eshap0').exists():
            if not marker.exists():
                raise ShareError('Concurrent AP name is already in use; existing interface preserved')
            owned=json.loads(marker.read_text())
            actual=Path('/sys/class/net/eshap0/phy80211').resolve().name
            if owned.get('phy')!=actual or actual!=phy.resolve().name or owned.get('parent')!=parent:
                raise ShareError('Concurrent AP ownership changed')
            mac=Path('/sys/class/net/eshap0/address').read_text().strip()
            if owned.get('mac',mac)!=mac or self.nm.devices().get('eshap0',{}).get('connection'):
                raise ShareError('Concurrent AP is already configured by another connection')
            reuse=True
        else:
            atomic(marker, json.dumps(dict(interface='eshap0', parent=parent, phy=phy.resolve().name)))
        try:
            if not reuse:
                run(['/usr/sbin/iw', 'phy', phy.resolve().name, 'interface', 'add', 'eshap0', 'type', '__ap'])
            for _ in range(30):
                if 'eshap0' in self.nm.devices():
                    break
                time.sleep(.2)
            self.start('hotspot', 'eshap0')
            self.active['hotspot']['virtual'] = True
            self.journal()
        except Exception:
            if 'hotspot' not in self.active:
                self.remove_virtual()
            raise

    def remove_virtual(self):
        marker = self.state / 'virtual.json'
        if marker.exists():
            v = json.loads(marker.read_text())
            assert v['interface'] == 'eshap0'
            phy = Path('/sys/class/net/eshap0/phy80211')
            if phy.exists():
                if phy.resolve().name != v['phy']:
                    raise ShareError('Concurrent interface ownership changed')
                result=subprocess.run(['/usr/sbin/iw','dev','eshap0','del'],capture_output=True,timeout=8)
                if result.returncode==245:  # downstream driver returns -EAGAIN
                    # The downstream driver refuses teardown during recovery.
                    # Retain ownership of its down netdev and block further AP
                    # starts until an administrator verifies radio recovery.
                    run(['ip','link','set','eshap0','down'])
                    v.update(parked=True,mac=Path('/sys/class/net/eshap0/address').read_text().strip())
                    atomic(marker,json.dumps(v))
                    atomic(self.state/'radio-recovery-required','WLAN teardown returned EAGAIN; verify driver recovery before clearing.\n')
                    return
                if result.returncode:
                    raise ShareError('The driver could not release its owned AP interface')
            marker.unlink()

    def counters(self, interface):
        def read(key):
            try:
                return int(Path('/sys/class/net', interface, 'statistics', key).read_text())
            except OSError:
                return 0
        return dict(rx=read('rx_bytes'), tx=read('tx_bytes'))

    def install_firewall(self, j):
        rules, hooks = firewall_rules(j)
        chains = sorted(set((a, t, c) for a, t, c, _ in rules))
        for program, table, chain in chains:
            # A preexisting chain is never adopted or flushed.
            if subprocess.run([program, '-w', '3', '-t', table, '-S', chain], capture_output=True).returncode == 0:
                raise ShareError('Reserved firewall chain already exists')
            j.setdefault('chains', []).append([program, table, chain])
            self.journal()
            result = subprocess.run([program, '-w', '3', '-t', table, '-N', chain], capture_output=True)
            if result.returncode:
                raise ShareError('Firewall unavailable or owned chain already exists')
        for program, table, chain, args in rules:
            run([program, '-w', '3', '-t', table, '-A', chain] + args)
        for program, table, chain, args in hooks:
            j.setdefault('hooks', []).append([program, table, chain, args])
            self.journal()
            run([program, '-w', '3', '-t', table, '-I', chain, '1'] + args)

    def routing(self, j, upstream):
        table, interface = str(j['table']), upstream['interface']
        # A terminal unreachable default prevents lookup falling through to main.
        run(['ip', 'route', 'replace', 'unreachable', 'default', 'metric', '32767', 'table', table])
        args = ['ip', 'route', 'replace', 'default']
        if upstream['gateway']:
            args += ['via', upstream['gateway'], 'onlink']
        run(args + ['dev', interface, 'metric', '10', 'table', table])
        existing = run(['ip', 'rule'])
        if not re.search(r'^%d:' % j['table'], existing, re.M):
            # iif restricts the policy to forwarded client packets. Local replies
            # from the recovery address must continue to use its connected route.
            run(['ip', 'rule', 'add', 'priority', table, 'iif', j['interface'], 'from', j['subnet'], 'lookup', table])
        # DNS forwarding originates on the phone, but must use the same upstream.
        # dnsmasq binds its upstream socket to the selected interface explicitly.

    def dns_config(self, j):
        interface, address = j['interface'], j['gateway']
        net = ipaddress.ip_network(j['subnet'])
        low = '10.77.0.1' if j['method'] == 'usb' else str(net.network_address + self.config['dhcpStart'])
        high = low if j['method'] == 'usb' else str(net.network_address + self.config['dhcpEnd'])
        lines = ['user=root', 'bind-dynamic', 'interface=' + interface, 'listen-address=' + address,
                 'except-interface=lo', 'no-resolv', 'domain-needed', 'bogus-priv',
                 'dhcp-range=%s,%s,%s,%sm' % (low, high, net.netmask, self.config['leaseMinutes']),
                 'dhcp-option=option:router,' + address, 'dhcp-option=option:dns-server,' + address,
                 'dhcp-leasefile=' + str(self.runtime / (interface + '.leases')),
                 'pid-file=' + str(self.runtime / (interface + '.pid'))]
        lines += ['server=%s@%s' % (d, j['upstream']) for d in j['dns']]
        return '\n'.join(lines) + '\n'

    def start_dns(self, j):
        if j['method'] == 'usb':
            # Existing recovery DHCP owner reads these option files on SIGHUP.
            atomic(self.runtime / 'usb.options', 'option:router,10.77.0.2\noption:dns-server,10.77.0.2\n')
            atomic(self.runtime / 'usb.servers', ''.join('server=%s@%s\n' % (d, j['upstream']) for d in j['dns']))
            self.signal_usb()
            return
        config = self.runtime / (j['interface'] + '.conf')
        atomic(config, self.dns_config(j))
        run(['/usr/sbin/dnsmasq', '--test', '--conf-file=' + str(config)])
        run(['/usr/sbin/dnsmasq', '--conf-file=' + str(config)])

    def signal_usb(self):
        pid = int(Path('/run/etherpocket-dnsmasq.pid').read_text())
        if Path('/proc', str(pid), 'comm').read_text().strip() != 'dnsmasq':
            raise ShareError('Recovery DHCP process identity changed')
        os.kill(pid, signal.SIGHUP)

    def stop_guard(self, interface):
        # While another downstream is sharing, ip_forward remains enabled.
        # An old DHCP gateway must not allow a stopped client to use main routes.
        self.blocked[interface] = True
        self.journal()
        for program in [IPT, IP6T]:
            for direction in ['-i', '-o']:
                args = [direction, interface, '-m', 'comment', '--comment', 'ethershare-stopped', '-j', 'DROP']
                if subprocess.run([program, '-w', '3', '-C', 'FORWARD'] + args, capture_output=True).returncode:
                    run([program, '-w', '3', '-I', 'FORWARD', '1'] + args)

    def clear_stop_guard(self, interface):
        if interface not in self.blocked:
            return
        for program in [IPT, IP6T]:
            for direction in ['-i', '-o']:
                args = [direction, interface, '-m', 'comment', '--comment', 'ethershare-stopped', '-j', 'DROP']
                if subprocess.run([program, '-w', '3', '-C', 'FORWARD'] + args, capture_output=True).returncode == 0:
                    run([program, '-w', '3', '-D', 'FORWARD'] + args)
        del self.blocked[interface]
        self.journal()

    def stop(self, method):
        j = self.active.get(method)
        if not j:
            return
        self.stop_guard(j['interface'])
        errors = []
        def attempt(fn):
            try:
                fn()
            except Exception as e:
                errors.append(str(e))
        # Stop forwarding first, including when restoring a failed activation.
        attempt(lambda: run(['ip', 'route', 'del', 'default', 'metric', '10', 'table', str(j['table'])], check=False))
        if method == 'usb':
            atomic(self.runtime / 'usb.options', 'option:router\noption:dns-server\n')
            atomic(self.runtime / 'usb.servers', '')
            attempt(self.signal_usb)
        else:
            pidfile = self.runtime / (j['interface'] + '.pid')
            if pidfile.exists():
                def terminate():
                    pid = int(pidfile.read_text())
                    cmdline = Path('/proc', str(pid), 'cmdline').read_bytes()
                    if str(self.runtime / (j['interface'] + '.conf')).encode() not in cmdline:
                        raise ShareError('DNS process identity changed')
                    os.kill(pid, signal.SIGTERM)
                attempt(terminate)
            if j.get('profile'):
                attempt(lambda: self.nm.remove_downstream(j))
        for program, table, chain, args in reversed(j.get('hooks', [])):
            if subprocess.run([program, '-w', '3', '-t', table, '-C', chain] + args, capture_output=True).returncode == 0:
                attempt(lambda p=program, t=table, c=chain, a=args: run([p, '-w', '3', '-t', t, '-D', c] + a))
        for program, table, chain in reversed(j.get('chains', [])):
            if subprocess.run([program, '-w', '3', '-t', table, '-S', chain], capture_output=True).returncode == 0:
                attempt(lambda p=program, t=table, c=chain: run([p, '-w', '3', '-t', t, '-F', c]))
                attempt(lambda p=program, t=table, c=chain: run([p, '-w', '3', '-t', t, '-X', c]))
        attempt(lambda: run(['ip', 'rule', 'del', 'priority', str(j['table']), 'iif', j['interface'], 'from', j['subnet'], 'lookup', str(j['table'])], check=False))
        # Only the table reserved and verified empty at activation is cleared.
        attempt(lambda: run(['ip', 'route', 'flush', 'table', str(j['table'])]))
        if errors:
            self.message = 'Cleanup incomplete; firewall guard retained where possible. Check diagnostics.'
            j['health'] = 'Cleanup requires attention'
            self.journal()
            raise ShareError(self.message)
        del self.active[method]
        self.seen_clients={x for x in self.seen_clients if x[0]!=method}
        if method == 'hotspot' and j['interface'] == 'eshap0':
            self.remove_virtual()
        if not self.active and self.forward_before is not None:
            Path('/proc/sys/net/ipv4/ip_forward').write_text(self.forward_before + '\n')
            if self.forward_before == '0':
                for interface in list(self.blocked):
                    self.clear_stop_guard(interface)
            self.forward_before = None
        self.journal()
        self.message = 'Sharing stopped; recovery networking preserved'
        self.revision += 1

    def recover(self):
        p = self.state / 'active.json'
        if p.exists():
            data = json.loads(p.read_text())
            self.active = data['active']
            self.blocked = data.get('blocked', {})
            self.forward_before = data.get('forward_before')
            for method in list(self.active):
                self.stop(method)
        if not any(j['interface'] == 'eshap0' for j in self.active.values()):
            self.remove_virtual()

    def clients(self, j):
        p = Path('/run/etherpocket-dnsmasq.leases') if j['method'] == 'usb' else self.runtime / (j['interface'] + '.leases')
        clients = []
        if p.exists():
            for line in p.read_text().splitlines()[:128]:
                fields = line.split()
                if len(fields) >= 4:
                    if fields[0].isdigit() and int(fields[0]) not in [0] and int(fields[0]) < time.time():
                        continue
                    clients.append(dict(expires=fields[0], mac=fields[1], address=fields[2], name=self.config['clientNames'].get(fields[1].lower(),fields[3]),
                                        method=j['method'], evidence='DHCP lease; presence not guaranteed'))
        if j['method'] == 'hotspot':
            # Read only the active AP's station table; this does not scan.
            text = run(['/usr/sbin/iw','dev',j['interface'],'station','dump'],check=False)
            for block in re.split(r'(?m)^Station ',text)[1:]:
                mac = block.split()[0].lower()
                if not re.fullmatch(r'(?:[0-9a-f]{2}:){5}[0-9a-f]{2}',mac):
                    continue
                entry = next((x for x in clients if x['mac'].lower()==mac),None)
                if entry is None:
                    entry=dict(mac=mac,address='Not leased',name=self.config['clientNames'].get(mac,'Wi-Fi client'),method=j['method'])
                    clients.append(entry)
                def value(key):
                    m=re.search(r'(?m)^\s*'+re.escape(key)+r':\s*(\d+)',block)
                    return int(m.group(1)) if m else None
                entry.update(evidence='Associated Wi-Fi station',connectedSeconds=value('connected time'),upload=value('rx bytes'),download=value('tx bytes'))
        return clients

    def traffic_health(self, j):
        """Use forwarded packets, excluding USB recovery SSH/DHCP traffic."""
        if j['health'].startswith(('Upstream lost', 'No usable')):
            return j['health']
        output = run([IPT, '-w', '3', '-L', j['tag']+'F', '-nvx'], check=False)
        sent = received = 0
        for line in output.splitlines():
            fields = line.split()
            if len(fields) < 7 or not fields[0].isdigit() or fields[2] != 'ACCEPT':
                continue
            if fields[5:7] == [j['interface'], j['upstream']]:
                sent += int(fields[0])
            elif fields[5:7] == [j['upstream'], j['interface']]:
                received += int(fields[0])
        if sent and received:
            return 'Client traffic forwarded in both directions'
        if sent:
            return 'Client traffic sent; waiting for replies'
        if j['method'] == 'usb':
            return 'USB configured; renew the USB network DHCP lease on the computer if internet is unavailable'
        return j['health']

    def snapshot(self):
        rows, routes = self.discover()
        c = copy.deepcopy(self.config)
        c['passwordSet'] = bool(c.pop('password'))
        active, clients = [], []
        for j in self.active.values():
            now = self.counters(j['interface'])
            instant = time.monotonic()
            previous = self.rates.get(j['interface'], dict(time=instant, **now))
            elapsed = max(.001, instant-previous['time'])
            speed = dict(uploadBps=max(0, now['rx']-previous['rx'])/elapsed,
                         downloadBps=max(0, now['tx']-previous['tx'])/elapsed)
            self.rates[j['interface']] = dict(time=instant, **now)
            active.append(dict(method=j['method'], interface=j['interface'], upstream=j['upstream'],
                               gateway=j['gateway'], subnet=j['subnet'], dns=j['dns'], health=self.traffic_health(j),
                               started=j['started'], upload=max(0, now['rx']-j['counters']['rx']),
                               download=max(0, now['tx']-j['counters']['tx']), **speed))
            clients += self.clients(j)
        usb = any(Path('/run/etherpocket-dnsmasq.pid').exists() and r['kind'] == 'usb' for r in rows)
        controllers = []
        for controller in Path('/sys/class/udc').glob('*'):
            try:
                controllers.append(dict(controller=controller.name,state=(controller/'state').read_text().strip()))
            except OSError:
                pass
        host = any(x['state'] in ['configured','suspended'] for x in controllers)
        return dict(version=1, revision=self.revision, message=self.message, config=c, interfaces=rows,
                    active=active, clients=clients, routes=routes, usbReady=usb,
                    usbControllers=controllers,usbHostDetected=host,
                    hotspotAvailable=not (self.state/'radio-recovery-required').exists(),
                    radioWarning='Hotspot quarantined after WLAN recovery failure; driver stability validation required' if (self.state/'radio-recovery-required').exists() else '',
                    bluetooth='Requires kernel CONFIG_BT_BNEP', ipv6='IPv4 sharing only; IPv6 forwarding blocked',
                    security='Downstream management blocked; existing USB recovery host retains SSH',
                    countersScope='Interface totals since sharing started, including recovery traffic',
                    vpn='Explicit policy required when a VPN is active',
                    usbProtocol='Existing RNDIS; NCM unverified; ECM absent in kernel')

    def monitor(self):
        now = time.monotonic()
        for method, j in list(self.active.items()):
            if not Path('/sys/class/net', j['interface']).exists():
                self.stop(method)
                self.message = 'Downstream disconnected; sharing stopped'
                continue
            if self.config['timeoutMinutes'] and time.time() - j['started'] > self.config['timeoutMinutes'] * 60:
                self.stop(method)
                self.message = 'Sharing time limit reached'
                continue
            for client in self.clients(j):
                if len(self.seen_clients)>4096:
                    self.seen_clients.clear()
                key=(method,client['mac'])
                if key not in self.seen_clients:
                    self.seen_clients.add(key)
                    self.events.append(('Internet Sharing','%s on %s: %s' % ('Client associated' if client['evidence']=='Associated Wi-Fi station' else 'DHCP lease present',method,client['name'])))
            rows, _ = self.discover()
            vpn_block = self.config['vpnPolicy'] == 'ask' and (self.nm.has_vpn() or any(x['kind']=='vpn' and x.get('state')=='UP' for x in rows))
            if now - self.last_monitor < 60 and not vpn_block:
                continue
            if vpn_block or not self.probe(j['upstream'], force=True):
                # Terminal route + strict egress guards prevent an accidental fallback.
                run(['ip', 'route', 'del', 'default', 'metric', '10', 'table', str(j['table'])], check=False)
                j['health'] = 'Upstream lost; forwarding blocked'
                self.message = j['health']
                if self.config['failover'] and self.config['upstream'] == 'auto':
                    try:
                        alternate = self.select(j['interface'])
                        if alternate['interface'] == j['upstream']:
                            self.routing(j, alternate)
                            j['health'] = 'Upstream restored'
                        else:
                            # Keep INPUT isolation continuously installed. Legacy
                            # restore commits only the owned forwarding/NAT chains.
                            j['upstream'], j['dns'] = alternate['interface'], self.dns(alternate)
                            self.journal()
                            rules, _ = firewall_rules(j)
                            for table, chain in [('filter', j['tag']+'F'), ('nat', j['tag']+'N')]:
                                body = '*' + table + '\n-F ' + chain + '\n'
                                body += ''.join('-A '+chain+' '+' '.join(a)+'\n' for p,t,c,a in rules if p==IPT and t==table and c==chain)
                                body += 'COMMIT\n'
                                run(['/usr/sbin/iptables-legacy-restore', '-w', '3', '--noflush'], input=body)
                            self.routing(j, alternate)
                            if method == 'usb':
                                self.start_dns(j)
                            else:
                                # restart only our DNS process, preserving its leases
                                pid = int((self.runtime / (j['interface'] + '.pid')).read_text())
                                os.kill(pid, signal.SIGTERM)
                                time.sleep(.15)
                                self.start_dns(j)
                            j['health'] = 'Failover completed; TCP connections may reconnect'
                            self.message = j['health']
                    except Exception:
                        j['health'] = 'No usable alternative; forwarding blocked'
            elif j['health'].startswith(('Upstream lost', 'No usable')):
                rows, _ = self.discover()
                u = next((x for x in rows if x['interface'] == j['upstream']), None)
                if u:
                    self.routing(j, u)
                    j['health'] = 'Upstream restored'
            self.journal()
        if now - self.last_monitor >= 60:
            self.last_monitor = now
