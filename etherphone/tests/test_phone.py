from pathlib import Path
import json,os,sqlite3,sys,tempfile,unittest
from types import SimpleNamespace
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from core import Contacts,History,Manager,PhoneError,number,diagnostic
from provider import ModemManagerProvider,ROOT,sim_is_ready

class PhoneTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.root=Path(self.tmp.name)
        self.contacts=Contacts(self.root/'contacts/data.sqlite')
        self.history=History(self.root/'phone/history.sqlite')
        self.now=1000.;self.manager=Manager(self.history,self.contacts,lambda:self.now)
    def tearDown(self):
        self.contacts.db.close();self.history.db.close();self.tmp.cleanup()
    def observe(self,state,direction=2,reason=0,key='call'):
        self.manager.observe(key,{'State':state,'StateReason':reason,'Direction':direction,'Number':'+441234567890'})
    def test_numbers_and_emergency_preservation(self):
        self.assertEqual(number('+44 (123) 456-7890'),'+441234567890')
        self.assertEqual(number('999'),'999');self.assertEqual(number('112'),'112')
        for value in ('+44;shutdown','++123','１２３','123\n456','*#06#','tel:123','1'*16,''):
            with self.assertRaises(PhoneError):number(value)
    def test_secondary_sim_locks_do_not_block_an_enabled_sim(self):
        for lock in (1,3,5):self.assertTrue(sim_is_ready('/SIM/0',lock,8))
        for lock in (0,2,4,6,7):self.assertFalse(sim_is_ready('/SIM/0',lock,8))
        self.assertFalse(sim_is_ready('/',1,8))
        self.assertFalse(sim_is_ready('/SIM/0',3,3))
    def test_preflight_emergency_bypasses_sim_and_registration_only(self):
        for n in ('112','999'):
            self.assertEqual(self.manager.preflight(n,{'voice':True}),n)
            with self.assertRaises(PhoneError):self.manager.preflight(n,{'voice':False})
        for status in ({'voice':True},{'voice':True,'simReady':True},{'voice':True,'simReady':True,'registered':True,'emergencyOnly':True}):
            with self.assertRaises(PhoneError):self.manager.preflight('+441234567890',status)
    def test_submission_never_sets_active_or_ended(self):
        self.observe(3,1);self.manager.request('call','answer')
        self.assertEqual(self.manager.calls['call'].state,'Incoming')
        self.assertEqual(self.history.list(),[])
    def test_ambiguous_start_never_deletes_or_retries_a_possible_call(self):
        calls=[]
        class Ambiguous(Exception):pass
        class Api:
            def CreateCall(self,properties,timeout):calls.append('CreateCall');return ROOT+'/Call/9'
            def Start(self,timeout):calls.append('Start');raise Ambiguous()
            def DeleteCall(self,*args,**kwargs):calls.append('DeleteCall')
        provider=ModemManagerProvider.__new__(ModemManagerProvider)
        provider.selected=ROOT+'/Modem/0';provider.known=set()
        provider.dbus=SimpleNamespace(String=str,Dictionary=lambda value,signature:value)
        provider.interface=lambda *args:Api()
        with self.assertRaises(Ambiguous):provider.dial('+441234567890')
        self.assertEqual(calls,['CreateCall','Start'])
        self.assertIn(ROOT+'/Call/9',provider.known)
        self.observe(4,1);self.manager.request('call','end')
        self.assertEqual(self.manager.calls['call'].state,'Active')
        self.assertEqual(self.history.list(),[])
    def test_duration_counts_only_observed_active_segments(self):
        self.observe(1);self.now+=5;self.observe(2);self.now+=10;self.observe(4)
        self.now+=20;self.observe(5);self.now+=100;self.observe(4);self.now+=7;self.observe(7,reason=4)
        row=self.history.list()[0];self.assertEqual(row['duration'],27)
        self.assertEqual(row['result'],'Outgoing')
        self.observe(7);self.assertEqual(len(self.history.list()),1)
    def test_incoming_notification_once_and_missed_only_after_terminal(self):
        self.observe(3,1);self.assertEqual(len(self.manager.events),1);self.manager.events=[]
        self.observe(3,1);self.assertEqual(self.manager.events,[])
        self.observe(7,1,3);self.assertEqual(self.history.list()[0]['result'],'Missed')
        self.assertEqual(self.manager.events,[('Missed','call')])
    def test_rejected_call_distinct_from_missed(self):
        self.observe(3,1);self.manager.request('call','decline');self.observe(7,1,3)
        self.assertEqual(self.history.list()[0]['result'],'Rejected')
        self.assertFalse(any(e[0]=='Missed' for e in self.manager.events))
    def test_backend_loss_is_uncertain_never_missed_or_successful(self):
        self.observe(3,1);self.manager.lost(['call'])
        self.assertEqual(self.manager.calls['call'].state,'Uncertain')
        self.assertEqual(self.history.list()[0]['result'],'Uncertain')
        self.assertFalse(any(e[0]=='Missed' for e in self.manager.events))
        self.observe(4,1);self.assertEqual(self.manager.calls['call'].state,'Uncertain')
    def test_failure_and_stale_event(self):
        self.observe(1);self.now+=5;self.observe(7,reason=7)
        self.assertEqual(self.history.list()[0]['result'],'Failed')
        self.manager.observe('call',{'State':4},stamp=900)
        self.assertEqual(self.manager.calls['call'].state,'Ended')
    def test_dtmf_and_multiple_call_gates(self):
        self.observe(2)
        with self.assertRaises(PhoneError):self.manager.request('call','dtmf')
        with self.assertRaises(PhoneError):self.manager.preflight('+441234567890',{'voice':True,'simReady':True,'registered':True})
        self.observe(4);self.manager.request('call','dtmf')
    def test_contacts_multiple_numbers_persistence_lookup_and_search(self):
        cid=self.contacts.save({'name':'Ada <script>', 'numbers':['+441234567890','+48123456789'],'emails':['ada@example.test'],'notes':'hello','favourite':True,'photo':'file:///photo.png'})
        self.assertEqual(self.contacts.lookup('+48123456789')['id'],cid)
        self.assertEqual(len(self.contacts.list('hello')),1)
        self.contacts.db.close();self.contacts=Contacts(self.root/'contacts/data.sqlite')
        self.assertEqual(len(self.contacts.list()[0]['numbers']),2)
        self.contacts.remove(cid);self.assertEqual(self.contacts.lookup('+48123456789'),{})
    def test_contact_conflict_rolls_back_entire_edit(self):
        a=self.contacts.save({'name':'A','numbers':['1111']});self.contacts.save({'name':'B','numbers':['2222']})
        with self.assertRaises(PhoneError):self.contacts.save({'id':a,'name':'Broken','numbers':['2222']})
        self.assertEqual(self.contacts.lookup('1111')['name'],'A')
        self.assertEqual(self.contacts.lookup('2222')['name'],'B')
    def test_vcard_utf8_folding_escape_roundtrip(self):
        self.contacts.save({'name':'Éther; '+('界'*40),'numbers':['+441234567890'],'emails':['a@example.test'],'notes':'one\ntwo;three, four\\five','favourite':True})
        text=self.contacts.export_vcard()
        self.assertTrue(all(len(line.encode())<=75 for line in text.splitlines()))
        self.contacts.remove(self.contacts.list()[0]['id'])
        self.assertEqual(self.contacts.import_vcard(text),1)
        self.assertEqual(self.contacts.list()[0]['notes'],'one\ntwo;three, four\\five')
        self.assertEqual(self.contacts.list()[0]['favourite'],1)
    def test_vcard_import_atomic_and_conflicts(self):
        text='BEGIN:VCARD\nFN:A\nTEL:1234\nEND:VCARD\nBEGIN:VCARD\nFN:B\nTEL:invalid\nEND:VCARD'
        with self.assertRaises(PhoneError):self.contacts.import_vcard(text)
        self.assertEqual(self.contacts.list(),[])
        self.contacts.save({'name':'A','numbers':['1234']})
        with self.assertRaises(PhoneError):self.contacts.import_vcard('BEGIN:VCARD\nFN:B\nTEL:1234\nEND:VCARD')
        self.assertEqual(self.contacts.lookup('1234')['name'],'A')
    def test_private_backup_no_overwrite(self):
        self.contacts.save({'name':'A','numbers':['1234']})
        path=self.root/'backup.sqlite';self.contacts.backup(path)
        with self.assertRaises(FileExistsError):self.contacts.backup(path)
        db=sqlite3.connect(path);self.assertEqual(db.execute('SELECT count(*) FROM people').fetchone()[0],1);db.close()
        if os.name!='nt':
            self.assertEqual(path.stat().st_mode&0o777,0o600)
            self.assertEqual((self.root/'contacts').stat().st_mode&0o777,0o700)
    def test_redacted_diagnostic_allowlist(self):
        text=json.dumps(diagnostic({'modem':True,'imei':'private','number':'+441234567890'},{'operational':False,'imsi':'secret'}))
        for value in ('private','secret','+441234567890','imei','imsi'):self.assertNotIn(value,text)
        self.assertIn('realCallVerified',text)
    def test_transfer_is_not_failed(self):
        self.observe(4);self.now+=3;self.observe(7,reason=8)
        self.assertEqual(self.history.list()[0]['result'],'Outgoing')
    def test_restart_reattaches_call_identity_and_does_not_invent_downtime(self):
        self.observe(4);self.now+=5;self.observe(4)
        original=self.manager.calls['call'].id
        self.manager=Manager(self.history,self.contacts,lambda:self.now)
        self.now+=100;self.observe(4)
        self.assertEqual(self.manager.calls['call'].id,original)
        self.now+=3;self.observe(7,reason=4)
        self.assertEqual(self.history.list()[0]['duration'],8)
        self.assertFalse(self.manager.calls['call'].timing_complete)
    def test_restart_missing_call_becomes_uncertain_without_duplicate_history(self):
        self.observe(3,1)
        self.manager=Manager(self.history,self.contacts,lambda:self.now)
        self.manager.lost(['call'])
        self.assertEqual(self.history.list()[0]['result'],'Uncertain')
        self.assertEqual(self.history.db.execute('SELECT count(*) FROM live').fetchone()[0],0)
    def test_contact_and_history_reference_actual_events(self):
        cid=self.contacts.save({'name':'Ada','numbers':['+441234567890']})
        self.observe(3,1);self.observe(4,1);self.now+=3;self.observe(7,1,3)
        row=self.history.list()[0];self.assertEqual(row['contact'],cid);self.assertEqual(row['result'],'Incoming')
        self.assertEqual(self.contacts.list()[0]['recent'],1003)
        self.history.remove(row['id']);self.assertEqual(self.history.list(),[])
if __name__=='__main__':unittest.main()
