"""Opt-in Windows USB traffic acceptance; never starts a radio or hotspot.

Requires a separately verified Wi-Fi SSH recovery path before renewing the
named Windows USB adapter's DHCP lease. Stops sharing and restores source policy.
"""
import argparse
import json
from pathlib import Path
import runpy
import shlex
import subprocess

ROOT = Path(__file__).resolve().parent.parent
SSH = runpy.run_path(str(ROOT / 'scripts/deploy-ethermobile.py'))['SSH']
PRELUDE = """import dbus,json,pathlib
assert pathlib.Path('/etc/etherpocket/disk-identity').read_text().strip()=='GM1920-548cb338-mobian-sda21'
api=dbus.Interface(dbus.SystemBus().get_object('com.etherneco.EtherShare1','/com/etherneco/EtherShare1'),'com.etherneco.EtherShare1')
"""


def remote(code, timeout=85):
    r = subprocess.run(SSH + ['python3 -c ' + shlex.quote(code)],
                       capture_output=True, text=True, timeout=timeout)
    if r.returncode:
        raise RuntimeError(r.stderr[-2500:])
    return r.stdout


def request(code):
    remote('import subprocess\nr=subprocess.run(' + repr([
        '/usr/sbin/runuser', '-u', 'mobian', '--', 'python3', '-c',
        PRELUDE + code]) + ',capture_output=True,text=True,timeout=75)\n'
        'assert r.returncode==0,r.stderr')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source', choices=['wlan0', 'epcell0'], required=True)
    parser.add_argument('--adapter', required=True)
    args = parser.parse_args()
    wifi = remote("import subprocess,json\na=json.loads(subprocess.check_output(['ip','-j','-4','addr','show','wlan0'],text=True));print(a[0]['addr_info'][0]['local'])").strip()
    alternate_ssh = SSH[:-1] + ['-o', 'HostKeyAlias=10.77.0.2', 'root@' + wifi]
    alt = subprocess.run(alternate_ssh + ['cat /etc/etherpocket/disk-identity'],
                         capture_output=True, text=True, timeout=12)
    assert alt.returncode == 0 and alt.stdout.strip() == 'GM1920-548cb338-mobian-sda21'
    previous = json.loads(remote(PRELUDE + "s=json.loads(api.GetState());assert not s['active'];c=json.loads(pathlib.Path('/var/lib/ethershare/config.json').read_text());print(json.dumps({k:c[k] for k in ['upstream','failover']}))"))
    report = {'source': args.source, 'alternate_wifi_ssh_verified': True}
    try:
        request("api.Configure(" + repr(json.dumps({'upstream': args.source, 'failover': False})) + ",timeout=20);api.Start('usb','usb0',False,timeout=60)")
        r = subprocess.run(['ipconfig', '/renew', args.adapter], capture_output=True, timeout=40)
        report['dhcp_renew_exit'] = r.returncode
        r = subprocess.run(['curl.exe', '-4', '--interface', '10.77.0.1', '--noproxy', '*', '--fail', '--silent', '--max-time', '10', '--output', 'NUL', '--write-out', '%{http_code}', 'https://1.1.1.1/cdn-cgi/trace'], capture_output=True, text=True, timeout=14)
        report['https'] = {'exit': r.returncode, 'http': r.stdout}
        r = subprocess.run(['powershell', '-NoProfile', '-Command', "Resolve-DnsName www.debian.org -Server 10.77.0.2 -DnsOnly -ErrorAction Stop | Out-Null"], capture_output=True, timeout=15)
        report['dns_exit'] = r.returncode
        report['rules'] = json.loads(remote("import subprocess,json\nprint(json.dumps(subprocess.check_output(['/usr/sbin/iptables-legacy-save','-c'],text=True).splitlines()))"))
    finally:
        request("api.Stop('usb',timeout=30);api.Configure(" + repr(json.dumps(previous)) + ',timeout=20)')
        # Windows retains an earlier router when a renewal omits that option.
        # Release this adapter's lease first, with live alternate recovery.
        alt = subprocess.run(alternate_ssh + ['cat /etc/etherpocket/disk-identity'],
                             capture_output=True, text=True, timeout=12)
        assert alt.returncode == 0 and alt.stdout.strip() == 'GM1920-548cb338-mobian-sda21'
        r = subprocess.run(['ipconfig', '/release', args.adapter], capture_output=True, timeout=40)
        report['cleanup_dhcp_release_exit'] = r.returncode
        r = subprocess.run(['ipconfig', '/renew', args.adapter], capture_output=True, timeout=40)
        report['cleanup_dhcp_renew_exit'] = r.returncode
        (ROOT / ('evidence/ethershare-post-reboot-' + args.source + '-usb.json')).write_text(json.dumps(report, indent=2) + '\n')
    print(json.dumps({k:v for k,v in report.items() if k != 'rules'}, indent=2))
    assert report['https'] == {'exit': 0, 'http': '200'} and report['dns_exit'] == 0
