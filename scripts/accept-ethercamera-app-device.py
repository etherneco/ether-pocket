"""Install only disposable QA runner files, test installed camera Python on
private buses/displays, and collect artefacts. Never supplies a physical source.
"""
from pathlib import Path
import io,json,runpy,shlex,subprocess,tarfile
ROOT=Path(__file__).resolve().parent.parent
SSH=runpy.run_path(str(ROOT/'scripts/deploy-ethermobile.py'))['SSH']

def upload(target,payload,mode=0o644):
 source=f'import pathlib,sys; p=pathlib.Path({target!r});p.write_bytes(sys.stdin.buffer.read());p.chmod({mode})'
 subprocess.run(SSH+['python3 -c '+shlex.quote(source)],input=payload,check=True,timeout=20)

if __name__=='__main__':
 folder='/var/tmp/ethercamera-capture-qa-0.3.0'
 subprocess.run(SSH+['install -d -o mobian -g mobian -m 700 '+folder],check=True)
 for file in ['test-ethercamera-capture.py','test-ethercamera-media.py']:
  upload(folder+'/'+file,(ROOT/'scripts'/file).read_bytes())
 binary=subprocess.check_output(['wsl','-d','EtherPocketBuild','--','cat','/opt/etherpocket/ethercamera-arm64/ethercamera-ui-test'])
 upload(folder+'/ethercamera-ui-test',binary,0o755)
 user=['runuser','-u','mobian','--','env','XDG_RUNTIME_DIR=/run/user/1000','DBUS_SESSION_BUS_ADDRESS=unix:path=/run/user/1000/bus']
 for kind,binary in [('capture',folder+'/ethercamera-ui-test'),('media','/usr/bin/ethercamera-media')]:
  output=folder+'/'+kind
  command=user+['python3',folder+'/test-ethercamera-'+kind+'.py','--binary',binary,'--source','/usr/share/ethercamera','--output',output]
  p=subprocess.run(SSH+[' '.join(shlex.quote(s) for s in command)],capture_output=True,text=True,timeout=250)
  (ROOT/'build'/('ethercamera-'+kind+'-arm64-console.txt')).write_text(p.stdout+p.stderr,encoding='utf-8')
  if p.returncode:raise RuntimeError((p.stdout+p.stderr)[-7000:])
  archive=subprocess.check_output(SSH+['tar -C '+shlex.quote(output)+' -cf - .'],timeout=30)
  destination=ROOT/'evidence'/('ethercamera-'+kind+'-arm64');destination.mkdir(exist_ok=True)
  with tarfile.open(fileobj=io.BytesIO(archive)) as tar:tar.extractall(destination,filter='data')
  data=json.loads((destination/'acceptance.json').read_text());print(kind,':',len(data),'acceptance results collected',flush=True)
