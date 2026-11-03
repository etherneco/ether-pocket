"""Deploy the patched Xorg module exclusively into the current RAM-root test."""
from pathlib import Path
import argparse
import subprocess
w = Path(__file__).resolve().parent.parent
p = argparse.ArgumentParser(description=__doc__)
p.add_argument('--panel-test', action='store_true')
a = p.parse_args()
ssh = ['ssh', '-i', str(w / 'build/etherpocket_ed25519'),
       '-o', 'UserKnownHostsFile=' + str(w / 'build/mobian-known-hosts'),
       '-o', 'BatchMode=yes', '-o', 'ConnectTimeout=8', 'root@10.77.0.2']
subprocess.run(ssh + ['test $(stat -f -c %T /) = tmpfs && systemctl stop lightdm && '
                     'mkdir -p /usr/local/lib/xorg/modules/drivers'], check=True)
module = 'modesetting_drv-panel-test.so' if a.panel_test else 'modesetting_drv-fixed.so'
with (w / 'build' / module).open('rb') as binary:
    subprocess.run(ssh + ['cat > /usr/local/lib/xorg/modules/drivers/modesetting_drv.so && '
                         'chmod 644 /usr/local/lib/xorg/modules/drivers/modesetting_drv.so'],
                   stdin=binary, check=True)
config = (w / 'config/20-gm1920-ram-diagnostic.conf').read_text()
if a.panel_test:
    config = config.replace('1080x2340x60x105300', '1440x3120x60x187200')
    config = config.replace('    Option "ShadowFB"', '    Option "Atomic" "true"\n    Option "ShadowFB"')
subprocess.run(ssh + ['cat > /etc/X11/xorg.conf.d/20-gm1920-ram-diagnostic.conf && '
                     'systemctl unmask lightdm && systemctl reset-failed lightdm && systemctl start lightdm'],
               input=config.encode(), check=True)
