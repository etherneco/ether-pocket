import copy
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

spec = importlib.util.spec_from_file_location('sharecore', Path(__file__).resolve().parents[1] / 'ethershare/core.py')
c = importlib.util.module_from_spec(spec)
spec.loader.exec_module(c)


class PolicyTests(unittest.TestCase):
    def test_defaults_no_implicit_activation(self):
        config = c.validated_config({})
        self.assertFalse(config['autostart'])
        self.assertFalse(config['failover'])
        self.assertEqual(config['vpnPolicy'], 'ask')

    def test_validation(self):
        bad = [dict(upstream='usb0;reboot'), dict(password='short'), dict(channel=36),
               dict(subnet='8.8.8.0/24'), dict(subnet='192.168.1.1/24'),
               dict(priority=['wifi']*3), dict(dns=['127.0.0.1']), dict(dns=['a\nport=0']),
               dict(autostart=1), dict(ssid='x\nfoo'), dict(band='a'), dict(unknown=True)]
        bad += [dict(dhcpStart=201,dhcpEnd=20), dict(dhcpStart=1), dict(leaseMinutes=0)]
        for update in bad:
            with self.subTest(update=update), self.assertRaises(c.ShareError):
                c.validated_config(update)

    def test_auto_subnet_avoids_broad_lan_and_other_shares(self):
        routes = [{'dst':'10.0.0.0/8'}, {'dst':'192.168.73.0/24'}, {'dst':'default'}]
        self.assertEqual(c.choose_subnet(routes, reserved=['192.168.74.0/24']), '192.168.75.0/24')
        with self.assertRaises(c.ShareError):
            c.choose_subnet(routes, '10.20.30.0/24')

    def test_management_isolation_and_egress_guards(self):
        j = dict(interface='usb0',upstream='epcell0',subnet='10.77.0.0/24',tag='ESH0',method='usb')
        rules, hooks = c.firewall_rules(j)
        forward = [a for p,t,ch,a in rules if p==c.IPT and ch=='ESH0F']
        self.assertEqual(forward[-1], ['-j','DROP'])
        self.assertTrue(any('-o' in a and a[a.index('-o')+1]=='epcell0' and a[-1]=='ACCEPT' for a in forward))
        self.assertTrue(any(p==c.IP6T and ch=='ESH0F' and a==['-j','DROP'] for p,t,ch,a in rules))
        incoming = [a for p,t,ch,a in rules if p==c.IPT and ch=='ESH0I']
        self.assertTrue(any('10.77.0.1' in a and '22' in a for a in incoming))
        j['method']='hotspot'
        self.assertFalse(any('22' in a for p,t,ch,a in c.firewall_rules(j)[0]))

    def make_core(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        class NM:
            vpn=False
            def has_vpn(self): return self.vpn
        core = c.LinuxShare(NM(), Path(tmp.name)/'state', Path(tmp.name)/'run')
        core.discover=lambda: ([dict(interface='epcell0',kind='cellular',addresses=['10.2.3.4'],default=True,downstream=False),
                               dict(interface='wlan0',kind='wifi',addresses=['10.1.2.3'],default=True,downstream=False)], [])
        return core

    def test_source_requires_connectivity(self):
        core=self.make_core();core.probe=lambda iface,force=False: iface=='epcell0'
        self.assertEqual(core.select('usb0')['interface'],'epcell0')
        core.probe=lambda *args:False
        with self.assertRaises(c.ShareError): core.select('usb0')

    def test_usb_health_requires_forwarded_replies_not_recovery_traffic(self):
        core = self.make_core()
        j = dict(method='usb', interface='usb0', upstream='epcell0', tag='ESH0', health='Sharing configured; waiting for client traffic')
        with patch.object(c, 'run', return_value=''):
            self.assertIn('renew', core.traffic_health(j))
        sent = '2 120 ACCEPT all -- usb0 epcell0 10.77.0.0/24 0.0.0.0/0\n'
        with patch.object(c, 'run', return_value=sent):
            self.assertIn('waiting for replies', core.traffic_health(j))
        with patch.object(c, 'run', return_value=sent+'3 200 ACCEPT all -- epcell0 usb0 0.0.0.0/0 10.77.0.0/24\n'):
            self.assertIn('both directions', core.traffic_health(j))
        j['health'] = 'Upstream lost; forwarding blocked'
        with patch.object(c, 'run', side_effect=AssertionError('Blocked state must take precedence')):
            self.assertEqual(core.traffic_health(j), j['health'])

    def test_vpn_requires_explicit_policy(self):
        core=self.make_core();core.nm.vpn=True;core.probe=lambda *args:True
        with self.assertRaises(c.ShareError):core.select('usb0')
        core.config['vpnPolicy']='vpn'
        with self.assertRaises(c.ShareError):core.select('usb0')
        core.config['vpnPolicy']='normal'
        self.assertEqual(core.select('usb0')['interface'],'wlan0')

    def test_dns_no_silent_public_fallback(self):
        core=self.make_core()
        with self.assertRaises(c.ShareError):core.dns(dict(kind='wifi',dns=[]))
        self.assertEqual(core.dns(dict(kind='wifi',dns=['10.1.1.1'])),['10.1.1.1'])

    def test_policy_route_has_terminal_guard(self):
        core=self.make_core();calls=[]
        with patch.object(c,'run',side_effect=lambda a,**kw:calls.append(a) or ''):
            core.routing(dict(table=24570,subnet='10.77.0.0/24',interface='usb0'),dict(interface='epcell0',gateway='10.2.3.1'))
        self.assertIn('unreachable',calls[0])
        self.assertIn('epcell0',calls[1])
        self.assertIn('from',calls[-1])
        self.assertIn('iif',calls[-1])
        self.assertEqual(calls[-1][calls[-1].index('iif')+1], 'usb0')

    def test_recovery_journal_before_mutations_and_private_config(self):
        core=self.make_core();core.save(dict(password='secure-test-password'))
        p=core.state/'config.json'
        self.assertEqual(p.stat().st_mode&0o777,0o600)
        self.assertEqual(json.loads(p.read_text())['password'],'secure-test-password')
        core.discover=lambda:([],[])
        snapshot=core.snapshot()
        self.assertTrue(snapshot['config']['passwordSet'])
        self.assertNotIn('secure-test-password',json.dumps(snapshot))

    def test_monitor_failure_blocks_forwarding_without_radio_actions(self):
        core=self.make_core();core.last_monitor=-100;core.probe=lambda *a,**kw:False
        core.active={'usb':dict(interface='usb0',table=24570,upstream='epcell0',health='',started=0)}
        calls=[]
        with patch.object(core,'clients',return_value=[]),patch.object(c.Path,'exists',return_value=True),patch.object(c,'run',side_effect=lambda a,**kw:calls.append(a) or ''):
            core.monitor()
        self.assertIn('del',calls[0]);self.assertIn('default',calls[0])
        self.assertEqual(core.active['usb']['health'],'Upstream lost; forwarding blocked')
        self.assertFalse(any('nmcli' in a for a in calls))

    def test_config_cannot_change_under_live_clients(self):
        core=self.make_core();core.active={'usb':{}}
        with self.assertRaises(c.ShareError):core.save(dict(upstream='epcell0'))

    def test_stopped_downstream_keeps_guard_while_others_share(self):
        core=self.make_core();calls=[]
        class Result:returncode=1
        with patch.object(c.subprocess,'run',return_value=Result()),patch.object(c,'run',side_effect=lambda a,**kw:calls.append(a) or ''):
            core.stop_guard('usb0')
        self.assertIn('usb0',core.blocked)
        self.assertEqual(len(calls),4)
        self.assertTrue(all('DROP' in a and 'FORWARD' in a for a in calls))
        with patch.object(c.subprocess,'run',return_value=type('R',(),{'returncode':0})()),patch.object(c,'run',side_effect=lambda a,**kw:calls.append(a) or ''):
            core.clear_stop_guard('usb0')
        self.assertFalse(core.blocked)
        self.assertTrue(all('-D' in a for a in calls[-4:]))

    def test_dns_stays_on_selected_interface_and_range(self):
        core=self.make_core();core.config.update(dhcpStart=40,dhcpEnd=50)
        config=core.dns_config(dict(interface='eshap0',gateway='192.168.73.1',subnet='192.168.73.0/24',method='hotspot',upstream='wlan0',dns=['10.1.1.1']))
        self.assertIn('server=10.1.1.1@wlan0',config)
        self.assertIn('no-resolv',config)
        self.assertIn('192.168.73.40,192.168.73.50',config)

    def test_local_device_names_update_during_sharing(self):
        core=self.make_core();core.active={'usb':{}}
        core.rename_client('aa:bb:cc:dd:ee:ff','My laptop')
        self.assertEqual(core.config['clientNames']['aa:bb:cc:dd:ee:ff'],'My laptop')
        with self.assertRaises(c.ShareError):core.rename_client('bad','x')
        core.rename_client('*','')
        self.assertEqual(core.config['clientNames'],{})

    def test_driver_eagain_parks_only_owned_virtual_interface(self):
        core=self.make_core();root=core.state.parent
        virtual=root/'virtual';virtual.mkdir()
        phy=root/'phy0';phy.mkdir();(virtual/'phy80211').symlink_to(phy,target_is_directory=True)
        (virtual/'address').write_text('02:00:00:00:00:01')
        marker=core.state/'virtual.json';marker.write_text(json.dumps(dict(interface='eshap0',parent='wlan0',phy='phy0')))
        original=c.Path
        def paths(*args):
            text=str(original(*args))
            if text.startswith('/sys/class/net/eshap0'):
                return virtual / text.removeprefix('/sys/class/net/eshap0').lstrip('/')
            return original(*args)
        commands=[]
        with patch.object(c,'Path',side_effect=paths),patch.object(c.subprocess,'run',return_value=type('R',(),{'returncode':245})()),patch.object(c,'run',side_effect=lambda a,**kw:commands.append(a) or ''):
            core.remove_virtual()
        self.assertTrue(json.loads(marker.read_text())['parked'])
        self.assertEqual(commands,[['ip','link','set','eshap0','down']])
        self.assertTrue((core.state/'radio-recovery-required').exists())

    def test_radio_quarantine_rejects_hotspot_before_network_mutation(self):
        core=self.make_core();(core.state/'radio-recovery-required').write_text('fault')
        with patch.object(c,'run',side_effect=AssertionError('must not mutate')):
            with self.assertRaises(c.ShareError):core.start('hotspot','wlan0')
            with self.assertRaises(c.ShareError):core.start_concurrent_hotspot('wlan0')

    def test_explicit_source_checks_respect_vpn_policy(self):
        core=self.make_core();core.nm.vpn=True
        calls=[];core.probe=lambda iface,**kw:calls.append(iface) or True
        with self.assertRaises(c.ShareError):core.refresh_sources()
        self.assertFalse(calls)
        core.config['vpnPolicy']='vpn'
        core.discover=lambda:([dict(interface='wlan0',kind='wifi',state='UP',default=True,downstream=False),dict(interface='wg0',kind='vpn',state='UP',default=True,downstream=False)],[])
        core.refresh_sources()
        self.assertEqual(calls,['wg0'])


if __name__=='__main__':unittest.main()
