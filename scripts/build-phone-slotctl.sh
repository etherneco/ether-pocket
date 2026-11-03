#!/bin/bash
set -euo pipefail
workspace=/mnt/c/projects.local/mobiam
src=/opt/etherpocket/qbootctl-menu
mkdir -p "$src"
cp -a /opt/etherpocket/qbootctl/qbootctl-0.2.2/. "$src/"
python3 - "$src" <<'PY'
from pathlib import Path
import sys
p = Path(sys.argv[1])/'bootctrl_impl.c'
s = p.read_text()
# The OEM Fastboot keeps firmware type GUID identities unchanged on this board.
# Boot-image identities alone need canonicalization (the verified host selector).
s = s.replace('memcpy(pentry, guid, TYPE_GUID_SIZE);', 'if (!strcmp(slotA, "boot_a")) memcpy(pentry, guid, TYPE_GUID_SIZE);')
anchor = '\t\tint a_state = slot == 0 ? SLOT_ACTIVE : SLOT_INACTIVE;'
assert s.count(anchor) == 1
s = s.replace(anchor, '''\t\tif (!strcmp(slotA, "boot_a")) {
            const unsigned char boot_guid[16] = {0x86,0x7f,0x11,0x20,0x85,0xe9,0x57,0x43,0xb9,0xee,0x37,0x4b,0xc1,0xd8,0x48,0x7d};
            const unsigned char unused_guid[16] = {0xd4,0x6c,0x03,0x77,0xd5,0x03,0xbb,0x42,0x8e,0xd1,0x37,0xe5,0xa8,0x8b,0xaa,0x34};
            memcpy(active_guid, boot_guid, 16);
            memcpy(inactive_guid, unused_guid, 16);
        }
'''+anchor)
s = s.replace('for (i = 0, slotA = g_all_ptns[0]; i < ARRAY_SIZE(g_all_ptns); slotA = g_all_ptns[++i]) {',
              'for (i = 0; (unsigned)i < ARRAY_SIZE(g_all_ptns); i++) { slotA = g_all_ptns[i];')
for entry, state in [('pentryA', 'a_state'), ('pentryA_bak', 'a_state'), ('pentryB', 'b_state'), ('pentryB_bak', 'b_state')]:
    # Preserve the active/inactive type identities in BOTH switch directions.
    import re
    pattern = r'UPDATE_SLOT\('+entry+r', (?:active_guid|inactive_guid), '+state+r'\);'
    s, count = re.subn(pattern, 'UPDATE_SLOT('+entry+', '+state+' == SLOT_ACTIVE ? active_guid : inactive_guid, '+state+');', s)
    assert count == 1
p.write_text(s)
header = Path(sys.argv[1])/'gpt-utils.h'
text = header.read_text()
text = text.replace('#define AB_SLOT_ACTIVE_VAL\t\t  0xF', '#define AB_SLOT_ACTIVE_VAL\t\t  0x3F')
header.write_text(text)
PY
aarch64-linux-gnu-gcc-12 -O2 -static -Wall -Wextra -I "$src" \
 "$src/qbootctl.c" "$src/bootctrl_impl.c" "$src/gpt-utils.c" "$src/crc32.c" \
 "$workspace/scripts/ufs-boot-lun.c" -o "$workspace/build/etherpocket-slotctl"
aarch64-linux-gnu-gcc-12 -O2 -static -Wall -Wextra -DUFS_QUERY_MAIN \
 "$workspace/scripts/ufs-boot-lun.c" -o "$workspace/build/ufs-boot-query"
