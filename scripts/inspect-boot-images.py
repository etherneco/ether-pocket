#!/usr/bin/env python3
"""Inspect RAM test images with official magiskboot, on the build host only."""
from pathlib import Path
import subprocess
import shutil

workspace = Path('/mnt/c/projects.local/mobiam')
tool = Path('/opt/etherpocket/boot-diagnostics/magiskboot')
tool.parent.mkdir(parents=True, exist_ok=True)
shutil.copyfile(workspace / 'sources/boot-diagnostics/magiskboot-x86_64', tool)
tool.chmod(0o755)
images = {
    'reference': workspace / 'recovery/twrp-3.4.0-0-guacamole.img',
    'native-reference': workspace / 'build/native-reference-kernel-test.img',
    'native-raw': workspace / 'build/native-mini-boot-raw.img',
}
for name, image in images.items():
    target = tool.parent / name
    target.mkdir(exist_ok=True)
    run = subprocess.run([str(tool), 'unpack', '-h', str(image)], cwd=target,
                         stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
    (workspace / f'evidence/magiskboot-{name}.txt').write_text(run.stdout)
    print(name, run.returncode, run.stdout)
    if run.returncode:
        raise SystemExit('Boot-image inspection failed')
