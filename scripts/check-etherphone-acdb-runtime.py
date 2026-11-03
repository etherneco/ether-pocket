"""Load the original ACDB library in an isolated temporary Android runtime.

Runs only stock toybox with LD_PRELOAD and inspects process maps. Does NOT call
ACDB initialization/calibration functions. No handset devices are exposed.
"""
import json
import runpy
from pathlib import Path

ROOT=Path(__file__).resolve().parent.parent
remote=runpy.run_path(str(ROOT/'scripts/check-etherphone-device.py'))['remote']
REMOTE=r'''
import hashlib,json,os,pathlib,re,resource,subprocess,tempfile,zipfile
manifest=json.loads(__import__('sys').stdin.buffer.read())
assert pathlib.Path('/etc/etherpocket/disk-identity').read_text().strip()=='GM1920-548cb338-mobian-sda21'
def debug(device,op):
 p=subprocess.run(['debugfs','-R',op,device],capture_output=True,timeout=20)
 return p.stdout
def dump(device,src,dst):
 dst.parent.mkdir(parents=True,exist_ok=True)
 debug(device,'dump '+src+' '+str(dst));assert dst.is_file(),src
def limits():
 resource.setrlimit(resource.RLIMIT_CORE,(0,0))
 resource.setrlimit(resource.RLIMIT_CPU,(8,8))
with tempfile.TemporaryDirectory(prefix='etherphone-acdb-runtime-') as temp:
 tmp=pathlib.Path(temp);root=tmp/'root';root.mkdir()
 system='/dev/disk/by-partlabel/system_b';vendor='/dev/disk/by-partlabel/vendor_b'
 apex=tmp/'runtime.apex';dump(system,'/system/apex/com.android.runtime.release.apex',apex)
 payload=tmp/'runtime.img'
 with zipfile.ZipFile(apex) as z:
  info=z.getinfo('apex_payload.img');assert info.file_size<512*1024*1024
  with z.open(info) as src,payload.open('wb') as dst:
   import shutil
   shutil.copyfileobj(src,dst)
 core={}
 for src,dst in [('/bin/linker64','/apex/com.android.runtime/bin/linker64')]+[('/lib64/bionic/'+n,'/apex/com.android.runtime/lib64/bionic/'+n) for n in ['libc.so','libm.so','libdl.so']]:
  target=root/dst.lstrip('/');dump(str(payload),src,target);target.chmod(0o755)
  core[dst]={'sha256':hashlib.sha256(target.read_bytes()).hexdigest(),'size':target.stat().st_size}
 libs={}
 for name,item in manifest['libraries'].items():
  src=item['path'];dst=('/vendor'+src) if item['partition']=='vendor_b' else src
  target=root/dst.lstrip('/');dump('/dev/disk/by-partlabel/'+item['partition'],src,target)
  assert hashlib.sha256(target.read_bytes()).hexdigest()==item['sha256'],name
  target.chmod(0o644)
  libs[name]=dst
 target=root/'system/bin/toybox';dump(system,'/system/bin/toybox',target);target.chmod(0o755)
 dyn=subprocess.run(['readelf','-d',str(target)],capture_output=True,text=True,check=True).stdout
 deps=re.findall(r'\(NEEDED\).*?\[(.*?)\]',dyn)
 assert all(n in libs or n in ['libc.so','libm.so','libdl.so'] for n in deps),deps
 (root/'system/bin/linker64').symlink_to('/apex/com.android.runtime/bin/linker64')
 for n in ['libc.so','libm.so','libdl.so']:
  (root/'system/lib64'/n).symlink_to('/apex/com.android.runtime/lib64/bionic/'+n)
 for d in ['dev','proc','sys','data','vendor/etc']:(root/d).mkdir(parents=True,exist_ok=True)
 # Bionic requires /dev/null during libc initialization. No physical devices.
 import stat
 os.mknod(root/'dev/null',stat.S_IFCHR|0o666,os.makedev(1,3));(root/'dev/null').chmod(0o666)
 root.chmod(0o755)
 for directory in root.rglob('*'):
  if directory.is_dir():directory.chmod(0o755)
 search='/vendor/lib64:/system/lib64:/system/lib64/vndk-29:/system/lib64/vndk-sp-29:/apex/com.android.runtime/lib64/bionic'
 # This downstream kernel lacks PID namespaces. Drop to nobody inside chroot;
 # proc permission checks then prevent access to root-owned host processes.
 wrapper='import os,subprocess,sys; subprocess.run(["mount","--bind","/dev/null",sys.argv[1]+"/dev/null"],check=True); os.execvp("chroot",["chroot","--userspec=65534:65534",sys.argv[1]]+sys.argv[2:])'
 base=['unshare','--mount','--net','--fork','--mount-proc='+str(root/'proc'),'python3','-c',wrapper,str(root),'/system/bin/toybox','env','LD_LIBRARY_PATH='+search]
 env={'PATH':'/usr/sbin:/usr/bin:/sbin:/bin','LANG':'C'}
 linker=subprocess.run(base[:base.index('/system/bin/toybox')]+['/apex/com.android.runtime/bin/linker64','--help'],capture_output=True,text=True,timeout=12,env=env,preexec_fn=limits)
 tracePrefix=[]
 if manifest.get('_straceBase64'):
  import base64
  traceTool=tmp/'strace';traceTool.write_bytes(base64.b64decode(manifest['_straceBase64']));traceTool.chmod(0o755)
  tracePrefix=[str(traceTool),'-f','-o',str(tmp/'trace.txt')]
 baseline=subprocess.run(tracePrefix+base+['/system/bin/toybox','true'],capture_output=True,text=True,timeout=12,env=env,preexec_fn=limits)
 probe=subprocess.run(base+['LD_PRELOAD=/vendor/lib64/libacdbloader.so','LD_BIND_NOW=1','/system/bin/toybox','cat','/proc/self/maps'],capture_output=True,text=True,timeout=12,env=env,preexec_fn=limits)
 mapped=sorted(set(l.split()[-1] for l in probe.stdout.splitlines() if '/' in l))
 result={'scope':'Temporary private mount/network namespaces and chroot, unprivileged nobody user, only /dev/null and empty /sys. No physical devices. Only stock toybox cat; no ACDB init/send functions called. Temporary files removed on exit.',
 'linker':{'exit':linker.returncode,'stdout':linker.stdout,'stderr':linker.stderr},
 'baseline':{'exit':baseline.returncode,'stderr':baseline.stderr},'probe':{'exit':probe.returncode,'stderr':probe.stderr,'mappedFiles':mapped},
 'coreRuntime':core,'toyboxNeeded':deps,
 'loaderMapped':'/vendor/lib64/libacdbloader.so' in mapped,
 'parserMapped':'/vendor/lib64/libaudcal.so' in mapped,
 'acdbInitializationVerified':False,'calibrationUploadVerified':False}
 result['dynamicLoadVerified']=probe.returncode==0 and result['loaderMapped'] and result['parserMapped']
 if tracePrefix:
  lines=(tmp/'trace.txt').read_text().splitlines()
  result['baselineTraceTail']='\n'.join(lines[-65:])
  result['baselineTraceErrors']='\n'.join(l for l in lines if any(e in l for e in ['EACCES','ENOENT','EPERM']))[-16000:]
 print(json.dumps(result,indent=2))
'''
if __name__=='__main__':
    manifest=json.loads((ROOT/'evidence/etherphone-acdb-loader-selection-2026-10-21.json').read_text())
    import sys,base64
    if '--trace' in sys.argv:
        manifest['_straceBase64']=base64.b64encode((ROOT/'build/etherphone-acdb-research/strace-arm64').read_bytes()).decode()
    result=json.loads(remote(REMOTE,json.dumps(manifest).encode(),timeout=90))
    (ROOT/'evidence/etherphone-acdb-runtime-check-2026-10-21.json').write_text(json.dumps(result,indent=2)+'\n',encoding='utf-8')
    print(json.dumps(result,indent=2))
