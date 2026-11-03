"""Bounded, reversible offline probe of the downstream VoiceMMode1 PCM.

No dial, recording, PCM samples, firmware, calibration or persistent audio changes.
Only the two OEM voice routing switches change; original values are restored.
"""
import json
import runpy
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
remote = runpy.run_path(str(ROOT / 'scripts/check-etherphone-device.py'))['remote']
REMOTE = r'''
import ctypes as C,json,pathlib,re,subprocess,time
import dbus
assert pathlib.Path('/etc/etherpocket/disk-identity').read_text().strip()=='GM1920-548cb338-mobian-sda21'
bus=dbus.SystemBus()
objects=dbus.Interface(bus.get_object('org.freedesktop.ModemManager1','/org/freedesktop/ModemManager1'),'org.freedesktop.DBus.ObjectManager').GetManagedObjects()
assert not any('org.freedesktop.ModemManager1.Call' in i and int(i['org.freedesktop.ModemManager1.Call']['State'])!=7 for i in objects.values()), 'Live call; refusing offline probe'
assert pathlib.Path('/sys/class/sound/card0/id').read_text().strip()=='sm8150tavilsndc'
assert 'VoiceMMode1' in pathlib.Path('/proc/asound/card0/pcm2p/info').read_text()
assert all(p.read_text().strip()=='closed' for p in pathlib.Path('/proc/asound/card0').glob('pcm*/sub*/status')), 'Audio in use'
names=['QUAT_MI2S_RX_Voice Mixer VoiceMMode1','VoiceMMode1_Tx Mixer SLIM_0_TX_MMode1']
def get(n):
 p=subprocess.run(['amixer','-c','0','cget','name='+n],capture_output=True,text=True,check=True,timeout=5)
 return re.search(r'^  : values=(.+)$',p.stdout,re.M).group(1)
def put(n,v):
 subprocess.run(['amixer','-q','-c','0','cset','name='+n,v],capture_output=True,check=True,timeout=5)
before={n:get(n) for n in names}
# This probe reuses only the already validated media backend configuration.
# Do not silently apply the route on a differently configured handset.
expected={'QUAT_MI2S_RX Channels':'1','QUAT_MI2S_RX Format':'1','QUAT_MI2S_RX SampleRate':'6','stereo Profile':'1','Tfa Mute':'0','AIF1_CAP Mixer SLIM TX0':'on','SLIM_0_TX Channels':'0','CDC_IF TX0 MUX':'2','ADC MUX0':'1','AMIC MUX0':'3','IIR0 INP0 MUX':'1','ADC3 Volume':'6','DEC0 Volume':'84'}
assert all(get(n)==v for n,v in expected.items()), 'Validated speaker/mic backend configuration differs'
started=str(int(time.time())-1)
a=C.CDLL('libasound.so.2')
a.snd_pcm_open.argtypes=[C.POINTER(C.c_void_p),C.c_char_p,C.c_int,C.c_int]
a.snd_pcm_set_params.argtypes=[C.c_void_p,C.c_int,C.c_int,C.c_uint,C.c_uint,C.c_int,C.c_uint]
a.snd_pcm_close.argtypes=[C.c_void_p]
a.snd_strerror.argtypes=[C.c_int];a.snd_strerror.restype=C.c_char_p
handles=[];result={'before':before,'operations':[]}
def checked(operation,rc):
 result['operations'].append({'operation':operation,'return':rc,'error':a.snd_strerror(rc).decode() if rc<0 else ''})
 if rc<0:raise RuntimeError(operation+': '+a.snd_strerror(rc).decode())
try:
 for n in names:put(n,'1,1')
 for stream in (0,1):
  h=C.c_void_p()
  checked('open '+str(stream),a.snd_pcm_open(C.byref(h),b'hw:0,2',stream,1))
  handles.append(h)
  # Driver: S16_LE, mono, 16kHz; 8192-byte buffer with 2048-byte periods.
  checked('configure/prepare '+str(stream),a.snd_pcm_set_params(h,2,3,1,16000,0,256000))
 result['prepared']={str(p):p.read_text() for p in pathlib.Path('/proc/asound/card0').glob('pcm2[cp]/sub0/status')}
 time.sleep(2)
except Exception as e:result['error']=str(e)
finally:
 for h in reversed(handles):result['operations'].append({'operation':'close','return':a.snd_pcm_close(h)})
 for n,v in reversed(list(before.items())):put(n,v)
result['after']={n:get(n) for n in names}
result['restored']=result['before']==result['after']
result['pcmAfter']={str(p):p.read_text() for p in pathlib.Path('/proc/asound/card0').glob('pcm2[cp]/sub0/status')}
p=subprocess.run(['journalctl','-k','--since','@'+started,'--no-pager','-g','voice|Voice|q6|apr|APR|CVP|CVS|MVM|calibration|tfa|TFA|SLIM|QUAT|asoc|ASoC'],capture_output=True,text=True,timeout=10)
result['kernel']=p.stdout[-24000:]
result['voiceCalibrationMissing']='No cal data for cal' in result['kernel']
result['twoWayAudioVerified']=False
result['note']='ALSA prepare returns success even when voc_start_voice_call fails; inspect DSP logs. An offline probe cannot verify call audio.'
print(json.dumps(result,indent=2))
'''

if __name__ == '__main__':
    result = json.loads(remote(REMOTE, timeout=65))
    (ROOT / 'evidence/etherphone-voice-pcm-probe-2026-10-21.json').write_text(json.dumps(result, indent=2)+'\n', encoding='utf-8')
    print(json.dumps(result, indent=2))
