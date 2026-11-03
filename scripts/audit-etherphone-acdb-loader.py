"""Inspect the handset's own ACDB loader; never execute or install vendor code."""
import json
import runpy
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
remote = runpy.run_path(str(ROOT/'scripts/check-etherphone-device.py'))['remote']
REMOTE = r'''
import hashlib,json,pathlib,re,subprocess,tempfile,xml.etree.ElementTree as E
assert pathlib.Path('/etc/etherpocket/disk-identity').read_text().strip()=='GM1920-548cb338-mobian-sda21'
def debug(part,op):
 p=subprocess.run(['debugfs','-R',op,'/dev/disk/by-partlabel/'+part],capture_output=True,timeout=10)
 return p.stdout
props=debug('vendor_b','cat /build.prop').decode()
out={'scope':'Read-only partition inspection, temporary ELF extraction; no dlopen/init, ioctl, mixer, service, firmware or partition writes',
 'vendorBuild':{l.split('=',1)[0]:l.split('=',1)[1] for l in props.splitlines() if '=' in l and any(x in l.split('=',1)[0] for x in ['ro.vendor.build.fingerprint','ro.vendor.build.version.sdk','ro.vendor.build.version.release','ro.product.board'])},
 'acdbVersion':debug('vendor_b','cat /etc/acdbdata/MTP/acdb_version').decode().strip(), 'libraries':{},'unresolved':{}}
paths=[('vendor_b','/lib64/'),('system_b','/system/lib64/'),('system_b','/system/lib64/vndk-29/'),('system_b','/system/lib64/vndk-sp-29/')]
pending=['libacdbloader.so']; seen=set()
with tempfile.TemporaryDirectory(prefix='etherphone-acdb-static-') as tmp:
 # The stock utility provides a probe executable without a foreign NDK build.
 toybox=pathlib.Path(tmp)/'toybox'
 debug('system_b','dump /system/bin/toybox '+str(toybox))
 dyn=subprocess.run(['readelf','-d',str(toybox)],capture_output=True,text=True,check=True,timeout=5).stdout
 out['probeUtilityNeeded']=re.findall(r'\(NEEDED\).*?\[(.*?)\]',dyn)
 pending.extend(out['probeUtilityNeeded'])
 while pending:
  name=pending.pop(0)
  if name in seen:continue
  assert re.fullmatch(r'[A-Za-z0-9_.+@-]+',name)
  seen.add(name);assert len(seen)<=100
  links=[];found=None
  for part,prefix in paths:
   path=prefix+name
   stat=debug(part,'stat '+path).decode()
   if 'Type: regular' in stat:found=(part,path);break
   if 'Type: symlink' in stat:links.append({'partition':part,'path':path,'stat':stat})
  if not found:
   out['unresolved'][name]={'symlinks':links,'reason':'Runtime/APEX symlink or absent from inspected library directories'}
   continue
  part,path=found;dest=pathlib.Path(tmp)/name
  debug(part,'dump '+path+' '+str(dest))
  assert dest.is_file()
  dyn=subprocess.run(['readelf','-d',str(dest)],capture_output=True,text=True,check=True,timeout=5).stdout
  hdr=subprocess.run(['readelf','-h',str(dest)],capture_output=True,text=True,check=True,timeout=5).stdout
  deps=re.findall(r'\(NEEDED\).*?\[(.*?)\]',dyn)
  item={'partition':part,'path':path,'sha256':hashlib.sha256(dest.read_bytes()).hexdigest(),'size':dest.stat().st_size,'needed':deps,'aarch64':'AArch64' in hdr,'elf64':'ELF64' in hdr}
  if name in ['libacdbloader.so','libaudcal.so']:
   symbols=subprocess.run(['readelf','-Ws',str(dest)],capture_output=True,text=True,check=True,timeout=5).stdout
   item['exports']=[l.split()[-1] for l in symbols.splitlines() if 'GLOBAL' in l and ' UND ' not in l]
   strings=subprocess.run(['strings','-a',str(dest)],capture_output=True,text=True,check=True,timeout=5).stdout
   item['relevantStrings']=[s for s in strings.splitlines() if any(x in s for x in ['/dev/','/vendor/etc','/system/etc','acdbdata','board_type','CVD Version','is_EU','param@'])][:100]
  out['libraries'][name]=item
  pending.extend(d for d in deps if d not in seen)
out['nativeGlibcCompatible']=False
out['runtimeLoadVerified']=False
out['voiceCalibrationUploadVerified']=False
print(json.dumps(out,indent=2))
'''

if __name__ == '__main__':
    result=json.loads(remote(REMOTE, timeout=110))
    path=ROOT/'evidence/etherphone-acdb-loader-selection-2026-10-21.json'
    path.write_text(json.dumps(result,indent=2)+'\n',encoding='utf-8')
    print(json.dumps({'evidence':str(path),'vendorBuild':result['vendorBuild'],
       'acdbVersion':result['acdbVersion'],'loader':result['libraries'].get('libacdbloader.so'),
       'resolvedLibraries':len(result['libraries']),'unresolved':result['unresolved']},indent=2))
