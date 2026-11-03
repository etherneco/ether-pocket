"""Verify automatic cellular internet after reboot without collecting SIM data."""
from pathlib import Path
import json
import runpy
import shlex
import subprocess
import time

ROOT = Path(__file__).resolve().parent.parent
SSH = runpy.run_path(str(ROOT / 'scripts/deploy-ethermobile.py'))['SSH']
REMOTE = r'''
import json,pathlib,subprocess
assert pathlib.Path('/etc/etherpocket/disk-identity').read_text().strip()=='GM1920-548cb338-mobian-sda21'
def run(*args):
    p=subprocess.run(args,capture_output=True,text=True,timeout=30)
    return {'exit':p.returncode,'stdout':p.stdout.strip(),'stderr':p.stderr.strip()}
state=pathlib.Path('/run/ethermobile-data.json')
data={'boot':pathlib.Path('/proc/sys/kernel/random/boot_id').read_text().strip(),
 'enabled':run('systemctl','is-enabled','ethermobile-data')['stdout'],
 'services':{s:run('systemctl','is-active',s)['stdout'] for s in ['ethermobile-data','ethermobile-ipa','ModemManager','NetworkManager','ssh','bluetooth']},
 'connected':state.exists() and json.loads(state.read_text()).get('connected') is True}
if data['connected']:
    data['routes']=run('ip','route')['stdout']
    data['ip_ping']=run('ping','-c','3','-W','3','1.1.1.1')
    data['dns_ping']=run('ping','-c','3','-W','3','example.com')
    data['https']=run('curl','--interface','epcell0','-4','--max-time','20','-sS','-o','/dev/null','-w','%{http_code}','https://example.com')
    data['journal']=run('journalctl','-b','-u','ethermobile-data','--no-pager','-o','cat')['stdout']
print(json.dumps(data))
'''


def main():
    before = json.loads((ROOT / 'evidence/ethermobile-data-start-install-2026-10-29.json').read_text())
    deadline = time.monotonic() + 240
    while True:
        result = subprocess.run(SSH + ['python3 -c ' + shlex.quote(REMOTE)], capture_output=True, timeout=100)
        if result.returncode == 0:
            data = json.loads(result.stdout)
            if (data['boot'] != before['boot'] and data['connected']) or time.monotonic() >= deadline:
                break
        elif time.monotonic() >= deadline:
            raise RuntimeError(result.stderr.decode(errors='replace'))
        time.sleep(5)
    checks = {
        'new_boot': data['boot'] != before['boot'],
        'enabled': data['enabled'] == 'enabled',
        'connected': data['connected'],
        'services_active': all(v == 'active' for v in data['services'].values()),
        'ip_ping': data.get('ip_ping', {}).get('exit') == 0,
        'dns_ping': data.get('dns_ping', {}).get('exit') == 0,
        'cellular_https': data.get('https', {}).get('exit') == 0 and data.get('https', {}).get('stdout') == '200',
    }
    data['checks'] = checks
    (ROOT / 'evidence/ethermobile-data-start-reboot-2026-10-29.json').write_text(json.dumps(data, indent=2) + '\n')
    print(json.dumps(data, indent=2))
    assert all(checks.values()), checks


if __name__ == '__main__':
    main()
