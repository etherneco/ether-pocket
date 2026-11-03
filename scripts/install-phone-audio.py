"""Install signed modules and audio startup on the native phone."""
from pathlib import Path
import importlib
import io
import tarfile

root = Path(__file__).resolve().parent.parent
remote = importlib.import_module('deploy-ethershell').remote
archive = io.BytesIO()
with tarfile.open(fileobj=archive, mode='w') as tar:
    for module in (root/'build/audio-modules').glob('*.ko'):
        tar.add(module, arcname='lib/modules/4.14.117-perf/extra/audio/'+module.name)
    tar.add(root/'scripts/etherpocket-audio-start.sh', arcname='usr/local/sbin/etherpocket-audio-start')
    tar.add(root/'config/etherpocket-audio.service', arcname='etc/systemd/system/etherpocket-audio.service')
    tar.add(root/'scripts/etherpocket-audio-route.sh', arcname='usr/local/sbin/etherpocket-audio-route')
    for name in ['EtherPocket.conf', 'HiFi.conf']:
        tar.add(root/'config/audio'/name, arcname='usr/share/alsa/ucm2/EtherPocket/'+name)
    for driver in ['sm8150-tavil-sn', 'machine_dlkm']:
        link = tarfile.TarInfo('usr/share/alsa/ucm2/conf.d/'+driver+'/sm8150-tavil-snd-card.conf')
        link.type = tarfile.SYMTYPE
        link.linkname = '../../EtherPocket/EtherPocket.conf'
        tar.addfile(link)
remote('tar xf - -C / && chmod 755 /usr/local/sbin/etherpocket-audio-start && '
       'chmod 755 /usr/local/sbin/etherpocket-audio-route && '
       'chmod 644 /etc/systemd/system/etherpocket-audio.service /usr/share/alsa/ucm2/EtherPocket/* && depmod -a && '
       'systemctl daemon-reload && systemd-analyze verify etherpocket-audio.service && '
       'systemctl enable etherpocket-audio.service', input=archive.getvalue())
remote('if [ ! -s /lib/firmware/tfa98xx.cnt ]; then '
       'mkdir -p /run/etherpocket/audio-vendor && '
       'mount -o ro /dev/disk/by-partlabel/vendor_b /run/etherpocket/audio-vendor && '
       'trap "umount /run/etherpocket/audio-vendor" EXIT; '
       'cp /run/etherpocket/audio-vendor/firmware/tfa98xx.cnt /lib/firmware/tfa98xx.cnt; fi')
