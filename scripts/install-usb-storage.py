"""Install an 8 GiB USB exchange disk on the connected native Mobian phone."""
from pathlib import Path
import subprocess

ROOT = Path(__file__).resolve().parent.parent
SSH = ['ssh', '-i', str(ROOT / 'build/etherpocket_ed25519'),
       '-o', 'UserKnownHostsFile=' + str(ROOT / 'build/mobian-known-hosts'),
       '-o', 'BatchMode=yes', '-o', 'ConnectTimeout=8', 'root@10.77.0.2']


def remote(command, **kwargs):
    return subprocess.run(SSH + [command], check=True, timeout=180, **kwargs)


if __name__ == '__main__':
    remote('test "$(findmnt -n -o SOURCE /)" = /dev/sda21 && '
           'command -v mkfs.vfat && command -v fsck.fat && '
           'mkdir -p /var/lib/etherpocket /media/mobian/ETHERPOCKET && '
           'if [ ! -e /var/lib/etherpocket/usb-storage.img ]; then '
           'fallocate -l 8G /var/lib/etherpocket/usb-storage.img.new && '
           'mkfs.vfat -F 32 -n ETHERPOCKET /var/lib/etherpocket/usb-storage.img.new && '
           'chmod 600 /var/lib/etherpocket/usb-storage.img.new && '
           'mv /var/lib/etherpocket/usb-storage.img.new /var/lib/etherpocket/usb-storage.img; fi')
    for source, target, mode in [
        ('scripts/etherpocket-usb-storage.py', '/usr/local/sbin/etherpocket-usb-storage', '755'),
        ('scripts/etherpocket-usb-home-sync.py', '/usr/local/sbin/etherpocket-usb-home-sync', '755'),
        ('config/etherpocket-usb-storage.service', '/etc/systemd/system/etherpocket-usb-storage.service', '644'),
        ('config/etherpocket-usb-files.desktop', '/usr/share/applications/etherpocket-usb-files.desktop', '644'),
    ]:
        remote('cat > ' + target + ' && chmod ' + mode + ' ' + target,
               input=(ROOT / source).read_bytes())
    remote('mkdir -p /home/mobian/Desktop && '
           'install -o mobian -g mobian -m755 /usr/share/applications/etherpocket-usb-files.desktop '
           '/home/mobian/Desktop/etherpocket-usb-files.desktop')
    remote('mkdir -p /etc/etherpocket && touch /etc/etherpocket/usb-home-sync; '
           'test -e /home/mobian/USB || ln -s /media/mobian/ETHERPOCKET /home/mobian/USB; '
           'systemctl daemon-reload && systemctl enable etherpocket-usb-storage.service && '
           'systemd-run --unit=etherpocket-usb-storage-start --on-active=3 '
           '/bin/systemctl restart etherpocket-usb-storage.service')
