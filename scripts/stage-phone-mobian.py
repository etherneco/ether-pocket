"""Stream the verified Mobian archive to native phone RAM over pinned SSH."""
from pathlib import Path
import hashlib
import subprocess

w = Path(__file__).resolve().parent.parent
archive = w / 'build/mobian-arm64-xfce-rootfs.tar.xz'
expected = '9788204e6b34ccb27f756b7630b3f189595f1d58b3825b999dfffd7d3f1f59c8'
with archive.open('rb') as stream:
    actual = hashlib.file_digest(stream, 'sha256').hexdigest()
if actual != expected:
    raise SystemExit('Mobian archive digest mismatch')
ssh = ['ssh', '-i', str(w / 'build/etherpocket_ed25519'),
       '-o', 'UserKnownHostsFile=' + str(w / 'build/mini-known-hosts'),
       '-o', 'BatchMode=yes', '-o', 'ConnectTimeout=8', 'root@10.77.0.2']

def run(command, **kwargs):
    return subprocess.run(ssh + [command], check=True, **kwargs)

run("grep -q 'etherpocket.ramboot=1' /proc/cmdline && "
    "test $(readlink /proc/1/exe) = /usr/bin/busybox && "
    "test $(stat -f -c %T /run) = tmpfs && "
    "mount -t tmpfs -o size=4G tmpfs /newroot")
print('Transferring verified Mobian archive to phone RAM...', flush=True)
with archive.open('rb') as stream:
    run('cat > /run/mobian-rootfs.tar.xz', stdin=stream)
print('Verifying and extracting archive in phone RAM...', flush=True)
run("test $(sha256sum /run/mobian-rootfs.tar.xz | cut -d ' ' -f1) = " + expected +
    " && tar -xJf /run/mobian-rootfs.tar.xz -C /newroot && test -x /newroot/init")
with (w / 'scripts/etherpocket-usb-debug.sh').open('rb') as stream:
    run('cat > /newroot/usr/local/sbin/etherpocket-usb-debug && '
        'chmod 755 /newroot/usr/local/sbin/etherpocket-usb-debug', stdin=stream)
run('chroot /newroot /usr/bin/ssh-keygen -A')
public = run('cat /newroot/etc/ssh/ssh_host_ed25519_key.pub', capture_output=True, text=True).stdout
parts = public.split()
if len(parts) < 2 or parts[0] != 'ssh-ed25519':
    raise SystemExit('Unexpected Mobian SSH host key')
(w / 'build/mobian-known-hosts').write_text('10.77.0.2 ' + ' '.join(parts[:2]) + '\n')
run('test $(stat -f -c %T /newroot) = tmpfs && '
    'test $(readlink /newroot/etc/systemd/system/systemd-repart.service) = /dev/null && '
    'test $(readlink /newroot/etc/systemd/system/systemd-growfs-root.service) = /dev/null && '
    'mkdir -p /newroot/etc/etherpocket && touch /newroot/etc/etherpocket/rootfs-ready')
print('Mobian rootfs ready in RAM; SSH host key pinned. PID 1 not switched yet.', flush=True)
