"""Explicitly authorized reboot acceptance; snapshots never contain credentials.

snapshot saves hashes of persistent GSM keyfiles, selected Core preferences,
the launcher, binary and IPA firmware. reboot is deliberately a separate action.
"""
from pathlib import Path
import argparse
import hashlib
import io
import json
import runpy
import shlex
import subprocess
import tarfile

ROOT=Path(__file__).resolve().parent.parent
SSH=runpy.run_path(str(ROOT/'scripts/deploy-ethermobile.py'))['SSH']
SOURCE=r'''import hashlib,json,pathlib,subprocess
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
assert pathlib.Path('/etc/etherpocket/disk-identity').read_text().strip()=='GM1920-548cb338-mobian-sda21'
launcher=pathlib.Path('/home/mobian/.local/bin/ethershell2-start')
profiles={p.name:sha(p) for p in pathlib.Path('/etc/NetworkManager/system-connections').iterdir() if p.is_file() and b'type=gsm' in p.read_bytes().splitlines()}
prefs=pathlib.Path('/home/mobian/.config/ethershell/preferences.json')
values=json.loads(prefs.read_text()) if prefs.exists() else {}
mobile={k:v for k,v in values.items() if k.startswith('mobile')}
stage=pathlib.Path(STAGE)
firmware={name:sha(pathlib.Path('/lib/firmware')/name) for name in FIRMWARE}
services={s:subprocess.run(['systemctl','is-active',s],capture_output=True,text=True).stdout.strip() for s in ['NetworkManager','ModemManager','ssh','bluetooth','etherpocket-modem']}
print(json.dumps({'boot_id':pathlib.Path('/proc/sys/kernel/random/boot_id').read_text().strip(),
 'gsm_keyfile_hashes':profiles,'mobile_preferences_hash':hashlib.sha256(json.dumps(mobile,sort_keys=True).encode()).hexdigest(),
 'launcher_sha256':sha(launcher),'binary_sha256':sha(stage/'usr/bin/ethershell'),'firmware_hashes':firmware,
 'services':services,'ipa_marker':pathlib.Path('/run/ethermobile-ipa-attempted').exists(),
 'interfaces':sorted(p.name for p in pathlib.Path('/sys/class/net').iterdir()),
 'shell_pids':subprocess.run(['pgrep','-u','1000','-x','ethershell'],capture_output=True,text=True).stdout.split()},indent=2))
'''

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action',choices=['before','reboot','after','ui'])
    args=parser.parse_args()
    if args.action=='reboot':
        assert (ROOT/'evidence/mobile-settings-reboot-before.json').exists()
        result=subprocess.run(SSH+['systemctl reboot'],capture_output=True,timeout=20)
        print('Reboot request exit:',result.returncode)
        if result.returncode not in [0,255]:raise RuntimeError(result.stderr.decode(errors='replace'))
        return
    stage=json.loads((ROOT/'evidence/mobile-settings-deployment.json').read_text())['stage']
    if args.action=='ui':
        source=r'''import os,pathlib,subprocess,sys,tarfile,tempfile
with tempfile.TemporaryDirectory(prefix='mobile-reboot-ui-',dir='/var/tmp') as folder:
 root=pathlib.Path(folder);os.chown(root,1000,1000);output=root/'portrait'
 p=subprocess.run(['runuser','-u','mobian','--','env','ETHERMOBILE_EXPECT_REAL_SIM=1','python3',STAGE+'/mobile-ui-test.py','--binary',STAGE+'/usr/bin/ethershell','--output',str(output)],capture_output=True,timeout=110)
 if p.returncode:sys.stderr.buffer.write(p.stdout+p.stderr);raise SystemExit(p.returncode)
 with tarfile.open(fileobj=sys.stdout.buffer,mode='w|gz') as archive:archive.add(output,arcname='portrait')
'''.replace('STAGE',repr(stage))
        result=subprocess.run(SSH+['python3 -c '+shlex.quote(source)],capture_output=True,timeout=130)
        if result.returncode:raise RuntimeError(result.stderr.decode(errors='replace'))
        output=ROOT/'evidence/mobile-settings-reboot-ui';output.mkdir(exist_ok=True)
        with tarfile.open(fileobj=io.BytesIO(result.stdout),mode='r:gz') as archive:archive.extractall(output,filter='data')
        checks=json.loads((output/'portrait/results.json').read_text());assert all(checks.values())
        print('Post-reboot real SIM/profile/UI checks passed:',len(checks));return
    manifest=json.loads((ROOT/'evidence/ethermobile-vendor-2026-10-18.json').read_text())['firmware']
    source=SOURCE.replace('STAGE',repr(stage)).replace('FIRMWARE',repr([Path(p).name for p in manifest]))
    result=subprocess.run(SSH+['python3 -c '+shlex.quote(source)],capture_output=True,timeout=40)
    if result.returncode:raise RuntimeError(result.stderr.decode(errors='replace'))
    data=json.loads(result.stdout)
    target=ROOT/('evidence/mobile-settings-reboot-'+args.action+'.json')
    target.write_text(json.dumps(data,indent=2)+'\n')
    if args.action=='after':
        before=json.loads((ROOT/'evidence/mobile-settings-reboot-before.json').read_text())
        checks={k:before[k]==data[k] for k in ['gsm_keyfile_hashes','mobile_preferences_hash','launcher_sha256','binary_sha256','firmware_hashes']}
        checks['new_boot']=before['boot_id']!=data['boot_id']
        (ROOT/'evidence/mobile-settings-reboot-comparison.json').write_text(json.dumps(checks,indent=2)+'\n')
        print(json.dumps(checks,indent=2));assert all(checks.values())
    else:print('Persistent GSM profiles:',len(data['gsm_keyfile_hashes']));print('Baseline saved:',target)

if __name__=='__main__':main()
