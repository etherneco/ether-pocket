"""Run the real ARM64 network engine against disposable, tunneled fixtures.

Start network_servers.py on EtherPocketBuild and forward its six fixture ports
to the phone's loopback over the pinned SSH connection first. No credentials
are printed or written into this repository. Temporary phone accounts and
their files are removed in finally, including after a test failure.
"""
from pathlib import Path
import hashlib
import json
import runpy
import shlex
import subprocess
import tarfile
import io

ROOT = Path(__file__).resolve().parent.parent
DEPLOY = runpy.run_path(str(ROOT/'scripts/deploy-etherfiles.py'))
SSH, remote = DEPLOY['SSH'], DEPLOY['remote']
FIXTURE = '/opt/etherpocket/etherfiles-network-fixtures-final'
CLIENT_ROOT = '/var/tmp/etherfiles-network-client'
RUNTIME_ROOT = '/tmp/efnetrt-phone'


if __name__ == '__main__':
    bundle = subprocess.check_output(['wsl', '-d', 'EtherPocketBuild', '--', 'tar', '-C', FIXTURE, '-cf', '-', 'fixture.json', 'known_hosts'])
    binary = (ROOT/'build/etherfiles-network-tests-arm64').read_bytes()
    # The marker and existing-account refusal prevent cleanup of an unrelated user.
    remote(r'''import pathlib,pwd,subprocess,os
try:pwd.getpwnam('efnettest')
except KeyError:pass
else:raise RuntimeError('A user named efnettest already exists; refusing reuse')
home=pathlib.Path(CLIENT_ROOT_LITERAL)
assert not home.exists(), 'A test home already exists; inspect before reusing'
assert not pathlib.Path(RUNTIME_ROOT_LITERAL).exists(), 'A test runtime directory already exists'
subprocess.run(['useradd','--system','--create-home','--home-dir',str(home),'--shell','/usr/sbin/nologin','efnettest'],check=True)
(home/'.etherfiles-network-fixture').write_text('EtherFiles disposable network test\n')
u=pwd.getpwnam('efnettest')
for p in [home/'.ssh',home/'config',home/'cache',home/'data',pathlib.Path(RUNTIME_ROOT_LITERAL)]:
 p.mkdir(mode=0o700,exist_ok=True);os.chown(p,u.pw_uid,u.pw_gid)
'''.replace('CLIENT_ROOT_LITERAL', repr(CLIENT_ROOT)).replace('RUNTIME_ROOT_LITERAL', repr(RUNTIME_ROOT)))
    try:
        remote(r'''import pathlib,pwd,tarfile,io,sys,json,os
home=pathlib.Path(CLIENT_ROOT_LITERAL);u=pwd.getpwnam('efnettest')
with tarfile.open(fileobj=io.BytesIO(sys.stdin.buffer.read())) as archive:
 assert set(archive.getnames())=={'fixture.json','known_hosts'}
 fixture=json.loads(archive.extractfile('fixture.json').read())
 for entry in fixture['targets']+fixture['reject']:
  if entry['uri'].startswith('sftp:'):entry['uri']=entry['uri'].replace('172.17.133.251','10.77.0.2')
 hosts=archive.extractfile('known_hosts').read().replace(b'172.17.133.251',b'10.77.0.2')
 for path,data in [(home/'fixture.json',json.dumps(fixture).encode()),(home/'.ssh/known_hosts',hosts)]:
  path.write_bytes(data);path.chmod(0o600);os.chown(path,u.pw_uid,u.pw_gid)
'''.replace('CLIENT_ROOT_LITERAL', repr(CLIENT_ROOT)), bundle)
        remote(r'''import pathlib,pwd,sys,hashlib,os
data=sys.stdin.buffer.read();assert hashlib.sha256(data).hexdigest()==DIGEST
p=pathlib.Path(CLIENT_ROOT_LITERAL)/'network-tests';p.write_bytes(data);p.chmod(0o755);u=pwd.getpwnam('efnettest');os.chown(p,u.pw_uid,u.pw_gid)
'''.replace('DIGEST', repr(hashlib.sha256(binary).hexdigest())).replace('CLIENT_ROOT_LITERAL', repr(CLIENT_ROOT)), binary)
        proxy = '''import socketserver,socket,select,threading,signal
stop=threading.Event()
class Proxy(socketserver.BaseRequestHandler):
 def handle(self):
  try:
   with socket.create_connection(('127.0.0.1',self.server.server_address[1]),timeout=5) as upstream:
    sockets=[self.request,upstream]
    while not stop.is_set():
     ready,_,_=select.select(sockets,[],[],.2)
     for current in ready:
      data=current.recv(65536)
      if not data:return
      (upstream if current is self.request else self.request).sendall(data)
  except OSError:pass
class Server(socketserver.ThreadingTCPServer):
 allow_reuse_address=True
 daemon_threads=True
servers=[]
for port in [22422,22423,22425]:
 server=Server(('10.77.0.2',port),Proxy);servers.append(server);threading.Thread(target=server.serve_forever,daemon=True).start()
signal.signal(signal.SIGTERM,lambda *_:stop.set())
stop.wait()
for server in servers:server.shutdown();server.server_close()
'''
        runner = '''import subprocess,time,sys
p=subprocess.Popen(['/usr/libexec/gvfsd','--no-fuse'])
time.sleep(.3)
try:sys.exit(subprocess.run(sys.argv[1:]).returncode)
finally:p.terminate();p.wait(timeout=5)
'''
        remote(r'''import pathlib,subprocess,sys,json,time
home=pathlib.Path(CLIENT_ROOT_LITERAL);files=json.loads(sys.stdin.buffer.read())
for name,source in files.items():(home/name).write_text(source)
log=(home/'proxy.log').open('wb')
subprocess.Popen(['runuser','-u','efnettest','--','python3',str(home/'proxy.py')],stdout=log,stderr=subprocess.STDOUT,start_new_session=True)
time.sleep(.3)
'''.replace('CLIENT_ROOT_LITERAL', repr(CLIENT_ROOT)), json.dumps({'proxy.py': proxy, 'run.py': runner}).encode())
        remote(r'''import pathlib,subprocess,hashlib,json,platform
home=pathlib.Path(CLIENT_ROOT_LITERAL);hosts=home/'.ssh/known_hosts';before=hashlib.sha256(hosts.read_bytes()).hexdigest()
env=['QT_QPA_PLATFORM=offscreen','LANG=C.UTF-8','XDG_CONFIG_HOME='+str(home/'config'),'XDG_CACHE_HOME='+str(home/'cache'),'XDG_DATA_HOME='+str(home/'data'),'XDG_RUNTIME_DIR='+RUNTIME_ROOT_LITERAL]
with (home/'run.log').open('wb') as log:
 result=subprocess.run(['runuser','-u','efnettest','--','env']+env+['dbus-run-session','--','python3',str(home/'run.py'),str(home/'network-tests'),str(home/'fixture.json'),str(home/'results.json')],stdout=log,stderr=subprocess.STDOUT,timeout=240)
report={'architecture':platform.machine(),'returncode':result.returncode,'known_hosts_unchanged':before==hashlib.sha256(hosts.read_bytes()).hexdigest(),'results':json.loads((home/'results.json').read_text())}
(home/'public-result.json').write_text(json.dumps(report,indent=2))
print(json.dumps(report,indent=2))
assert result.returncode==0 and report['known_hosts_unchanged'], 'Network acceptance failed; public results retain the failure'
'''.replace('CLIENT_ROOT_LITERAL', repr(CLIENT_ROOT)).replace('RUNTIME_ROOT_LITERAL', repr(RUNTIME_ROOT)))
    finally:
        result = subprocess.run(SSH+['cat '+shlex.quote(CLIENT_ROOT+'/public-result.json')], capture_output=True, check=False)
        if result.returncode == 0:
            (ROOT/'evidence/etherfiles-network-arm64.json').write_bytes(result.stdout)
        remote(r'''import pathlib,pwd,subprocess,shutil,time
home=pathlib.Path(CLIENT_ROOT_LITERAL);runtime=pathlib.Path(RUNTIME_ROOT_LITERAL)
u=pwd.getpwnam('efnettest');assert pathlib.Path(u.pw_dir)==home and (home/'.etherfiles-network-fixture').is_file()
subprocess.run(['pkill','-TERM','-u',str(u.pw_uid)],check=False)
for attempt in range(50):
 if subprocess.run(['pgrep','-u',str(u.pw_uid)],capture_output=True).returncode:break
 time.sleep(.1)
else:
 subprocess.run(['pkill','-KILL','-u',str(u.pw_uid)],check=False)
 time.sleep(.3)
subprocess.run(['userdel','efnettest'],check=True)
assert home.resolve()==pathlib.Path('/var/tmp/etherfiles-network-client')
assert runtime.resolve()==pathlib.Path('/tmp/efnetrt-phone')
shutil.rmtree(home);shutil.rmtree(runtime)
print('Disposable phone test account and credentials removed.')
'''.replace('CLIENT_ROOT_LITERAL', repr(CLIENT_ROOT)).replace('RUNTIME_ROOT_LITERAL', repr(RUNTIME_ROOT)))
