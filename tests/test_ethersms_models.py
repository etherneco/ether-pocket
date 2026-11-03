import hashlib
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
ROOT=Path(__file__).resolve().parents[1]
HELPER=ROOT/'ethersms/ethersms-model'
class ModelTests(unittest.TestCase):
 def call(self,home,*args):
  return subprocess.run([sys.executable,str(HELPER),*args],env=dict(os.environ,HOME=str(home),USERPROFILE=str(home)),capture_output=True,text=True,timeout=10)
 def test_linux_shebang(self):
  self.assertTrue(HELPER.read_bytes().startswith(b"#!/usr/bin/python3\n"))
 def test_checksum_and_atomic_collision(self):
  with tempfile.TemporaryDirectory() as folder:
   home=Path(folder);source=home/'ggml-tiny.bin';source.write_bytes(b'isolated test fixture, not a speech model')
   checksum=hashlib.sha256(source.read_bytes()).hexdigest()
   self.assertNotEqual(self.call(home,'install',str(source),'0'*64).returncode,0)
   self.assertEqual(self.call(home,'install',str(source),checksum).returncode,0)
   target=home/'.local/share/Etherneco/EtherSMS/models/ggml-tiny.bin'
   self.assertEqual(target.read_bytes(),source.read_bytes())
   self.assertNotEqual(self.call(home,'install',str(source),checksum).returncode,0)
   self.assertEqual(len(list(target.parent.iterdir())),1)
 def test_download_requires_consent_and_digest(self):
  with tempfile.TemporaryDirectory() as home:
   self.assertNotEqual(self.call(home,'download','base','0'*64).returncode,0)
   self.assertNotEqual(self.call(home,'download','base','bad','--approved').returncode,0)
 def test_paths_and_english_only_models_rejected(self):
  with tempfile.TemporaryDirectory() as home:
   self.assertNotEqual(self.call(home,'remove','../private').returncode,0)
   self.assertNotEqual(self.call(home,'install',str(Path(home)/'ggml-base.en.bin'),'0'*64).returncode,0)
if __name__=='__main__':unittest.main()
