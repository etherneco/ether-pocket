"""Verify service authorization independently of UI and release metadata."""
import importlib.util
from pathlib import Path
import sys
import os
import unittest
from unittest.mock import Mock, patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
AVAILABLE=importlib.util.find_spec('dbus') is not None
if AVAILABLE:
    from service import Service
    import dbus


@unittest.skipUnless(AVAILABLE,'Linux D-Bus bindings')
class AuthorizationTest(unittest.TestCase):
    def service(self):
        # No system bus registration or privileged host changes.
        s=object.__new__(Service);s.bus=Mock();s.bus.get_unix_user.return_value=1000
        s.busy=False;s.authorizing=False;s.work=Mock()
        return s

    def test_denied_polkit_cannot_execute_operation(self):
        s=self.service();authority=Mock();operation=Mock();success=Mock();failure=Mock()
        authority.CheckAuthorization.side_effect=lambda *args,**kw:kw['reply_handler']((False,False,{}))
        with patch('service.dbus.Interface',return_value=authority):
            s.authorize(':1.42','install',operation,success,failure)
        s.work.assert_not_called();operation.assert_not_called();failure.assert_called_once()

    def test_authority_failure_cannot_execute_operation(self):
        s=self.service();authority=Mock();operation=Mock();failure=Mock()
        authority.CheckAuthorization.side_effect=lambda *args,**kw:kw['error_handler'](RuntimeError('Unavailable'))
        with patch('service.dbus.Interface',return_value=authority):s.authorize(':1.42','install',operation,Mock(),failure)
        s.work.assert_not_called();operation.assert_not_called();failure.assert_called_once()

    def test_authorized_operation_uses_derived_uid_and_unique_sender(self):
        s=self.service();authority=Mock();operation=Mock()
        authority.CheckAuthorization.side_effect=lambda *args,**kw:kw['reply_handler']((True,False,{}))
        with patch('service.dbus.Interface',return_value=authority):s.authorize(':1.42','install',operation,Mock(),Mock())
        args=authority.CheckAuthorization.call_args.args
        self.assertEqual(args[0][0],'system-bus-name');self.assertEqual(args[0][1]['name'],':1.42')
        self.assertEqual(args[1],'com.etherneco.etherupdate.install')
        s.work.call_args.args[0]();operation.assert_called_once_with(1000)

    def test_disconnected_caller_is_rejected_after_authorization(self):
        s=self.service();s.bus.get_unix_user.side_effect=[1000,dbus.DBusException('Gone')]
        authority=Mock();operation=Mock();failure=Mock()
        authority.CheckAuthorization.side_effect=lambda *args,**kw:kw['reply_handler']((True,False,{}))
        with patch('service.dbus.Interface',return_value=authority):s.authorize(':1.42','install',operation,Mock(),failure)
        s.work.assert_not_called();failure.assert_called_once()

    def test_busy_service_cannot_authorize_concurrent_install(self):
        s=self.service();s.busy=True;operation=Mock();failure=Mock()
        s.authorize(':1.42','install',operation,Mock(),failure)
        s.work.assert_not_called();failure.assert_called_once()

    def test_credential_denial_closes_descriptor_and_never_reads_secret(self):
        s=self.service();authority=Mock();failure=Mock();reader,writer=os.pipe()
        os.close(writer);descriptor=Mock();descriptor.take.return_value=reader
        authority.CheckAuthorization.side_effect=lambda *args,**kw:kw['reply_handler']((False,False,{}))
        with patch('service.dbus.Interface',return_value=authority):s.SetCredential(descriptor,':1.42',Mock(),failure)
        self.assertEqual(authority.CheckAuthorization.call_args.args[1],'com.etherneco.etherupdate.credentials')
        with self.assertRaises(OSError):os.fstat(reader)
        s.work.assert_not_called();failure.assert_called_once()
