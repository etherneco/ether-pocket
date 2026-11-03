#!/usr/bin/python3
"""Prepare downstream Qualcomm services without mounting Android at boot."""
from pathlib import Path

root = Path('/run/etherpocket/remoteproc/modem')
root.mkdir(parents=True, exist_ok=True)
(root / 'firmware').write_text('modem.mdt')
for device in Path('/sys/class/uio').glob('uio*'):
    if (device / 'name').read_text().strip() == 'rmtfs':
        link = Path('/dev/qcom_rmtfs_uio1')
        if not link.exists():
            link.symlink_to('/dev/' + device.name)
        break
else:
    raise RuntimeError('Qualcomm remote storage shared memory is missing')
for device in Path('/sys/bus/msm_subsys/devices').glob('subsys*'):
    if (device / 'name').read_text().strip() == 'modem':
        (device / 'restart_level').write_text('RELATED')
        break
