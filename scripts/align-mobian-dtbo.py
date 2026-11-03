"""Use the verified Android-10 board overlays for Mobian's slot A only."""
import argparse
import hashlib
from pathlib import Path
import struct
import subprocess

root = Path(__file__).resolve().parent.parent
p = argparse.ArgumentParser(description=__doc__)
p.add_argument('--apply-mobian-slot-a',action='store_true')
args = p.parse_args()
images = {s:(root/('recovery/stock-backup/dtbo_'+s+'.img')).read_bytes() for s in 'ab'}
expected = {'a':'e157f7ab02980616ba83e888eeca0891a19aa90a10b5558a69c08f9774e8ec64',
            'b':'6c319d579555e5f09de443db832c1659a0ee0763c59f64ebbca2ed11a3f921ef'}
for slot, data in images.items():
    assert hashlib.sha256(data).hexdigest() == expected[slot]
    fields = struct.unpack_from('>8I',data)
    assert fields[0] == 0xd7b7ab1e and fields[2:4] == (32,32)
    print('Stock slot',slot,':',fields[4],'DTBO entries')
assert struct.unpack_from('>I',images['a'],16)[0] == 21
assert struct.unpack_from('>I',images['b'],16)[0] == 38
print('The working GM1920 board uses DTBO index 35, absent from original slot A.')
if not args.apply_mobian_slot_a:
    raise SystemExit('Inspection only; no phone writes.')
fb = [str(Path.home()/'AppData/Local/Android/Sdk/platform-tools/fastboot.exe'),'-s','548cb338']
subprocess.run(fb+['flash','dtbo_a',str(root/'recovery/stock-backup/dtbo_b.img')],check=True,timeout=45)
subprocess.run(fb+['--set-active=a'],check=True,timeout=10)
subprocess.run(fb+['reboot'],check=True,timeout=10)
