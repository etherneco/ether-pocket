"""Read-only Linux IIO compatibility provider. Never enables buffers or drivers.

IIO ABI conversions apply to scaled values only. Poll rate is not hardware ODR.
Unknown board axes and vendor input protocols deliberately fail closed.
"""
import math
from pathlib import Path
import time

TYPES = {
 'accelerometer': ('accel', 'm/s²', 1., ('x','y','z')),
 'gyroscope': ('anglvel', 'rad/s', 1., ('x','y','z')),
 'magnetometer': ('magn', 'µT', 100., ('x','y','z')),
 'ambient_light': ('illuminance', 'lux', 1., ('',)),
 'proximity': ('proximity', None, 1., ('',)),
 'barometer': ('pressure', 'Pa', 1000., ('',)),
}
DERIVED = ('orientation','gravity','linear_acceleration','rotation_vector')

def read(path):
 try:return Path(path).read_text().strip()
 except OSError:return None

def finite(value):
 result=float(value)
 if not math.isfinite(result):raise ValueError('Non-finite measurement')
 return result

class Provider:
 """Provider contract: discover(), sample(id), close(); no automatic writes."""
 def discover(self):raise NotImplementedError
 def sample(self,ident):raise NotImplementedError
 def close(self):pass

class IIO(Provider):
 def __init__(self,root='/sys/bus/iio/devices'):
  self.root=Path(root);self.channels={}

 def discover(self):
  rows=[];self.channels.clear()
  for p in sorted(self.root.glob('iio:device*')):
   for kind,(prefix,unit,factor,axes) in TYPES.items():
    channels=[]
    for axis in axes:
     stem='in_'+prefix+('_'+axis if axis else '')
     raw=p/(stem+'_raw');processed=p/(stem+'_input')
     if not raw.exists() and not processed.exists():break
     scale=read(p/(stem+'_scale')) or read(p/('in_'+prefix+'_scale'))
     offset=read(p/(stem+'_offset')) or read(p/('in_'+prefix+'_offset')) or '0'
     channels.append((processed if processed.exists() else raw, processed.exists(),scale,offset))
    else:
     ident=p.name+':'+kind
     # Vector channels are not published until board coordinate mapping is validated.
     usable=unit is not None and len(axes)==1 and all(c[1] or c[2] is not None for c in channels)
     driver=p/'device/driver'
     if not driver.exists():driver=p.resolve().parent/'driver'
     rates=read(p/('in_'+prefix+'_sampling_frequency_available')) or read(p/'sampling_frequency_available')
     row=dict(id=ident,type=kind,physical=True,manufacturer=None,name=read(p/'name') or p.name,
      provider='linux-iio',driver=driver.resolve().name if driver.exists() else None,devicePath=str(p),
      units=unit,resolution=None,range=None,hardwareFrequency=read(p/('in_'+prefix+'_sampling_frequency')) or read(p/'sampling_frequency'),
      advertisedFrequencies=rates,verifiedFrequencies=[],calibration='Unknown; factory data unchanged',
      status='Not tested' if usable else 'Blocked',measurementAvailable=usable,verified=False,
      accuracy='Unknown',coordinateSystem='Unverified sensor axes' if len(axes)>1 else 'Scalar',
      reason='Read-only scaled IIO channel; physical response not verified' if usable else 'Board axis mapping, scale or proximity protocol requires validation',
      powerRequirements=None,lastError='')
     self.channels[ident]=(channels,factor,row);rows.append(row)
  return rows

 def sample(self,ident):
  channels,factor,row=self.channels[ident]
  if not row['measurementAvailable']:raise ValueError(row['reason'])
  start=time.monotonic_ns();raw=[];values=[]
  for path,processed,scale,offset in channels:
   value=finite(path.read_text());raw.append(value)
   values.append(finite((value if processed else (value+finite(offset))*finite(scale))*factor))
  end=time.monotonic_ns()
  return dict(sensorId=ident,values=values,raw=raw,units=row['units'],timestampNs=end,
   clock='CLOCK_MONOTONIC',timestampSource='host read completion; not hardware acquisition',readDurationNs=end-start,
   accuracy='Unknown',simulated=False,physicalResponseVerified=False)

class Discovery:
 def __init__(self,provider=None,system='/'):
  self.provider=provider or IIO();self.system=Path(system)
 def scan(self):
  rows=self.provider.discover();present={r['type'] for r in rows}
  ssc=(self.system/'dev/sensors').exists()
  inputs=[]
  for p in (self.system/'sys/class/input').glob('event*'):
   name=read(p/'device/name') or ''
   if name in ('STM VL53L1 proximity sensor','elliptic_ultrasound_proximity'):
    inputs.append({'node':'/dev/input/'+p.name,'name':name})
  for kind in TYPES:
   if kind in present:continue
   partial=kind=='proximity' and bool(inputs)
   rows.append(dict(id='unavailable:'+kind,type=kind,physical=True,physicalPresence='Vendor interface detected; part role unverified' if partial else 'Unknown',
    manufacturer=None,name=kind.replace('_',' ').title(),provider='vendor-unverified' if ssc or partial else None,
    driver='sensors-ssc (timer only)' if ssc else None,devicePath=None,units=TYPES[kind][1],resolution=None,range=None,
    hardwareFrequency=None,advertisedFrequencies=None,verifiedFrequencies=[],calibration='Unknown',powerRequirements=None,
    status='Partially supported' if partial else 'Blocked' if ssc and kind!='barometer' else 'Not tested',
    measurementAvailable=False,verified=False,accuracy='Unknown',lastError='',inputCandidates=inputs if kind=='proximity' else [],
    reason='No validated sample transport; SSC timer/input nodes do not prove real measurements'))
  for kind in DERIVED:
   rows.append(dict(id='derived:'+kind,type=kind,physical=False,status='Blocked',measurementAvailable=False,verified=False,
    reason='Deferred until real motion inputs, timestamps, calibration and board axes are validated',units=None,
    calibration='Unavailable',verifiedFrequencies=[],lastError=''))
  return rows
