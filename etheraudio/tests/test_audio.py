from pathlib import Path
import copy
import json
import sys
import tempfile
import unittest
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from core import Audio,AudioError,DEFAULTS,is_monitor,volume


def endpoint(index,name,bus='platform'):
    return dict(index=index,name=name,description=name,volume={'mono':{'value':32768}},mute=False,state='IDLE',properties={'device.bus':bus})


class Backend:
    def __init__(self):
        self.data={'sinks':[endpoint(1,'Speaker')],'sources':[endpoint(2,'HandsetMic'),dict(endpoint(3,'Speaker.monitor'),monitor_of_sink=1)],
                   'sink-inputs':[dict(endpoint(4,'media'),sink=1,client=10,corked=False)],'source-outputs':[],
                   'default-sink':'Speaker','default-source':'HandsetMic','cards':[]}
        self.calls=[];self.reject=None
    def snapshot(self):return copy.deepcopy(self.data)
    def run(self,*args):
        self.calls.append(args)
        if self.reject and self.reject(args):raise AudioError('Injected backend rejection')
        action=str(args[0])
        if action.startswith('get-default-'):return self.data[action[4:]]
        if action.startswith('set-default-'):
            self.data[action[4:]]=args[1];return ''
        if action=='move-sink-input':
            row=next(r for r in self.data['sink-inputs'] if r['index']==args[1])
            row['sink']=next(r['index'] for r in self.data['sinks'] if r['name']==args[2] or r['index']==args[2]);return ''
        if action=='set-card-profile':
            next(c for c in self.data['cards'] if c['name']==args[1])['active_profile']=args[2];return ''
        for kind in ('sink-input','source-output','sink','source'):
            key={'sink-input':'sink-inputs','source-output':'source-outputs','sink':'sinks','source':'sources'}[kind]
            if action in ('set-'+kind+'-volume','set-'+kind+'-mute'):
                row=next(r for r in self.data[key] if r['index']==args[1])
                if action.endswith('-volume'):row['volume']={'mono':{'value':round(int(args[2][:-1])*65536/100)}}
                else:row['mute']=args[2]=='1'
                return ''
        raise AssertionError(args)


class AudioTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.backend=Backend();self.audio=Audio(self.temp.name,self.backend)
        self.audio.refresh();self.backend.calls.clear()
    def tearDown(self):self.temp.cleanup()
    def test_existing_stack_and_levels_are_preserved_on_start(self):
        self.assertEqual(volume(self.audio.state['sink-inputs'][0]),50)
        self.assertEqual(len(self.audio.state['sources']),1)
        self.assertFalse(self.audio.state['callAudio']['verified'])
    def test_volume_and_mute_verify_effective_values(self):
        self.audio.set_volume('sink',1,35);self.assertEqual(volume(self.audio.find('sink',1)),35)
        self.audio.mute('source',2,True);self.assertTrue(self.audio.find('source',2)['mute'])
    def test_invalid_values_never_reach_backend(self):
        for v in (-1,101,True,50.5,'50'):
            with self.assertRaises(AudioError):self.audio.set_volume('sink',1,v)
        self.assertEqual(self.backend.calls,[])
    def test_readback_failure_is_reported(self):
        self.backend.run=lambda *args:''
        with self.assertRaisesRegex(AudioError,'readback'):self.audio.set_volume('sink',1,12)
    def test_route_moves_existing_playback_and_persists_preference(self):
        self.backend.data['sinks'].append(endpoint(5,'USB','usb'));self.audio.state=self.backend.snapshot()
        self.audio.select('sink','USB')
        self.assertEqual(self.backend.data['default-sink'],'USB');self.assertEqual(self.backend.data['sink-inputs'][0]['sink'],5)
        self.assertEqual(Audio(self.temp.name,self.backend).config['preferredOutput'],'USB')
    def test_failed_route_rolls_back(self):
        self.backend.data['sinks'].append(endpoint(5,'USB','usb'));self.audio.state=self.backend.snapshot()
        self.backend.reject=lambda a:a[0]=='move-sink-input' and a[2]=='USB'
        with self.assertRaisesRegex(AudioError,'rollback completed'):self.audio.select('sink','USB')
        self.assertEqual(self.backend.data['default-sink'],'Speaker');self.assertEqual(self.backend.data['sink-inputs'][0]['sink'],1)
    def test_hotplug_routes_and_disconnect_restores_speaker(self):
        self.backend.data['sinks'].append(endpoint(5,'USB','usb'));self.audio.refresh()
        self.assertEqual(self.backend.data['default-sink'],'USB')
        self.backend.data['sinks']=[self.backend.data['sinks'][0]];self.audio.refresh()
        self.assertEqual(self.backend.data['default-sink'],'Speaker')
    def test_volume_events_do_not_reroute(self):
        self.audio.refresh();self.assertFalse(any(a[0].startswith('set-default') for a in self.backend.calls))
    def test_manual_route_survives_bluetooth_arrival(self):
        self.audio.select('sink','Speaker');self.backend.calls.clear()
        self.backend.data['sinks'].append(endpoint(5,'bluez_output.test','bluetooth'));self.audio.refresh()
        self.assertEqual(self.backend.data['default-sink'],'Speaker')
    def test_call_and_live_capture_protect_routes(self):
        token=self.audio.request_focus(':1.5','call')
        with self.assertRaisesRegex(AudioError,'call'):self.audio.select('sink','Speaker')
        self.audio.release_focus(':1.5',token)
        self.audio.state['source-outputs']=[{'index':9}]
        with self.assertRaisesRegex(AudioError,'recording'):self.audio.select('source','HandsetMic')
    def test_monitor_never_selected_as_microphone(self):
        self.audio.state=self.backend.snapshot()
        with self.assertRaisesRegex(AudioError,'monitor'):self.audio.select('source','Speaker.monitor')
    def test_focus_priority_ownership_and_crash_cleanup(self):
        media=self.audio.request_focus(':1.1','media');call=self.audio.request_focus(':1.2','call')
        self.assertEqual(volume(self.backend.data['sink-inputs'][0]),20)
        with self.assertRaises(AudioError):self.audio.release_focus(':1.1',call)
        self.audio.release_focus(':1.2')
        self.assertEqual(volume(self.backend.data['sink-inputs'][0]),50)
        self.audio.release_focus(':1.1',media);self.assertEqual(self.audio.focus,{})
    def test_user_volume_edit_is_not_overwritten_after_focus(self):
        self.audio.request_focus(':1.1','alarm');self.audio.set_volume('sink-input',4,37)
        self.audio.release_focus(':1.1');self.assertEqual(volume(self.backend.data['sink-inputs'][0]),37)
    def test_external_edit_is_respected_after_focus(self):
        self.audio.request_focus(':1.1','alarm')
        self.backend.run('set-sink-input-volume',4,'33%');self.audio.release_focus(':1.1')
        self.assertEqual(volume(self.backend.data['sink-inputs'][0]),33)
    def test_recycled_stream_id_is_not_restored(self):
        self.audio.request_focus(':1.1','alarm');self.backend.data['sink-inputs'][0]['client']=999
        self.audio.release_focus(':1.1');self.assertEqual(volume(self.backend.data['sink-inputs'][0]),20)
    def test_categories_are_real_software_stream_controls(self):
        self.audio.set_category('media',45);self.assertEqual(volume(self.backend.data['sink-inputs'][0]),45)
        stream=dict(endpoint(8,'alarm'),sink=1,client=30,properties={'media.role':'alarm'})
        self.backend.data['sink-inputs'].append(stream);self.audio.refresh()
        self.assertEqual(volume(self.backend.data['sink-inputs'][1]),70)
    def test_policy_validation_and_persistence(self):
        self.audio.configure({'automatic':False,'microphonePolicy':'deny'})
        self.assertFalse(Audio(self.temp.name,self.backend).config['automatic'])
        for change in ({'shell':'rm'},{'categories':{}},{'automatic':1},{'microphonePolicy':'always-allow'}):
            with self.assertRaises(AudioError):self.audio.configure(change)
    def test_recording_activity_and_no_automatic_capture(self):
        self.backend.data['source-outputs']=[dict(index=9,corked=False,properties={'application.name':'Recorder'})]
        state=self.audio.refresh();self.assertTrue(state['recording']);self.assertEqual(state['recordingStreams'][0]['application'],'Recorder')
        self.assertIn('no sandbox isolation',state['privacy'])
    def test_diagnostics_bounded_and_without_audio_data(self):
        for _ in range(105):self.audio.diagnostic_result('playback','heard')
        rows=json.loads((Path(self.temp.name)/'diagnostics.json').read_text());self.assertEqual(len(rows),100)
        self.assertEqual(set(rows[0]),{'timestamp','kind','result','output','input'})
    def test_card_profiles_require_available_external_backend(self):
        card=dict(name='headset',properties={'device.bus':'bluetooth'},profiles={'a2dp-sink':{'available':'yes'},'headset-head-unit':{'available':'no'}},active_profile='off')
        self.backend.data['cards']=[card];self.audio.state=self.backend.snapshot()
        self.audio.set_card_profile('headset','a2dp-sink');self.assertEqual(card['active_profile'],'a2dp-sink')
        for profile in ('headset-head-unit','invented'):
            with self.assertRaises(AudioError):self.audio.set_card_profile('headset',profile)
        self.audio.request_focus(':1.5','call')
        with self.assertRaisesRegex(AudioError,'call'):self.audio.set_card_profile('headset','a2dp-sink')
    def test_internal_card_profiles_not_changed(self):
        self.audio.state['cards']=[dict(name='internal',properties={'device.bus':'platform'},profiles={'off':{}},active_profile='HiFi')]
        with self.assertRaises(AudioError):self.audio.set_card_profile('internal','off')
        self.assertEqual(self.backend.calls,[])
    def test_failed_focus_request_does_not_leave_an_orphan_lease(self):
        self.backend.data['sink-inputs'].append(dict(endpoint(8,'other'),sink=1,client=30))
        self.audio.state=self.backend.snapshot()
        self.backend.reject=lambda a:a[0]=='set-sink-input-volume' and a[1]==8
        with self.assertRaises(AudioError):self.audio.request_focus(':1.5','call')
        self.assertEqual(self.audio.focus,{})
        self.assertEqual(volume(self.backend.data['sink-inputs'][0]),50)


if __name__=='__main__':unittest.main()
