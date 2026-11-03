"""Prepare the carrier-documented giffgaff APN without activating data.

Source: https://help.giffgaff.com/en/articles/245215-internet-apn-settings-guide
Never displays credentials. No roaming, autoconnect or default-route takeover.
"""
from pathlib import Path
import json
import runpy
import subprocess
ROOT=Path(__file__).resolve().parent.parent
SSH=runpy.run_path(str(ROOT/'scripts/deploy-ethermobile.py'))['SSH']
REMOTE=r"""
import configparser,json,os,pathlib,subprocess,uuid
assert pathlib.Path('/etc/etherpocket/disk-identity').read_text().strip()=='GM1920-548cb338-mobian-sda21'
# Verify operator metadata in memory, never persist the rest of mmcli output.
p=subprocess.run(['mmcli','-i','0','-J'],capture_output=True,text=True,check=True)
sim=json.loads(p.stdout)['sim']['properties']
assert sim['operator-code']=='23410' and sim['operator-name'].lower()=='giffgaff'
target=pathlib.Path('/etc/NetworkManager/system-connections/ethermobile-giffgaff.nmconnection')
assert not target.is_symlink()
before=subprocess.run(['nmcli','-t','-f','UUID,TYPE,DEVICE','connection','show','--active'],capture_output=True,check=True).stdout
created=False
if target.exists():
 assert target.stat().st_mode & 0o777 == 0o600
 config=configparser.ConfigParser();config.read(target)
 assert config['gsm']['apn']=='giffgaff.com'
 assert config['gsm'].getboolean('home-only') and not config['connection'].getboolean('autoconnect')
 assert config['ipv4'].getboolean('never-default') and config['ipv6'].getboolean('never-default')
else:
 profile_uuid=str(uuid.uuid4())
 text='''[connection]
id=EtherMobile · giffgaff
uuid=UUID
type=gsm
autoconnect=false
autoconnect-retries=1
permissions=user:mobian:;

[gsm]
apn=giffgaff.com
auto-config=false
home-only=true
username=gg
password=p
password-flags=0

[ppp]
refuse-eap=true
refuse-chap=true
refuse-mschap=true
refuse-mschapv2=true

[ipv4]
method=auto
never-default=true
route-metric=900

[ipv6]
method=auto
never-default=true
route-metric=900
'''.replace('UUID',profile_uuid)
 fd=os.open(target,os.O_WRONLY|os.O_CREAT|os.O_EXCL|os.O_NOFOLLOW,0o600)
 with os.fdopen(fd,'w') as f:f.write(text)
 created=True
subprocess.run(['nmcli','connection','load',str(target)],capture_output=True,check=True)
after=subprocess.run(['nmcli','-t','-f','UUID,TYPE,DEVICE','connection','show','--active'],capture_output=True,check=True).stdout
print(json.dumps({'source':'https://help.giffgaff.com/en/articles/245215-internet-apn-settings-guide',
 'created':created,'stored_mode':'0600','carrier':'giffgaff','apn':'giffgaff.com','authentication':'PAP',
 'roaming_allowed':False,'autoconnect':False,'default_route':False,'activated':False,
 'active_connections_unchanged':before==after},indent=2))
"""
if __name__=='__main__':
    r=subprocess.run(SSH+['python3 -'],input=REMOTE.encode(),capture_output=True,check=True,timeout=30)
    report=json.loads(r.stdout)
    (ROOT/'evidence/ethermobile-giffgaff-profile-2026-10-18.json').write_text(json.dumps(report,indent=2)+'\n',encoding='utf-8')
    print(json.dumps(report,indent=2))
