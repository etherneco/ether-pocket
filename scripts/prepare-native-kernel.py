#!/usr/bin/env python3
"""Rebuild the RAM-boot adaptation from pristine files in the pinned source.

Run in the task's WSL build host. Stock phone partitions are never accessed.
The vendor's omitted panic_flush code is replaced by standard SysRq sync;
this candidate is exclusively for RAM tests without mounting stock volumes.
"""
import difflib
from pathlib import Path
import tarfile

workspace = Path('/mnt/c/projects.local/mobiam')
kernel = Path('/opt/etherpocket/kernel')
files = ('kernel/Makefile', 'kernel/panic.c', 'init/initramfs.c', 'drivers/tty/sysrq.c')
with tarfile.open(workspace / 'sources/oneplus-sdx50m-31bebb6.tar.gz') as archive:
    prefix = archive.getmembers()[0].name.split('/')[0]
    original = {name: archive.extractfile(prefix + '/' + name).read().decode() for name in files}
modified = dict(original)


def replace(name, before, after):
    if modified[name].count(before) != 1:
        raise RuntimeError(f'Expected unique source context in {name}')
    modified[name] = modified[name].replace(before, after)


replace('kernel/Makefile', 'obj-y += panic_flush.o',
        '# panic_flush.c was omitted from the public vendor source.\n# RAM-only native tests retain standard panic and SysRq behavior.')
replace('kernel/panic.c', '\t/* [OSP-3675]: ext4 fsync */\n\tif (!get_download_mode())\n\t\tpanic_flush_device_cache(2000);\n', '')
replace('drivers/tty/sysrq.c', '\tpanic_flush_device_cache(0);', '\temergency_sync(); /* Standard sync; omitted vendor implementation unavailable. */')
replace('init/initramfs.c', 'static int __initdata do_skip_initramfs;', '''static int __initdata do_skip_initramfs;
static int __initdata etherpocket_ramboot;

/* Preserve stock skip_initramfs behavior unless a native RAM test opts in. */
static int __init etherpocket_ramboot_param(char *str)
{
    if (str && !strcmp(str, "1"))
        etherpocket_ramboot = 1;
    return 0;
}
early_param("etherpocket.ramboot", etherpocket_ramboot_param);''')
replace('init/initramfs.c', '\tif (*str)\n\t\treturn 0;\n\tdo_skip_initramfs = 1;',
        '\tif (*str)\n\t\treturn 0;\n\tif (etherpocket_ramboot)\n\t\treturn 1;\n\tdo_skip_initramfs = 1;')
patch = []
for name in files:
    patch.extend(difflib.unified_diff(original[name].splitlines(keepends=True),
                                    modified[name].splitlines(keepends=True),
                                    fromfile='a/' + name, tofile='b/' + name))
    (kernel / name).write_text(modified[name])
(workspace / 'kernel/patches/0002-native-ramboot-and-missing-panic-flush.patch').write_text(''.join(patch))
print('Prepared native RAM-only adaptations from the pinned original source.')
