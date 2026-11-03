"""Read exact vendor files through debugfs without -w, mounting or journal replay."""
from pathlib import Path
import json
import subprocess
from importlib.machinery import SourceFileLoader

ROOT=Path(__file__).resolve().parent.parent
transport=SourceFileLoader('audit_transport',str(ROOT/'scripts/audit-ethermobile-device.py')).load_module()
REMOTE=r'''
import subprocess,json,hashlib
device='/dev/disk/by-partlabel/vendor_b'
files=['/etc/init/ipa_fws.rc','/etc/init/ipacm.rc','/etc/init/netmgrd.rc','/bin/init.mdm.sh']
result={'source':device,'method':'debugfs read-only (no -w)', 'files':{},'firmware':{}}
for path in files:
    r=subprocess.run(['debugfs','-R','cat '+path,device],capture_output=True,timeout=15)
    result['files'][path]={'text':r.stdout.decode(errors='replace'),'sha256':hashlib.sha256(r.stdout).hexdigest()}
for prefix,parts in [('ipa_fws',['mdt','b00','b01','b02','b03','b04']),('ipa_uc',['mdt','b00','b01','b02'])]:
    for part in parts:
        path='/firmware/'+prefix+'.'+part
        r=subprocess.run(['debugfs','-R','cat '+path,device],capture_output=True,timeout=15)
        result['firmware'][path]={'bytes':len(r.stdout),'sha256':hashlib.sha256(r.stdout).hexdigest()}
print(json.dumps(result,indent=2))
'''
if __name__=='__main__':
    r=subprocess.run(transport.SSH+['python3 -'],input=REMOTE.encode(),capture_output=True,check=True,timeout=180)
    data=json.loads(r.stdout)
    target=ROOT/'evidence/ethermobile-vendor-2026-10-18.json'
    target.write_text(json.dumps(data,indent=2)+'\n',encoding='utf-8')
    print(target)
    print(data['files']['/etc/init/ipa_fws.rc']['text'])
