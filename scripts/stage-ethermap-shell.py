"""Reuse the isolated Location-page staging workflow for EtherMAP integration."""
from pathlib import Path
template=Path(__file__).with_name('stage-etherlocation-shell.py')
source=template.read_text(encoding='utf-8')
for old,new in [
 ('build/ethershell-location_2.1.0_arm64.deb','build/ethershell-map_2.1.0_arm64.deb'),
 ('/opt/ethershell2/2.1.0-location-','/opt/ethershell2/2.1.0-map-'),
 ('/var/tmp/etherlocation-shell-qa-','/var/tmp/ethermap-shell-qa-'),
 ('evidence/etherlocation-settings-device','evidence/ethermap-settings-device'),
 ('evidence/etherlocation-shell-stage.json','evidence/ethermap-shell-stage.json')]:
    assert old in source,old
    source=source.replace(old,new)
if __name__=='__main__':exec(compile(source,str(template),'exec'),{'__name__':'__main__','__file__':str(template)})
