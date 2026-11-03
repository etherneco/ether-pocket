"""Capture native DRM scanout bytes through SSH without a text pipeline."""
from pathlib import Path
import subprocess
from PIL import Image
w = Path(__file__).resolve().parent.parent
ssh = ['ssh', '-i', str(w / 'build/etherpocket_ed25519'),
       '-o', 'UserKnownHostsFile=' + str(w / 'build/mobian-known-hosts'),
       '-o', 'BatchMode=yes', '-o', 'ConnectTimeout=8', 'root@10.77.0.2']
ppm = w / 'evidence/native-scanout.ppm'
with ppm.open('wb') as out:
    subprocess.run(ssh + ['/run/capture-drm-buffer'], stdout=out, check=True)
with Image.open(ppm) as image:
    image.save(w / 'evidence/native-scanout.png')
    print('Captured scanout', image.size, image.getbbox())
