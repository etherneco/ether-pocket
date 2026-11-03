"""Extract the verified original Android boot payload and capture the board FDT."""
from pathlib import Path
import hashlib
import json
import struct
import subprocess

root=Path(__file__).resolve().parent.parent
image=(root/'recovery/stock-backup/boot_b.img').read_bytes()
assert hashlib.sha256(image).hexdigest() == '12f5ceb09558339c5d395078f7b0675374b4fd2b7c6d6900d2939badec11440d'
kernel_size,_,ramdisk_size,_,_,_,_,page,version,_=struct.unpack_from('<10I',image,8)
assert page==4096 and version==2
out=root/'build/bootmenu'
out.mkdir(parents=True,exist_ok=True)
kernel=image[page:page+kernel_size]
assert kernel[56:60]==b'ARM\x64'
rd_offset=page+((kernel_size+page-1)//page)*page
ramdisk=image[rd_offset:rd_offset+ramdisk_size]
(out/'android-Image').write_bytes(kernel)
(out/'android-initrd.gz').write_bytes(ramdisk)
ssh=['ssh','-i',str(root/'build/etherpocket_ed25519'),'-o',
     'UserKnownHostsFile='+str(root/'build/mobian-known-hosts'),'-o','BatchMode=yes',
     '-o','ConnectTimeout=6','root@10.77.0.2']
with (out/'android-board.dtb').open('wb') as f:
    subprocess.run(ssh+['cat /sys/firmware/fdt'],check=True,stdout=f,timeout=20)
dtb=(out/'android-board.dtb').read_bytes()
assert dtb[:4]==b'\xd0\x0d\xfe\xed'
metadata={name:dict(size=(out/name).stat().st_size,sha256=hashlib.sha256((out/name).read_bytes()).hexdigest())
          for name in ['android-Image','android-initrd.gz','android-board.dtb']}
(out/'android-payload.json').write_text(json.dumps(metadata,indent=2)+'\n')
print(json.dumps(metadata,indent=2))
