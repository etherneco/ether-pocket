"""Test capture descriptors using synthetic commands on a private bus; no real PCM."""
from pathlib import Path
import runpy,subprocess
ROOT=Path(__file__).resolve().parent.parent
SSH=runpy.run_path(str(ROOT/'scripts/deploy-ethermobile.py'))['SSH']
if __name__=='__main__':
    p=subprocess.run(SSH+['runuser -u mobian -- env XDG_RUNTIME_DIR=/run/user/1000 dbus-run-session -- python3 /usr/share/etheraudio/tests/service_fixture.py'],capture_output=True,text=True,timeout=55)
    (ROOT/'evidence/etheraudio-protocol-tests.txt').write_text(p.stdout+p.stderr,encoding='utf-8')
    print(p.stdout+p.stderr)
    assert p.returncode==0, 'Private protocol runner exited with code '+str(p.returncode)
