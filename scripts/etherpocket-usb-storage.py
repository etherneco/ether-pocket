#!/usr/bin/python3
"""Exclusive FAT32 ownership: USB host while connected, Mobian after eject."""
import logging
import os
from pathlib import Path
import subprocess
import time

GADGET = Path('/sys/kernel/config/usb_gadget/etherpocket')
IMAGE = Path('/var/lib/etherpocket/usb-storage.img')
MOUNT = Path('/media/mobian/ETHERPOCKET')
FUNCTION = GADGET / 'functions/mass_storage.usb0'
LUN = FUNCTION / 'lun.0'
HOME_SYNC_ENABLED = Path('/etc/etherpocket/usb-home-sync')


def synchronize_home():
    if HOME_SYNC_ENABLED.exists():
        result = run('runuser', '-u', 'mobian', '--', '/usr/local/sbin/etherpocket-usb-home-sync')
        logging.info('%s', result.stderr.strip())


def write(path, value):
    path.write_text(str(value) + '\n')


def run(*args):
    return subprocess.run(args, check=True, capture_output=True, text=True)


def backing():
    return (LUN / 'file').read_text().strip()


def mount_local():
    if backing():
        raise RuntimeError('USB still owns the image')
    if not os.path.ismount(MOUNT):
        # Never repair a host-mounted filesystem. Only called after release/eject.
        check = subprocess.run(['fsck.fat', '-a', str(IMAGE)], capture_output=True, text=True)
        if check.returncode not in (0, 1):
            raise RuntimeError('FAT check failed: ' + check.stdout + check.stderr)
        run('mount', '-t', 'vfat', '-o', 'loop,uid=1000,gid=1000,umask=0022,utf8', str(IMAGE), str(MOUNT))
        logging.info('Files available on Mobian: %s', MOUNT)
    synchronize_home()


def export_usb():
    if HOME_SYNC_ENABLED.exists() and not backing():
        if os.path.ismount(MOUNT):
            synchronize_home()
        else:
            mount_local()
    if os.path.ismount(MOUNT):
        # No lazy/forced unmount: an open file must block the handover.
        run('umount', str(MOUNT))
    if not backing():
        write(LUN / 'file', IMAGE)
        logging.info('Files exported over USB')


def configure():
    if not IMAGE.is_file():
        raise RuntimeError('Missing USB storage image; run the installer first')
    for _ in range(90):
        if (GADGET / 'UDC').exists() and (GADGET / 'UDC').read_text().strip():
            break
        time.sleep(1)
    else:
        raise RuntimeError('USB debug gadget is not bound')
    FUNCTION.mkdir(exist_ok=True)
    link = GADGET / 'configs/c.1/mass_storage.usb0'
    if link.is_symlink():
        return
    udc = (GADGET / 'UDC').read_text().strip()
    write(GADGET / 'UDC', '')
    try:
        # OnePlus defaults this function to its virtual driver CD-ROM.
        write(LUN / 'cdrom', 0)
        write(LUN / 'removable', 1)
        write(LUN / 'ro', 0)
        write(LUN / 'nofua', 0)
        write(LUN / 'inquiry_string', 'EtherPktUSB Storage     0100')
        if not os.path.ismount(MOUNT) and not HOME_SYNC_ENABLED.exists():
            write(LUN / 'file', IMAGE)
        # New PID prevents Windows reusing the previous RNDIS-only descriptor.
        write(GADGET / 'idProduct', '0x0105')
        write(GADGET / 'strings/0x409/product', 'EtherPocket USB Storage')
        link.symlink_to(FUNCTION)
    except Exception:
        if link.is_symlink():
            link.unlink()
        write(GADGET / 'idProduct', '0x0104')
        raise
    finally:
        write(GADGET / 'UDC', udc)


def main():
    import fcntl

    logging.basicConfig(level=logging.INFO, format='%(levelname)s %(message)s')
    lock = open('/run/etherpocket-usb-storage.lock', 'w')
    fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
    MOUNT.mkdir(parents=True, exist_ok=True)
    configure()
    udc = (GADGET / 'UDC').read_text().strip()
    state = Path('/sys/class/udc') / udc / 'state'
    disconnected_at = None
    was_disconnected = False
    exported = bool(backing())
    while True:
        try:
            disconnected = state.read_text().strip() == 'not attached'
            if disconnected:
                if disconnected_at is None:
                    disconnected_at = time.monotonic()
                if time.monotonic() - disconnected_at >= 3:
                    if backing():
                        write(LUN / 'file', '')
                    if not was_disconnected or not os.path.ismount(MOUNT):
                        mount_local()
                    was_disconnected = True
                    exported = False
            else:
                disconnected_at = None
                if was_disconnected or (not exported and not os.path.ismount(MOUNT)):
                    export_usb()
                    was_disconnected = False
                    exported = True
                elif exported and not backing():
                    # SCSI eject releases the LUN. Keep it local until reconnect.
                    mount_local()
                    exported = False
        except Exception:
            logging.exception('Storage handover failed; will retry without forcing ownership')
        time.sleep(1)


if __name__ == '__main__':
    main()
