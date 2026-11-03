from pathlib import Path
import difflib
root = Path('/opt/etherpocket/kernel')
patch = []
for name in ['arch/arm64/kernel/cpu-reset.h','arch/arm64/kernel/machine_kexec.c']:
    path = root/name
    before = path.read_text()
    if 'etherpocket_cpu_soft_restart(' in before:
        continue
    # The vendor's proc-fns.h retains a separate two-argument restart ABI.
    # Rename only the static upstream kexec wrapper, preserving that ABI.
    old = 'static inline void __noreturn cpu_soft_restart(' if name.endswith('.h') else '\tcpu_soft_restart(kimage'
    new = old.replace('cpu_soft_restart','etherpocket_cpu_soft_restart')
    assert before.count(old) == 1
    after = before.replace(old,new)
    path.write_text(after)
    patch.extend(difflib.unified_diff(before.splitlines(True),after.splitlines(True),fromfile='a/'+name,tofile='b/'+name))
if patch:
    Path('/mnt/c/projects.local/mobiam/kernel/patches/0007-kexec-wrapper-name.patch').write_text(''.join(patch))
