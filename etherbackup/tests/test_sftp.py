"""Real pinned-key SFTP round trip using a disposable loopback SSH server only."""
import json
import os
from pathlib import Path
import shutil
import signal
import socket
import subprocess
import sys
import tempfile
import time
import unittest
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from adapter import Restic
from core import Core
from destinations import inspect
from security import BackupError
from test_backup import contract

@unittest.skipUnless(os.geteuid()==0 and Path('/usr/sbin/sshd').exists() and shutil.which('restic'),'Disposable SSH server requires root, sshd and Restic')
class SFTPTests(unittest.TestCase):
 def test_pinned_host_encrypted_restore_and_connection_retry(self):
  with tempfile.TemporaryDirectory(prefix='etherbackup-sftp-',dir=Path.home()) as folder:
   root=Path(folder)
   for name in ('host','client','wrong-host'):
    subprocess.run(['ssh-keygen','-q','-t','ed25519','-N','','-f',str(root/name)],check=True,capture_output=True)
   (root/'authorized_keys').write_bytes((root/'client.pub').read_bytes());(root/'authorized_keys').chmod(0o600)
   with socket.socket() as s:s.bind(('127.0.0.1',0));port=s.getsockname()[1]
   hostkey=' '.join((root/'host.pub').read_text().split()[:2]);wrong=' '.join((root/'wrong-host.pub').read_text().split()[:2])
   known=root/'known_hosts';known.write_text('[127.0.0.1]:'+str(port)+' '+hostkey+'\n')
   key=root/'password';key.write_text(os.urandom(32).hex());key.chmod(0o600)
   ssh_config=root/'ssh_config';ssh_config.write_text('Host isolated-backup\n HostName 127.0.0.1\n User root\n Port '+str(port)+'\n')
   server_config=root/'sshd_config'
   server_config.write_text(f'Port {port}\nListenAddress 127.0.0.1\nHostKey {root}/host\nPidFile {root}/sshd.pid\nAuthorizedKeysFile {root}/authorized_keys\nPermitRootLogin yes\nPasswordAuthentication no\nKbdInteractiveAuthentication no\nUsePAM yes\nStrictModes yes\nSubsystem sftp internal-sftp\nLogLevel ERROR\n')
   Path('/run/sshd').mkdir(mode=0o755,exist_ok=True)
   server=None
   def start():
    nonlocal server
    server=subprocess.Popen(['/usr/sbin/sshd','-D','-e','-f',str(server_config)],stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,start_new_session=True)
    for _ in range(50):
     if server.poll() is not None:raise RuntimeError('Disposable SSH server failed')
     try:
      with socket.create_connection(('127.0.0.1',port),timeout=.1):return
     except OSError:time.sleep(.05)
    raise RuntimeError('Disposable SSH server did not listen')
   def stop():
    nonlocal server
    if server and server.poll() is None:os.killpg(server.pid,signal.SIGTERM);server.wait(timeout=10)
   config=dict(kind='sftp',repository=f'sftp:isolated-backup:{root}/repo',passwordFile=str(key),sshConfig=str(ssh_config),knownHosts=str(known),sshKey=str(root/'client'))
   start()
   try:
    options=inspect(config)['options'];engine=Restic(config,root/'cache',options);engine.init()
    source=root/'source';source.mkdir();(source/'document').write_text('remote original')
    policy=dict(sources={'app':contract([source])},profiles={'personal':['app']},destinations={'remote':config})
    core=Core(root/'state',policy,safety=lambda:dict(allowed=True));row=core.backup('personal','remote')
    known.write_text('[127.0.0.1]:'+str(port)+' '+wrong+'\n')
    with self.assertRaises(BackupError):engine.snapshots()
    known.write_text('[127.0.0.1]:'+str(port)+' '+hostkey+'\n')
    stop()
    with self.assertRaises(BackupError):engine.snapshots()
    start();self.assertTrue(core.verify(row['id'])['passed'])
    result=core.restore(row['id'],'',True)
    self.assertEqual((Path(result['destination'])/str(source/'document').lstrip('/')).read_text(),'remote original')
   finally:stop()

if __name__=='__main__':unittest.main()
