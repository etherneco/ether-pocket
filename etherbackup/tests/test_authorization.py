"""Exercise real service authorization gates without registering a host service."""
import importlib.util
from pathlib import Path
import sys
import unittest
from unittest.mock import Mock,patch
import os,tempfile
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
AVAILABLE=importlib.util.find_spec('dbus') is not None
if AVAILABLE:
 from service import Service
 import dbus

@unittest.skipUnless(AVAILABLE,'Linux D-Bus bindings')
class AuthorizationTests(unittest.TestCase):
 def service(self):
  s=object.__new__(Service);s.bus=Mock();s.bus.get_unix_user.return_value=1000;s.busy=False;s.authorizing=False;s.pool=Mock();s.state={}
  s.Changed=Mock();s.GetState=Mock(return_value='{}');return s
 def setUp(self):
  self.process=patch('service.graphical_process',return_value=dict(pid=123,start=1,uid=1000));self.process.start();self.addCleanup(self.process.stop)
 def authority(self):
  a=Mock();a.Get.return_value=('c1','/session');a.GetAll.return_value=dict(Active=True,LockedHint=False,User=(1000,'/user'),Scope='session-c1.scope')
  return a
 def test_denied_authority_cannot_start_worker(self):
  s=self.service();authority=self.authority();op=Mock();failed=Mock()
  authority.CheckAuthorization.side_effect=lambda *args,**kw:kw['reply_handler']((False,False,{}))
  with patch('service.dbus.Interface',return_value=authority):s.authorize(':1.20','restore',op,Mock(),failed)
  op.assert_not_called();s.pool.submit.assert_not_called();failed.assert_called_once()
 def test_authority_error_fails_closed(self):
  s=self.service();authority=self.authority();op=Mock();failed=Mock()
  authority.CheckAuthorization.side_effect=lambda *args,**kw:kw['error_handler'](RuntimeError('Unavailable'))
  with patch('service.dbus.Interface',return_value=authority):s.authorize(':1.20','manage',op,Mock(),failed)
  s.pool.submit.assert_not_called();self.assertFalse(s.authorizing)
 def test_locked_session_cannot_start_restore(self):
  s=self.service();authority=self.authority();failed=Mock()
  authority.CheckAuthorization.side_effect=lambda *args,**kw:kw['reply_handler']((True,False,{}))
  authority.GetAll.return_value=dict(Active=True,LockedHint=True,User=(1000,'/user'),Scope='session-c1.scope')
  authority.Get.return_value=('c1','/session')
  authority.GetConnectionUnixProcessID.return_value=123;authority.GetSessionByPID.return_value='/session'
  with patch('service.dbus.Interface',return_value=authority):s.authorize(':1.20','restore',Mock(),Mock(),failed)
  s.pool.submit.assert_not_called();failed.assert_called_once()
 def test_unique_sender_and_uncached_action(self):
  s=self.service();authority=self.authority()
  authority.CheckAuthorization.side_effect=lambda *args,**kw:kw['reply_handler']((True,False,{}))
  authority.GetAll.return_value=dict(Active=True,LockedHint=False,User=(1000,'/user'),Scope='session-c1.scope')
  authority.Get.return_value=('c1','/session')
  authority.GetConnectionUnixProcessID.return_value=123;authority.GetSessionByPID.return_value='/session'
  with patch('service.dbus.Interface',return_value=authority):s.authorize(':1.20','inspect',Mock(),Mock(),Mock())
  self.assertEqual(authority.CheckAuthorization.call_args.args[0][0],'unix-process')
  self.assertEqual(authority.CheckAuthorization.call_args.args[0][1]['uid'],1000)
  self.assertEqual(authority.CheckAuthorization.call_args.args[1],'com.etherneco.etherbackup.inspect')
  s.pool.submit.assert_called_once()
 def test_disconnected_sender_fails_closed(self):
  s=self.service();s.bus.get_unix_user.side_effect=[1000,dbus.DBusException('Gone')];authority=self.authority()
  authority.CheckAuthorization.side_effect=lambda *args,**kw:kw['reply_handler']((True,False,{}))
  with patch('service.dbus.Interface',return_value=authority):s.authorize(':1.20','restore',Mock(),Mock(),Mock())
  s.pool.submit.assert_not_called()
 def test_other_users_display_is_rejected_before_prompt(self):
  s=self.service();authority=self.authority();authority.GetAll.return_value=dict(Active=True,LockedHint=False,User=(2000,'/user'))
  with patch('service.dbus.Interface',return_value=authority):s.authorize(':1.20','inspect',Mock(),Mock(),Mock())
  authority.CheckAuthorization.assert_not_called();s.pool.submit.assert_not_called()
 def test_session_change_during_authorization_is_rejected(self):
  s=self.service();authority=self.authority();authority.GetAll.side_effect=[dict(Active=True,LockedHint=False,User=(1000,'/user'),Scope='session-c1.scope'),dict(Active=True,LockedHint=True,User=(1000,'/user'),Scope='session-c1.scope')]
  authority.CheckAuthorization.side_effect=lambda *args,**kw:kw['reply_handler']((True,False,{}))
  with patch('service.dbus.Interface',return_value=authority):s.authorize(':1.20','restore',Mock(),Mock(),Mock())
  s.pool.submit.assert_not_called()
 def test_root_cli_keeps_unique_bus_subject(self):
  s=self.service();s.bus.get_unix_user.return_value=0;authority=self.authority()
  authority.CheckAuthorization.side_effect=lambda *args,**kw:kw['reply_handler']((True,False,{}))
  with patch('service.dbus.Interface',return_value=authority):s.authorize(':1.20','inspect',Mock(),Mock(),Mock())
  self.assertEqual(authority.CheckAuthorization.call_args.args[0][1]['name'],':1.20')
  s.pool.submit.assert_called_once()
 def test_report_event_root_only(self):
  s=self.service()
  with self.assertRaises(dbus.DBusException):s.ReportEvent('backup-completed',':1.20')
 def test_overlap_does_not_prompt(self):
  s=self.service();s.busy=True;failed=Mock()
  with patch('service.dbus.Interface') as authority:s.authorize(':1.20','manage',Mock(),Mock(),failed)
  authority.assert_not_called();failed.assert_called_once()

class GraphicalProcessTests(unittest.TestCase):
 def test_only_same_uid_process_from_logind_scope_is_selected(self):
  from authorization import graphical_process
  from security import BackupError
  with tempfile.TemporaryDirectory() as folder:
   root=Path(folder);uid=os.getuid() or 1000;scope='session-c1.scope'
   group=root/'groups/user.slice'/('user-'+str(uid)+'.slice')/scope;group.mkdir(parents=True)
   (group/'cgroup.procs').write_text('123\n')
   proc=root/'proc/123';proc.mkdir(parents=True)
   (proc/'stat').write_text('123 (desktop session) '+' '.join(['S']+['0']*18+['99']))
   (proc/'cgroup').write_text('0::/user.slice/user-'+str(uid)+'.slice/'+scope+'\n')
   if os.getuid()==0:os.chown(proc,uid,uid)
   self.assertEqual(graphical_process(uid,scope,root/'groups',root/'proc'),dict(pid=123,start=99,uid=uid))
   (proc/'cgroup').write_text('0::/other.scope\n')
   with self.assertRaises(BackupError):graphical_process(uid,scope,root/'groups',root/'proc')
   with self.assertRaises(BackupError):graphical_process(uid,'../../other',root/'groups',root/'proc')
   with self.assertRaises(BackupError):graphical_process(0,scope,root/'groups',root/'proc')
