"""Pipe lifecycle contracts only; never starts a receiver or generates fixes."""
import json,os,sys,unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
try:from gnss import Gnss
except ImportError:Gnss=None

@unittest.skipIf(Gnss is None,'Linux GLib runtime required')
class GnssLifecycleTests(unittest.TestCase):
    def pipe(self,payload):
        states=[];g=Gnss(lambda p:self.fail('Lifecycle test must never receive coordinates'),lambda state,error:states.append((state,error)),lambda rows:None)
        r,w=os.pipe();os.write(w,payload);os.close(w)
        class Process:
            stdout=os.fdopen(r,'rb')
            def wait(self,timeout):return 0
        g.process=Process();g.active=True
        return g,r,states
    def test_unsupported_preserved_after_clean_helper_exit(self):
        g,fd,states=self.pipe(json.dumps(dict(event='status',state='Unsupported',error='No QRTR node')).encode()+b'\n')
        self.assertTrue(g.read(fd,0));self.assertFalse(g.read(fd,0))
        self.assertEqual(states,[('Unsupported','No QRTR node')]);self.assertFalse(g.active);self.assertIsNone(g.process)
    def test_unexpected_helper_exit_is_an_error(self):
        g,fd,states=self.pipe(b'')
        self.assertFalse(g.read(fd,0));self.assertEqual(states[-1][0],'Error');self.assertFalse(g.active)

if __name__=='__main__':unittest.main()
