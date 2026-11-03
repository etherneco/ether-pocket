import base64
from contextlib import nullcontext
import hashlib
import io
import json
import os
from pathlib import Path
import sys
import tarfile
import tempfile
import threading
import unittest
from unittest.mock import Mock
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from cryptography.hazmat.primitives.serialization import Encoding, PublicFormat
from agent import Agent
from artifacts import ArtifactManager
from engine import InstallationEngine, newer
from history import History
from provider import Provider, ProviderError, Release
from security import Rejected, verify_envelope, verify_file

DEVICE=dict(architecture='arm64',distribution='debian',distribution_major=13,device_family='oneplus7pro',kernel_abi='4.14.117-perf')
SAFE=dict(battery=80,callActive=False,recording=False,criticalActivity=False)


class UpdateTest(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.root=Path(self.temp.name);self.addCleanup(self.temp.cleanup)
        self.private=Ed25519PrivateKey.generate()
        self.keys={'test':dict(public_key=base64.b64encode(self.private.public_key().public_bytes(Encoding.Raw,PublicFormat.Raw)).decode(),projects=['test-app'])}
        self.policy=dict(package='test-app',type='versioned-bundle',critical=False,health=[['/usr/bin/true']])
        self.path=self.bundle('good')
        self.manifest=dict(schema=1,project='test-app',package='test-app',version='2.0.0',channel='Stable',type='versioned-bundle',
                           size=self.path.stat().st_size,sha256=hashlib.sha256(self.path.read_bytes()).hexdigest(),compatibility=DEVICE)


    def bundle(self,content,name='app.txt',kind=None):
        path=self.root/'bundle.tar.gz'
        with tarfile.open(path,'w:gz') as archive:
            info=tarfile.TarInfo(name);data=content.encode();info.size=len(data);info.mode=0o644
            if kind:info.type=kind;info.linkname='/etc/passwd';info.size=0
            archive.addfile(info,io.BytesIO(data))
        return path

    def envelope(self,m=None):
        payload=json.dumps(m or self.manifest,separators=(',',':')).encode()
        return dict(key_id='test',payload=base64.b64encode(payload).decode(),signature=base64.b64encode(self.private.sign(payload)).decode())

    def agent(self,runner=None):
        engine=InstallationEngine(self.root/'components',runner or (lambda *args: ''))
        backup=Mock();backup.request.return_value=dict(id='test-point',snapshot='f'*64,sampleVerified=True);backup.result.return_value=dict(recorded=True)
        agent=Agent(self.root/'state',self.root/'cache',dict(components={'test-app':self.policy}),self.keys,DEVICE,engine=engine,backup=backup)
        self.addCleanup(agent.history.db.close)
        return agent

    def imported(self,agent):return agent.import_offline('test-app','Stable',self.envelope(),self.path)

    def previous(self,agent):
        base=agent.engine.root/'test-app';old=base/'1.0.0';old.mkdir(parents=True);(old/'app.txt').write_text('old')
        (base/'current').symlink_to('1.0.0',target_is_directory=True)
        return old

    def test_signed_manifest(self):
        self.assertEqual(verify_envelope(self.envelope(),self.keys,'test-app','Stable',DEVICE),self.manifest)

    def test_signature_tamper_and_unknown_key(self):
        e=self.envelope();e['payload']=base64.b64encode(b'{}').decode()
        with self.assertRaises(Rejected):verify_envelope(e,self.keys,'test-app','Stable',DEVICE)
        with self.assertRaises(Rejected):verify_envelope(self.envelope(),{},'test-app','Stable',DEVICE)

    def test_rotation_revocation_and_scope(self):
        self.keys['test']['revoked']=True
        with self.assertRaises(Rejected):verify_envelope(self.envelope(),self.keys,'test-app','Stable',DEVICE)
        self.keys['test']['revoked']=False;self.keys['test']['projects']=[]
        with self.assertRaises(Rejected):verify_envelope(self.envelope(),self.keys,'test-app','Stable',DEVICE)

    def test_compatibility_requires_kernel_device_and_os(self):
        for key in DEVICE:
            with self.subTest(key=key), self.assertRaises(Rejected):
                verify_envelope(self.envelope(),self.keys,'test-app','Stable',dict(DEVICE,**{key:'wrong'}))

    def test_project_channel_and_critical_type(self):
        with self.assertRaises(Rejected):verify_envelope(self.envelope(),self.keys,'test-app','Beta',DEVICE)
        with self.assertRaises(Rejected):verify_envelope(self.envelope(dict(self.manifest,type='boot-image')),self.keys,'test-app','Stable',DEVICE)

    def test_file_tampering(self):
        self.path.write_bytes(b'corrupt')
        with self.assertRaises(Rejected):verify_file(self.path,self.manifest)

    @unittest.skipUnless(os.name=='posix','Debian version comparator')
    def test_debian_version_order(self):
        self.assertTrue(newer('1:1.0','9.0'));self.assertTrue(newer('1.0','1.0~rc1'))
        self.assertFalse(newer('1.0~beta1','1.0'));self.assertFalse(newer('1.0','1.0'))

    def test_redirects_and_token_urls_blocked(self):
        p=Provider('secret')
        for url in ('http://autoupddate.etherneco.com/file','https://evil.invalid/file','https://autoupddate.etherneco.com/f?token=secret'):
            with self.assertRaises(Rejected):p.open(url)

    def test_transfer_cancellation_and_partial_cleanup(self):
        p=Mock();response=Mock();response.status=200;response.read.side_effect=[b'content',b'']
        response.__enter__=Mock(return_value=response);response.__exit__=Mock(return_value=False);p.open.return_value=response
        a=ArtifactManager(self.root/'cache',p);event=threading.Event();event.set()
        with self.assertRaises(Rejected):a.download(self.manifest,'https://example.invalid',event,lambda *args:None)
        self.assertEqual(list(a.directory.glob('*.part')),[])

    def test_oversized_transfer_refused(self):
        p=Mock();response=Mock();response.status=200;response.read.side_effect=[b'x'*(self.manifest['size']+1),b'']
        response.__enter__=Mock(return_value=response);response.__exit__=Mock(return_value=False);p.open.return_value=response
        a=ArtifactManager(self.root/'cache',p)
        with self.assertRaises(Rejected):a.download(self.manifest,'url',threading.Event(),lambda *args:None)
        self.assertFalse(a.path(self.manifest).exists())

    def test_history_persists_and_restart_is_not_success(self):
        history=History(self.root/'history.sqlite');self.addCleanup(history.db.close);ident=history.create({})
        for state in ('Available','Downloading','Downloaded','Verifying','Verified','Preparing','Installing'):history.transition(ident,state)
        history.db.close();history=History(self.root/'history.sqlite');self.addCleanup(history.db.close);history.interrupted()
        self.assertEqual(history.get(ident)['state'],'Recovery Required')
        with self.assertRaises(Rejected):history.transition(ident,'Completed')

    def test_state_ordering(self):
        h=History(self.root/'h.sqlite');self.addCleanup(h.db.close);ident=h.create({})
        with self.assertRaises(Rejected):h.transition(ident,'Completed')

    def test_safety_unknown_calls_recording_and_low_battery(self):
        for changes in (dict(battery=5),dict(callActive=True),dict(recording=True),dict(criticalActivity=None),dict(battery=None)):
            with self.subTest(changes=changes),self.assertRaises(Rejected):Agent.safe(dict(SAFE,**changes))

    def test_discovery_requires_signature_not_api_claim(self):
        a=self.agent();a.provider=Mock();a.provider.projects.return_value=[dict(slug='test-app')]
        a.provider.latest.return_value=Release('test-app','Stable','2.0.0','notes','url',self.manifest['sha256'],self.manifest['size'],{})
        result=a.check();self.assertEqual(result['updates'][0]['status'],'No compatible release')

    def test_error_status_is_distinct(self):
        a=self.agent();a.provider=Mock();a.provider.projects.side_effect=ProviderError('Authentication failed')
        self.assertEqual(a.check()['status'],'Authentication failed')

    @unittest.skipUnless(os.name=='posix','Unix symlink installation')
    def test_real_bundle_install_and_health_then_success(self):
        a=self.agent();self.previous(a);ident=self.imported(a)
        plan=a.prepare(ident,1000,SAFE);result=a.install(plan['approval'],1000,SAFE,nullcontext)
        self.assertEqual(result['state'],'Completed');self.assertTrue(result['document']['health']['passed'])
        self.assertEqual((a.engine.root/'test-app/current/app.txt').read_text(),'good')
        self.assertEqual(result['document']['dataRecoveryPoint']['id'],'test-point')
        with self.assertRaises(Rejected):a.install(plan['approval'],1000,SAFE,nullcontext)

    @unittest.skipUnless(os.name=='posix','Unix symlinks')
    def test_backup_failure_blocks_activation_and_preserves_old_data(self):
        a=self.agent();old=self.previous(a);ident=self.imported(a)
        a.backup.request.side_effect=Rejected('No verified recovery point')
        plan=a.prepare(ident,1000,SAFE)
        with self.assertRaises(Rejected):a.install(plan['approval'],1000,SAFE,nullcontext)
        self.assertEqual((a.engine.root/'test-app/current').resolve(),old)
        self.assertEqual(a.history.get(ident)['state'],'Installation Failed')
        self.assertNotIn('dataRecoveryPoint',a.history.get(ident)['document'])

    @unittest.skipUnless(os.name=='posix','Unix symlinks')
    def test_backup_reference_durable_before_activation(self):
        a=self.agent();self.previous(a);ident=self.imported(a)
        original=a.engine.activate
        def activation(*args):
            second=History(a.directory/'history.sqlite')
            try:self.assertEqual(second.get(ident)['document']['dataRecoveryPoint']['id'],'test-point')
            finally:second.db.close()
            return original(*args)
        a.engine.activate=activation
        plan=a.prepare(ident,1000,SAFE);a.install(plan['approval'],1000,SAFE,nullcontext)
        a.backup.result.assert_called_with(ident,'healthy')

    @unittest.skipUnless(os.name=='posix','Unix symlink recovery')
    def test_failing_application_restores_previous_and_checks_health(self):
        calls=[]
        def health(command,timeout=30):
            calls.append(command)
            if (a.engine.root/'test-app/current/app.txt').read_text()=='good':raise Rejected('Deliberately failing test release')
            return ''
        a=self.agent(health);old=self.previous(a);ident=self.imported(a)
        plan=a.prepare(ident,1000,SAFE)
        with self.assertRaises(Rejected):a.install(plan['approval'],1000,SAFE,nullcontext)
        result=a.history.get(ident);self.assertEqual(result['state'],'Rolled Back')
        self.assertEqual((a.engine.root/'test-app/current').resolve(),old);self.assertEqual(len(calls),2)

    @unittest.skipUnless(os.name=='posix','Unix symlinks')
    def test_wrong_caller_and_expired_approval(self):
        a=self.agent();self.previous(a);ident=self.imported(a);plan=a.prepare(ident,1000,SAFE)
        with self.assertRaises(Rejected):a.install(plan['approval'],1001,SAFE,nullcontext)
        plan=a.prepare(ident,1000,SAFE);a.plans[plan['approval']]['expires']=0
        with self.assertRaises(Rejected):a.install(plan['approval'],1000,SAFE,nullcontext)

    @unittest.skipUnless(os.name=='posix','Debian preflight comparator')
    def test_archive_traversal_and_links(self):
        for name,kind in (('../escape',None),('/escape',None),('link',tarfile.SYMTYPE),('link',tarfile.LNKTYPE),('device',tarfile.CHRTYPE)):
            with self.subTest(name=name,kind=kind):
                self.path=self.bundle('bad',name,kind);self.manifest.update(size=self.path.stat().st_size,sha256=hashlib.sha256(self.path.read_bytes()).hexdigest())
                a=self.agent()
                with self.assertRaises(Rejected):a.engine.prepare(self.path,self.manifest,self.policy)
                self.assertFalse((self.root/'escape').exists())

    def test_local_policy_and_health_required(self):
        a=self.agent()
        for policy in (dict(self.policy,critical=True),dict(self.policy,package='other'),dict(self.policy,health=[])):
            with self.assertRaises(Rejected):a.engine.component(self.manifest,policy)

    def test_offline_does_not_bypass_signature(self):
        a=self.agent();bad=self.envelope();bad['key_id']='unknown'
        with self.assertRaises(Rejected):a.import_offline('test-app','Stable',bad,self.path)


if __name__=='__main__':unittest.main()
