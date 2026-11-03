"""Ensure this logo update changes only the two rendered menu framebuffers."""
from pathlib import Path
import gzip
import json
import struct
from PIL import Image

root = Path(__file__).resolve().parent.parent
def unpack(path):
    data = path.read_bytes()
    ks, _, rs, _, ss, _, _, page, version, _ = struct.unpack_from('<10I', data, 8)
    assert data[:8] == b'ANDROID!' and version == 2
    rd = page + ((ks + page - 1)//page)*page
    raw = gzip.decompress(data[rd:rd+rs])
    files, offset = {}, 0
    while True:
        assert raw[offset:offset+6] == b'070701'
        fields = [int(raw[offset+6+i*8:offset+14+i*8],16) for i in range(13)]
        size, namesize = fields[6], fields[11]
        name = raw[offset+110:offset+110+namesize-1].decode().removeprefix('./')
        start = (offset+110+namesize+3)&~3
        if name == 'TRAILER!!!':
            break
        files[name] = raw[start:start+size]
        offset = (start+size+3)&~3
    dtb_size = struct.unpack_from('<I',data,1648)[0]
    dtb_offset = rd + ((rs+page-1)//page)*page + ((ss+page-1)//page)*page
    return data[page:page+ks], data[dtb_offset:dtb_offset+dtb_size], files

report = {}
expected = {'usr/share/etherpocket/bootmenu/option-0.xrgb',
            'usr/share/etherpocket/bootmenu/option-1.xrgb'}
for name in ['native-bootmenu-test.img','stock-menu-test.img']:
    old = unpack(root/'recovery/bootmenu-before-header-logo'/name)
    new = unpack(root/'build'/name)
    assert old[:2] == new[:2], 'Kernel/DTB changed: '+name
    assert old[2].keys() == new[2].keys(), 'Ramdisk file list changed: '+name
    changed = {key for key in old[2] if old[2][key] != new[2][key]}
    assert changed == expected, (name,changed)
    report[name] = dict(kernel_unchanged=True,dtb_unchanged=True,changed_files=sorted(changed))

logo = Image.open(root/'assets/etherneco-logo-header.png').convert('RGBA')
manifest = json.loads((root/'build/bootmenu/manifest.json').read_text())
base = Image.new('RGBA',logo.size,'black')
base.alpha_composite(logo)
for selected in range(2):
    screen = Image.open(root/f'build/bootmenu/option-{selected}.png')
    x,y = manifest['logo_position']
    assert screen.crop((x,y,x+logo.width,y+logo.height)).tobytes() == base.convert('RGB').tobytes()
    assert (root/f'build/bootmenu/option-{selected}.xrgb').stat().st_size == 1440*3120*4
(root/'evidence/bootmenu-header-logo-payload-check.json').write_text(json.dumps(report,indent=2)+'\n')
print('Kernels, DTBs and boot logic unchanged; only menu framebuffers changed. PNG alpha verified.')
