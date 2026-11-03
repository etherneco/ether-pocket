"""Read-only post-boot IPA/modem acceptance; stores no SIM identifiers."""
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
def run(*args):
    p=subprocess.run(args,capture_output=True,text=True,timeout=20)
    return p.stdout.strip()
assert pathlib.Path('/etc/etherpocket/disk-identity').read_text().strip()=='GM1920-548cb338-mobian-sda21'
p=subprocess.run(['mmcli','-m','any','-J'],capture_output=True,text=True,timeout=20)
modem=json.loads(p.stdout).get('modem',{}) if p.returncode==0 else {}
generic=modem.get('generic',{})
registration=modem.get('3gpp',{})
services={s:run('systemctl','is-active',s) for s in ['ethermobile-ipa','ModemManager','etherpocket-modem','NetworkManager','ssh','bluetooth','ethermobile-data']}
print(json.dumps({'boot':pathlib.Path('/proc/sys/kernel/random/boot_id').read_text().strip(),
 'services':services,'enabled':run('systemctl','is-enabled','ethermobile-ipa'),
 'interfaces':sorted(p.name for p in pathlib.Path('/sys/class/net').iterdir()),
 'modem_state':generic.get('state'),'unlock_required':generic.get('unlock-required'),
 'registration':registration.get('registration-state'),
 'ipa_journal':run('journalctl','-b','-u','ethermobile-ipa','--no-pager','-o','cat'),
 'ordering':run('systemctl','show','ethermobile-ipa','ModemManager','-p','Id','-p','ExecMainStartTimestampMonotonic','-p','ActiveEnterTimestampMonotonic')
}))
'''


def main():
    before = json.loads((ROOT / 'evidence/ethermobile-ipa-start-install-2026-10-29.json').read_text())
    deadline = time.monotonic() + 240
    while True:
        result = subprocess.run(SSH + ['python3 -c ' + shlex.quote(REMOTE)], capture_output=True, timeout=45)
        if result.returncode == 0:
            data = json.loads(result.stdout)
            ready = (data['boot'] != before['boot'] and data['modem_state'] is not None
                     and data['modem_state'] not in ['unknown', 'initializing', 'failed'])
            if ready or time.monotonic() >= deadline:
                break
        elif time.monotonic() >= deadline:
            raise RuntimeError(result.stderr.decode(errors='replace'))
        time.sleep(5)
    checks = {
        'new_boot': data['boot'] != before['boot'],
        'ipa_enabled': data['enabled'] == 'enabled',
        'ipa_interface': 'rmnet_ipa0' in data['interfaces'],
        'modem_ready': data['modem_state'] not in [None, 'unknown', 'initializing', 'failed'],
        'single_firmware_write': data['ipa_journal'].count('initialization requested once') == 1,
        'services_active': all(data['services'][s] == 'active' for s in data['services'] if s != 'ethermobile-data'),
    }
    data['checks'] = checks
    (ROOT / 'evidence/ethermobile-ipa-start-reboot-2026-10-29.json').write_text(json.dumps(data, indent=2) + '\n')
    print(json.dumps(data, indent=2))
    assert all(checks.values()), checks


if __name__ == '__main__':
    main()
