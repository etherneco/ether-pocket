"""Associate the verified real downstream IPA netdev with the existing QRTR modem.

Reloads udev rules and triggers ONLY rmnet_ipa0. No daemon/radio/subsystem reset.
"""
from pathlib import Path
import json
import runpy
import shlex
import subprocess
ROOT=Path(__file__).resolve().parent.parent
SSH=runpy.run_path(str(ROOT/'scripts/deploy-ethermobile.py'))['SSH']
if __name__=='__main__':
    rule=(ROOT/'config/78-mm-ethermobile-gm1920.rules').read_text()
    source='''import json,pathlib,subprocess
assert pathlib.Path('/etc/etherpocket/disk-identity').read_text().strip()=='GM1920-548cb338-mobian-sda21'
assert pathlib.Path('/sys/class/net/rmnet_ipa0/type').read_text().strip()=='519'
assert pathlib.Path('/sys/bus/platform/drivers/rmnet_ipa3/soc:qcom,rmnet-ipa').exists()
target=pathlib.Path('/etc/udev/rules.d/78-mm-ethermobile-gm1920.rules')
rule=RULE
assert not target.is_symlink()
if target.exists():assert target.read_text()==rule
else:target.write_text(rule);target.chmod(0o644)
subprocess.run(['udevadm','control','--reload-rules'],check=True)
subprocess.run(['udevadm','trigger','--action=change','/sys/class/net/rmnet_ipa0'],check=True)
subprocess.run(['udevadm','settle','--timeout=10'],check=True)
p=subprocess.run(['udevadm','info','/sys/class/net/rmnet_ipa0'],capture_output=True,text=True,check=True)
print(json.dumps({'rule':str(target),'properties':p.stdout},indent=2))
'''.replace('RULE',repr(rule))
    r=subprocess.run(SSH+['python3 -c '+shlex.quote(source)],capture_output=True,check=True,timeout=30)
    report=json.loads(r.stdout)
    (ROOT/'evidence/ethermobile-ipa-port-2026-10-18.json').write_text(json.dumps(report,indent=2)+'\n',encoding='utf-8')
    print(report['properties'])
