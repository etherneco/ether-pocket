"""Activate the accepted EtherMAP shell stage with the existing automatic rollback."""
from pathlib import Path
template=Path(__file__).with_name('activate-etherlocation-shell.py')
source=template.read_text(encoding='utf-8')
for old,new in [
 ('evidence/etherlocation-shell-stage.json','evidence/ethermap-shell-stage.json'),
 ('build/ethershell-location_2.1.0_arm64.deb','build/ethershell-map_2.1.0_arm64.deb'),
 ('evidence/etherlocation-settings-device/acceptance.json','evidence/ethermap-settings-device/acceptance.json'),
 ('/var/tmp/etherlocation-shell-launch.log','/var/tmp/ethermap-shell-launch.log'),
 ('evidence/etherlocation-shell-deployment.json','evidence/ethermap-shell-deployment.json')]:
    assert old in source,old
    source=source.replace(old,new)
if __name__=='__main__':exec(compile(source,str(template),'exec'),{'__name__':'__main__','__file__':str(template)})
