import datetime as dt
import json
from pathlib import Path
import sys
import tempfile
import unittest
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from core import Engine, Invalid, presentation


class CoreTests(unittest.TestCase):
    def setUp(self):
        self.folder = tempfile.TemporaryDirectory()
        self.path = Path(self.folder.name)/'private/history.sqlite'
        self.now = 1780000000.
        self.engine = Engine(self.path, lambda: self.now)
        self.engine.locked = False

    def tearDown(self):
        self.engine.db.close(); self.folder.cleanup()

    def send(self, **kwargs):
        values = dict(owner=':1.1', app='verified-app', name='Display App', replaces=0, icon='mail-unread',
                      title='Title', body='A private message', actions=['default', 'Open'], hints={}, timeout=0)
        values.update(kwargs)
        return self.engine.notify(**values)

    def test_legacy_power_presentation_and_privacy(self):
        ident, _ = self.send(app='etherpower', name='EtherPower', title='EtherPower',
                            body='BatteryEmergency: {"capacity": 2.0, "level": "emergency"}',
                            hints={'category': 'system.power.BatteryEmergency'})
        card = self.engine.snapshot()['cards'][0]
        self.assertEqual(card['title'], 'Charge your phone now')
        self.assertIn('2% battery remaining', card['body'])
        self.assertNotIn('{', card['body'])
        self.assertIn('{', self.engine.rows[ident]['body'])
        self.engine.locked = True
        self.assertEqual(self.engine.snapshot()['cards'][0]['body'], '')

    def test_structured_and_plain_notification_bodies(self):
        row = dict(appId='test', category='', title='Status', body='{"online":true,"nested":{"count":0}}')
        title, body = presentation(row)
        self.assertEqual(title, 'Status')
        self.assertIn('Online: Yes', body)
        self.assertIn('Count: 0', body)
        row['body'] = 'Please keep {this text} unchanged.'
        self.assertEqual(presentation(row)[1], row['body'])

    def test_thermal_presentation_preserves_unknown_measurements(self):
        row = dict(appId='etherpower', category='system.power.ThermalWarning', title='EtherPower',
                   body='ThermalWarning: {"cpuC": 85.5, "batteryC": null}')
        title, body = presentation(row)
        self.assertEqual(title, 'Device temperature warning')
        self.assertIn('CPU: 85.5 °C', body)
        self.assertNotIn('Battery:', body)

    def test_ownership_replacement_close_and_actions(self):
        ident, _ = self.send()
        with self.assertRaises(Invalid): self.send(owner=':1.2', replaces=ident)
        with self.assertRaises(Invalid): self.engine.close(ident, owner=':1.2')
        same, _ = self.send(replaces=ident, title='Updated')
        self.assertEqual(same, ident)
        with self.assertRaises(Invalid): self.engine.invoke(ident, 'rm-command')
        self.engine.invoke(ident, 'default')
        self.assertEqual(self.engine.events, [('action', ':1.1', ident, 'default'), ('closed', ':1.1', ident, 2)])
        with self.assertRaises(Invalid): self.engine.invoke(ident, 'default')

    def test_history_survives_restart_ids_and_sensitive_redaction(self):
        ident, _ = self.send(body='NEVER-STORE-THIS', title='SECRET-TITLE')
        second, _ = self.send(body='Public', hints={'x-ether-privacy':'public'})
        self.engine.db.close()
        self.assertNotIn(b'NEVER-STORE-THIS', self.path.read_bytes())
        self.assertNotIn(b'SECRET-TITLE', self.path.read_bytes())
        self.engine = Engine(self.path, lambda: self.now)
        self.assertEqual(self.engine.rows[ident]['body'], '')
        self.assertEqual(self.engine.rows[second]['body'], 'Public')
        self.assertEqual(self.engine.rows[second]['actions'], [])
        self.assertEqual(self.engine.rows[second]['owner'], '')
        self.assertGreater(self.send()[0], second)

    def test_transient_and_secret_never_persist_and_replacement_erases(self):
        ident, _ = self.send(hints={'x-ether-privacy':'public'})
        self.send(replaces=ident, hints={'transient':True})
        self.assertFalse(self.engine.db.execute('SELECT id FROM records').fetchall())
        self.send(hints={'x-ether-privacy':'secret'})
        self.assertFalse(self.engine.db.execute('SELECT id FROM records').fetchall())

    def test_privacy_and_locked_actions(self):
        ident, _ = self.send()
        self.engine.locked = True
        self.assertEqual(self.engine.snapshot()['cards'][0]['body'], '')
        self.assertFalse(self.engine.snapshot()['cards'][0]['actions'])
        with self.assertRaises(Invalid): self.engine.invoke(ident, 'default')
        self.engine.configure({'lockPrivacy':'count'})
        self.assertFalse(self.engine.snapshot()['cards'])
        self.assertEqual(self.engine.snapshot()['unread'], 1)
        self.engine.configure({'lockPrivacy':'hidden'})
        self.assertEqual(self.engine.snapshot()['unread'], 0)
        self.engine.configure({'lockPrivacy':'sensitive','apps':{'verified-app':{'lockPrivacy':'hidden'}}})
        self.assertEqual(self.engine.snapshot()['unread'], 0)
        self.engine.configure({'apps':{}})
        self.send(hints={'x-ether-privacy':'secret'})
        self.assertEqual(self.engine.snapshot()['unread'], 1)  # no secret existence leak

    def test_dnd_untrusted_critical_and_authorized_exceptions(self):
        self.engine.configure({'dnd':'priority','manualDnd':True})
        ident, delivery = self.send(hints={'urgency':2,'category':'alarm'})
        self.assertEqual(self.engine.rows[ident]['priority'], 2)
        self.assertFalse(delivery['banner'])
        self.assertEqual(delivery['sound'], 'silent')
        self.engine.configure({'apps':{'verified-app':{'dndException':True}}})
        self.assertTrue(self.send()[1]['banner'])
        self.engine.configure({'dnd':'silence'})
        self.assertFalse(self.send()[1]['banner'])
        self.engine.configure({'dnd':'alarms'})
        self.assertFalse(self.send(hints={'category':'alarm'})[1]['banner'])
        self.assertTrue(self.send(hints={'category':'alarm'}, trusted=True)[1]['banner'])

    def test_schedule_crosses_midnight_and_manual_override(self):
        self.engine.configure({'schedule':dict(enabled=True,start=1320,end=420,days=[0]),'dnd':'priority'})
        self.assertEqual(self.engine.dnd(dt.datetime(2026,10,19,23)), 'priority')
        self.assertEqual(self.engine.dnd(dt.datetime(2026,10,20,6)), 'priority')
        self.assertEqual(self.engine.dnd(dt.datetime(2026,10,20,23)), 'off')
        self.engine.configure({'manualDnd':True,'dnd':'off'})
        self.assertEqual(self.engine.dnd(dt.datetime(2026,10,19,23)), 'off')

    def test_expiry_reason_and_bulk_clear_respects_resident(self):
        ident, _ = self.send(timeout=1000)
        persistent, _ = self.send(hints={'resident':True})
        self.now += 2; self.engine.expire()
        self.assertEqual(self.engine.events[0], ('closed', ':1.1', ident, 1))
        self.engine.clear()
        self.assertTrue(self.engine.rows[persistent]['active'])
        self.engine.close(persistent, 3, ':1.1')
        self.assertEqual(self.engine.events[-1][-1], 3)

    def test_disconnect_and_dedup_and_group_counters(self):
        ident, _ = self.send(hints={'x-ether-thread':'conversation','x-ether-event-id':'event'})
        self.engine.owner_lost(':1.1')
        with self.assertRaises(Invalid): self.engine.invoke(ident, 'default')
        self.assertEqual(self.send(owner=':1.3', hints={'x-ether-event-id':'event'}), (ident,None))
        self.send(hints={'x-ether-thread':'conversation'})
        self.assertEqual(len(set(c['groupKey'] for c in self.engine.snapshot()['cards'])),1)
        self.engine.mark_read(ident)
        self.assertEqual(self.engine.snapshot()['unread'],1)

    def test_calls_sleep_silent_and_disabled(self):
        self.engine.call_active = True
        self.assertEqual(self.send()[1]['sound'], 'silent')
        self.engine.call_active = False; self.engine.sleeping = True
        self.assertFalse(self.send()[1]['banner'])
        self.engine.sleeping = False
        self.engine.configure({'silent':True})
        self.assertEqual(self.send()[1]['sound'], 'silent')
        self.engine.configure({'enabled':False})
        ident,delivery=self.send()
        self.assertTrue(delivery['suppressed'])
        self.assertFalse(self.engine.rows[ident]['active'])
        self.assertFalse(any(c['active'] for c in self.engine.snapshot()['cards']))

    def test_input_limits_sanitization_and_rate(self):
        ident,_=self.send(title='<b>Hello</b>\u202e', body='&lt;script&gt;x&lt;/script&gt;')
        self.assertEqual(self.engine.rows[ident]['title'], 'Hello')
        with self.assertRaises(Invalid): self.send(actions=['default'])
        with self.assertRaises(Invalid): self.send(actions=['a','A','a','Duplicate'])
        with self.assertRaises(Invalid): self.send(body='X'*33000)
        with self.assertRaises(Invalid): self.send(timeout=-2)
        for _ in range(19): self.send()
        with self.assertRaises(Invalid): self.send()
        self.now += 11; self.send()

    def test_retention_bound_export_and_restore(self):
        self.engine.MAX_ROWS = 4
        for _ in range(8): self.send()
        self.assertEqual(len(self.engine.rows),4)
        self.assertEqual(self.engine.db.execute('SELECT count(*) FROM records').fetchone()[0],4)
        self.assertNotIn('private',json.dumps(self.engine.export()))
        ident = max(self.engine.rows)
        self.engine.close(ident)
        self.engine.restore(ident)
        self.assertFalse(self.engine.rows[ident]['actions'])
        self.now += 8*86400; self.engine.prune()
        self.assertFalse(self.engine.rows)
        self.assertFalse(self.engine.db.execute('SELECT * FROM records').fetchall())

    def test_invalid_settings_are_atomic(self):
        before=json.dumps(self.engine.config)
        for data in ({'enabled':'yes'},{'retentionDays':0},{'apps':{'a':{'sound':'/bin/sh'}}},{'schedule':{}},{'unknown':True}):
            with self.assertRaises(Invalid): self.engine.configure(data)
        self.assertEqual(json.dumps(self.engine.config),before)


if __name__ == '__main__': unittest.main()
