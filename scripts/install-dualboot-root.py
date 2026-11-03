#!/usr/bin/env python3
"""Install verified Mobian on the reviewed new partition, never on Android volumes."""
import hashlib
import argparse
import json
from pathlib import Path
import subprocess
from importlib.machinery import SourceFileLoader

ROOT = Path(__file__).resolve().parent.parent
parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('--install-authorized-partition', action='store_true')
if not parser.parse_args().install_authorized_partition:
    raise SystemExit('Requires --install-authorized-partition; this formats the new Mobian partition.')
audit = SourceFileLoader('gpt_audit', str(ROOT/'scripts/audit-dualboot.py')).load_module()
plan = json.loads((ROOT/'build/dualboot-gpt/plan.json').read_text())
assert plan['applied'] is True and plan['android_data_reset_authorized'] is True
archive = ROOT/'build/mobian-arm64-xfce-rootfs.tar.xz'
expected = '9788204e6b34ccb27f756b7630b3f189595f1d58b3825b999dfffd7d3f1f59c8'
with archive.open('rb') as f:
    assert hashlib.file_digest(f,'sha256').hexdigest() == expected


def run(command, **kwargs):
    return subprocess.run(audit.SSH+[command],check=True,timeout=600,**kwargs)


def upload(local, destination, mode='644'):
    with (ROOT/local).open('rb') as f:
        run('cat > '+destination+' && chmod '+mode+' '+destination,stdin=f)


run("test $(stat -f -c %T /) = tmpfs && "
    "test $(blockdev --getsize64 /dev/sda20) = 34359738368 && "
    "test $(blockdev --getsize64 /dev/sda21) = 208467374080 && "
    "test $(blkid -s PART_ENTRY_UUID -o value -p /dev/sda21) = 6e8c4f39-c819-4b95-a7ea-548cb3380021 && "
    "test $(sha256sum /dev/sde39 | cut -d ' ' -f1) = 12f5ceb09558339c5d395078f7b0675374b4fd2b7c6d6900d2939badec11440d")
# Save small reset/recovery metadata locally without printing its contents.
backup = ROOT/'recovery/dualboot-audit'
for name, block, size in [('misc-before-reset','/dev/sda3',1048576),
                          ('metadata-before-reset','/dev/sda17',16777216)]:
    target = backup/(name+'.img')
    if target.exists():
        raise SystemExit('Refusing to overwrite '+str(target))
    with target.open('wb') as f:
        run('cat '+block,stdout=f)
    assert target.stat().st_size == size
print('Formatting only the new Mobian partition...',flush=True)
run('! findmnt -rn -S /dev/sda21 && '
    'mkfs.ext4 -F -L etherpocket -m 0 -O ^orphan_file,^metadata_csum_seed /dev/sda21 && '
    'mkdir -p /mnt/mobian && mount -t ext4 /dev/sda21 /mnt/mobian')
print('Transferring root archive to RAM and verifying it...',flush=True)
with archive.open('rb') as f:
    run('cat > /run/dualboot-rootfs.tar.xz',stdin=f)
run('test $(sha256sum /run/dualboot-rootfs.tar.xz | cut -d " " -f1) = '+expected+
    ' && tar --warning=no-timestamp -xJpf /run/dualboot-rootfs.tar.xz -C /mnt/mobian')
print('Configuring persistent native X11, touchscreen and USB SSH...',flush=True)
run('mkdir -p /mnt/mobian/etc/etherpocket /mnt/mobian/etc/libinput '
    '/mnt/mobian/usr/local/lib/xorg/modules/drivers /mnt/mobian/etc/X11/xorg.conf.d '
    '/mnt/mobian/etc/systemd/system/multi-user.target.wants '
    '/mnt/mobian/etc/xdg/autostart /mnt/mobian/usr/local/bin '
    '/mnt/mobian/usr/local/sbin /mnt/mobian/etc/sudoers.d /mnt/mobian/run/sshd '
    '/mnt/mobian/etc/systemd/system/graphical.target.wants; '
    'cp -a /etc/ssh/ssh_host_* /mnt/mobian/etc/ssh/; '
    'rm -f /mnt/mobian/init; '
    'ln -s /sbin/init /mnt/mobian/init')
upload('build/modesetting_drv-panel-test.so','/mnt/mobian/usr/local/lib/xorg/modules/drivers/modesetting_drv.so')
upload('config/gm1920-libinput-local-overrides.quirks','/mnt/mobian/etc/libinput/local-overrides.quirks')
upload('scripts/etherair-x11.py','/mnt/mobian/usr/local/bin/etherair-x11','755')
upload('scripts/etherpocket-usb-debug.sh','/mnt/mobian/usr/local/sbin/etherpocket-usb-debug','755')
upload('build/reboot-bootloader','/mnt/mobian/usr/local/sbin/etherpocket-fastboot','755')
upload('build/xdg-utils_1.2.1-2_all.deb','/run/xdg-utils_1.2.1-2_all.deb')
upload('build/qbootctl_0.2.2-1_arm64.deb','/run/qbootctl.deb')
config = (ROOT/'config/20-gm1920-ram-diagnostic.conf').read_text().replace(
    '1080x2340x60x105300','1440x3120x60x187200').replace(
    '    Option "ShadowFB"','    Option "Atomic" "true"\n    Option "ShadowFB"')
run('cat > /mnt/mobian/etc/X11/xorg.conf.d/20-gm1920-ram-diagnostic.conf',input=config.encode())
configure = r'''
set -eu
printf 'GM1920-548cb338-mobian-sda21\n' > /mnt/mobian/etc/etherpocket/disk-identity
root_uuid=$(blkid -s UUID -o value /dev/sda21)
printf 'UUID=%s / ext4 defaults,noatime 0 1\n' "$root_uuid" > /mnt/mobian/etc/fstab
cat > /mnt/mobian/etc/systemd/system/etherpocket-panel-brightness.service <<'EOF'
[Unit]
Description=GM1920 initial panel brightness
After=lightdm.service
[Service]
Type=oneshot
ExecStart=/bin/sh -c 'sleep 8; echo 0 > /sys/class/backlight/panel0-backlight/bl_power; echo 300 > /sys/class/backlight/panel0-backlight/brightness'
[Install]
WantedBy=graphical.target
EOF
ln -sfn /etc/systemd/system/etherpocket-panel-brightness.service /mnt/mobian/etc/systemd/system/graphical.target.wants/etherpocket-panel-brightness.service
cat > /mnt/mobian/etc/xdg/autostart/etherpocket-mobile.desktop <<'EOF'
[Desktop Entry]
Type=Application
Name=EtherPocket mobile setup
Exec=sh -c "sleep 10; etherair-x11 mobile --dpi 264 --icon-size 72"
OnlyShowIn=XFCE;
EOF
cat > /mnt/mobian/etc/xdg/autostart/etherpocket-onboard.desktop <<'EOF'
[Desktop Entry]
Type=Application
Name=Onboard touch keyboard
Exec=onboard
OnlyShowIn=XFCE;
EOF
mount --bind /dev /mnt/mobian/dev
mount -t proc proc /mnt/mobian/proc
mount -t sysfs sysfs /mnt/mobian/sys
trap 'umount /mnt/mobian/sys /mnt/mobian/proc /mnt/mobian/dev' EXIT
cp /run/xdg-utils_1.2.1-2_all.deb /mnt/mobian/tmp/xdg-utils.deb
cp /run/qbootctl.deb /mnt/mobian/tmp/qbootctl.deb
chroot /mnt/mobian dpkg -i /tmp/xdg-utils.deb
chroot /mnt/mobian dpkg -i /tmp/qbootctl.deb
rm /mnt/mobian/tmp/xdg-utils.deb /mnt/mobian/tmp/qbootctl.deb
chroot /mnt/mobian systemctl enable lightdm.service etherpocket-panel-brightness.service etherpocket-usb-debug.service
chroot /mnt/mobian /usr/sbin/sshd -t
sync
'''
run('sh -s',input=configure.encode())
run('umount /mnt/mobian && e2fsck -fn /dev/sda21')
print('Persistent Mobian installed and filesystem checked. No boot partition flashed yet.',flush=True)
