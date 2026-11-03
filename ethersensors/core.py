"""Bounded subscription and permission policy, independent of D-Bus/hardware."""
import math
import secrets
import time

class Rejected(ValueError):pass

def rate(value):
 if isinstance(value,bool):raise Rejected('Rate must be numeric')
 try:value=float(value)
 except (TypeError,ValueError):raise Rejected('Rate must be numeric')
 if not math.isfinite(value) or not .2<=value<=10:raise Rejected('Managed polling supports 0.2–10 Hz only; high-frequency transport unavailable')
 return value

class Core:
 def __init__(self,discovery,clock=time.monotonic):
  self.discovery=discovery;self.clock=clock;self.rows={r['id']:r for r in discovery.scan()}
  self.grants={};self.subscriptions={};self.latest={};self.due={};self.suspended=False;self.saver=False
  self.config={'rotationLock':True,'autoRotate':False,'motionControl':False}

 def grant(self,owner,hz=2,background=False):
  self.grants[owner]={'rate':rate(hz),'background':bool(background),'expires':self.clock()+300}

 def authorize(self,owner,hz,background=False):
  g=self.grants.get(owner,{})
  if self.clock()>=g.get('expires',0) or hz>g.get('rate',0) or background and not g.get('background'):
   raise Rejected('Session permission missing or expired; request approval in Sensors & Motion')
  if self.suspended:raise Rejected('Suspended')

 def start(self,owner,ident,hz=2,background=False):
  hz=rate(hz);self.authorize(owner,hz,background)
  row=self.rows.get(ident)
  if not row or not row['measurementAvailable']:raise Rejected('Sensor has no validated compatible measurement interface')
  if len(self.subscriptions)>=32 or sum(s['owner']==owner for s in self.subscriptions.values())>=8:raise Rejected('Subscription limit')
  token=secrets.token_hex(16)
  self.subscriptions[token]=dict(owner=owner,sensor=ident,rate=hz,background=bool(background),expires=self.clock()+300,lastRead=-math.inf)
  return token

 def owned(self,owner,token):
  s=self.subscriptions.get(token)
  if not s or s['owner']!=owner:raise Rejected('Unknown subscription')
  if self.clock()>=s['expires']:
   self.stop(owner,token);raise Rejected('Subscription expired')
  self.authorize(owner,s['rate'],s['background']);return s

 def set_rate(self,owner,token,hz):
  hz=rate(hz);s=self.owned(owner,token);self.authorize(owner,hz,s['background']);s['rate']=hz

 def stop(self,owner,token):
  s=self.subscriptions.get(token)
  if not s or s['owner']!=owner:raise Rejected('Unknown subscription')
  del self.subscriptions[token];self.cleanup()

 def release(self,owner):
  self.grants.pop(owner,None)
  self.subscriptions={k:s for k,s in self.subscriptions.items() if s['owner']!=owner};self.cleanup()

 def cleanup(self):
  active={s['sensor'] for s in self.subscriptions.values()}
  self.latest={k:v for k,v in self.latest.items() if k in active};self.due={k:v for k,v in self.due.items() if k in active}
  if not active:self.discovery.provider.close()

 def reset(self):
  self.subscriptions.clear();self.grants.clear();self.latest.clear();self.due.clear();self.discovery.provider.close()

 def effective_rate(self,ident):
  requested=max((s['rate'] for s in self.subscriptions.values() if s['sensor']==ident),default=0)
  return min(requested,1) if self.saver else requested

 def tick(self):
  now=self.clock()
  for token,s in list(self.subscriptions.items()):
   try:self.owned(s['owner'],token)
   except Rejected:self.subscriptions.pop(token,None)
  self.cleanup()
  if self.suspended:return
  for ident in {s['sensor'] for s in self.subscriptions.values()}:
   hz=self.effective_rate(ident)
   if now<self.due.get(ident,0):continue
   self.due[ident]=now+1/hz
   try:
    sample=self.discovery.provider.sample(ident)
    self.latest[ident]=(now,sample);self.rows[ident]['lastError']=''
   except (OSError,ValueError,KeyError) as e:
    self.latest.pop(ident,None);self.rows[ident]['lastError']=str(e)[:200]

 def read(self,owner,token):
  s=self.owned(owner,token);now=self.clock();hz=self.effective_rate(s['sensor'])
  if now-s['lastRead']<1/hz:raise Rejected('Read rate limited')
  s['lastRead']=now
  cached=self.latest.get(s['sensor'])
  if not cached or now-cached[0]>max(2,2/hz):raise Rejected('No fresh measurement')
  return dict(cached[1],ageSeconds=now-cached[0],pollRateHz=hz,hardwareRateHz=None)

 def configure(self,changes):
  if not isinstance(changes,dict) or set(changes)-set(self.config):raise Rejected('Unknown setting')
  if any(type(v) is not bool for v in changes.values()):raise Rejected('Expected boolean settings')
  if changes.get('autoRotate') or changes.get('motionControl') or changes.get('rotationLock') is False:
   raise Rejected('Motion policy unavailable until real motion inputs are validated')
  self.config.update(changes)

 def snapshot(self):
  return dict(schemaVersion=1,ready=True,config=self.config,sensors=list(self.rows.values()),
   activeSubscriptions=len(self.subscriptions),profile='Suspend' if self.suspended else 'Idle' if not self.subscriptions else 'Battery Saver' if self.saver else 'Normal',
   fusion={'status':'Blocked','absoluteOrientation':False,'reason':'Real inputs not validated; fusion not implemented'},
   integrations={k:False for k in ('autoRotation','ambientBrightness','callProximity','etherAIR','etherLocationMotion','cameraOrientation')},
   highFrequencyTransport=False,history=False,simulated=False)
