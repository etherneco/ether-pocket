#!/usr/bin/env python3
"""Read boot metadata from the GM1920 while a temporary root recovery is active.

No writes to phone block devices, slot changes, rooting or flashing.
"""
import hashlib
import json
from pathlib import Path
import subprocess

SERIAL = '548cb338'
ADB = [r'C:\Users\ether\AppData\Local\Android\Sdk\platform-tools\adb.exe', '-s', SERIAL]
out = Path('recovery/stock-backup')
out.mkdir(parents=True, exist_ok=True)
devices = subprocess.check_output([ADB[0], 'devices'], text=True, timeout=10)
if SERIAL + '\trecovery' not in devices:
    raise SystemExit('Expected the connected phone in recovery mode.')
identity = subprocess.check_output(ADB + ['shell', 'id'], text=True, timeout=10)
model = subprocess.check_output(ADB + ['shell', 'getprop', 'ro.product.model'], text=True, timeout=10).strip()
if 'uid=0(root)' not in identity or model != 'GM1920':
    raise SystemExit('Backup requires root recovery on GM1920.')
sizes = {'boot_a': 0x6000000, 'boot_b': 0x6000000,
         'dtbo_a': 0x1800000, 'dtbo_b': 0x1800000,
         'vbmeta_a': 0x10000, 'vbmeta_b': 0x10000}
manifest = {'serial': SERIAL, 'model': model, 'method': 'read-only adb exec-out from temporary TWRP', 'partitions': {}}
for partition, expected_size in sizes.items():
    block = '/dev/block/by-name/' + partition
    path = out / (partition + '.img')
    if path.exists():
        raise SystemExit(f'Refusing to overwrite {path}')
    partial = path.with_suffix('.partial')
    with partial.open('wb') as stream:
        result = subprocess.run(ADB + ['exec-out', 'cat', block], stdout=stream,
                                stderr=subprocess.PIPE, timeout=90)
    if result.returncode or partial.stat().st_size != expected_size:
        raise SystemExit(f'Backup failed for {partition}: {result.stderr.decode(errors="replace")}')
    host_hash = hashlib.sha256(partial.read_bytes()).hexdigest()
    remote_hash = subprocess.check_output(ADB + ['shell', 'sha256sum', block], text=True, timeout=60).split()[0]
    if host_hash != remote_hash:
        raise SystemExit(f'Phone/host hash mismatch for {partition}')
    partial.rename(path)
    manifest['partitions'][partition] = {'size': expected_size, 'sha256': host_hash, 'file': str(path)}
    (out / 'manifest.json').write_text(json.dumps(manifest, indent=2) + '\n')
    print(f'{partition}: {expected_size} bytes, phone/host SHA256 verified', flush=True)
