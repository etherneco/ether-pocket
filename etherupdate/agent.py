"""Single-worker agent; persisted transactions and one-use, caller-bound plans."""
import json
from pathlib import Path
import secrets
import threading
import time
import uuid
from artifacts import ArtifactManager
from engine import InstallationEngine, newer
from history import History, TERMINAL
from provider import Provider, ProviderError, CHANNELS
from security import Rejected, verify_envelope, verify_file
from backup import BackupCoordinator


class Agent:
    def __init__(self,directory,cache,config,keys,device,token='',engine=None,backup=None):
        self.directory=Path(directory);self.directory.mkdir(parents=True,exist_ok=True,mode=0o700)
        self.history=History(self.directory/'history.sqlite');self.history.interrupted()
        self.config=config;self.keys=keys;self.device=device
        self.provider=Provider(token);self.artifacts=ArtifactManager(cache,self.provider)
        self.engine=engine or InstallationEngine()
        self.backup=backup or BackupCoordinator()
        self.plans={};self.cancel=threading.Event();self.progress={}
        self.credential_validated_at=None
        self.status=self.history.setting('discovery',dict(status='Not checked',updates=[]))
        self.installation_id=self.history.setting('installation_id') or uuid.uuid4().hex
        self.history.save_setting('installation_id',self.installation_id)

    def snapshot(self):
        return dict(ready=True,agentVersion='0.1.0',server=self.provider.base,discovery=self.status,
                    credentialConfigured=bool(self.provider.token),credentialValidatedAt=self.credential_validated_at,
                    device=self.device,progress=self.progress,history=self.history.list(),
                    installed={k:self.engine.installed(p) for k,p in self.config['components'].items()},
                    channels=self.history.setting('channels',{}),trustKeys=[dict(id=k,revoked=bool(v.get('revoked'))) for k,v in self.keys.items()],
                    recovery=dict(versionedApplications=True,automaticOS=False,debian='Manual recovery only',selfUpdate=False),
                    capabilities=dict(reporting=False,registration=False,rollout=False,schedulingInstall=False,resumeDownload=False),
                    cacheUsage=sum(p.stat().st_size for p in self.artifacts.directory.glob('*') if p.is_file()))

    def set_credential(self,value,store):
        from credentials import validate
        validate(value)
        candidate=Provider(value)
        try:
            data=candidate.json('/api/manage/projects?page=1')
            if not isinstance(data,dict) or not isinstance(data.get('data'),list):
                raise Rejected('Unexpected authentication response; token was not saved')
        except ProviderError:
            raise Rejected('Token validation failed. Check the token and network connection; the previous credential was preserved') from None
        store.save(value)
        self.provider.token=value;self.credential_validated_at=time.time();self.plans.clear()
        return dict(saved=True)

    def remove_credential(self,store):
        store.save('')
        self.provider.token='';self.credential_validated_at=None;self.plans.clear()
        self.status=dict(status='Token removed; public access only',updates=[])
        self.history.save_setting('discovery',self.status)
        return dict(removed=True)

    def policy(self,project):
        if project not in self.config['components']:raise Rejected('Project is not commissioned in local policy')
        return self.config['components'][project]

    def channel(self,project,channel,confirmed=False):
        policy=self.policy(project)
        if channel not in CHANNELS:raise Rejected('Unknown channel')
        if channel=='Experimental' and policy.get('critical',True) and not confirmed:
            raise Rejected('Confirm Experimental channel for a critical component')
        channels=self.history.setting('channels',{});channels[project]=channel
        self.history.save_setting('channels',channels)

    def manifest(self,project,channel,envelope):
        return verify_envelope(envelope,self.keys,project,channel,self.device)

    def check(self):
        channels=self.history.setting('channels',{});updates=[];errors=[]
        try:
            projects=self.provider.projects()
            accessible={p['slug'] for p in projects}
            for project,policy in self.config['components'].items():
                row=dict(project=project,name=policy.get('name',project),installed=self.engine.installed(policy),channel=channels.get(project,'Stable'))
                try:
                    if project not in accessible:raise ProviderError('Project not found')
                    release=self.provider.latest(project,row['channel'])
                    if not release:row['status']='No updates'
                    else:
                        row.update(version=release.version,notes=release.notes,size=release.size)
                        try:
                            manifest=self.manifest(project,row['channel'],release.envelope)
                            if (manifest['version'],manifest['sha256'],manifest['size'])!=(release.version,release.sha256,release.size):raise Rejected('Release metadata differs from signed identity')
                            self.engine.component(manifest,policy)
                            row.update(compatible=True,reboot=bool(manifest.get('reboot')),dependencies=manifest.get('dependencies',{}))
                            if newer(manifest['version'],row['installed']):
                                # Deduplicate periodic discovery without losing installation history.
                                tx=next((t for t in self.history.list() if t['state'] not in TERMINAL and t['document'].get('manifest')==manifest),None)
                                if tx:ident=tx['id']
                                else:
                                    ident=self.history.create(dict(project=project,channel=row['channel'],envelope=release.envelope,manifest=manifest,url=release.url))
                                    self.history.transition(ident,'Available')
                                row.update(status='Update available',transaction=ident)
                            else:row['status']='No updates'
                        except Rejected as e:row.update(status='No compatible release',reason=str(e),compatible=False)
                except ProviderError as e:row['status']=e.code;errors.append(e.code)
                updates.append(row)
            self.status=dict(status=errors[0] if errors else 'No components commissioned' if not self.config['components'] else 'Update available' if any(r['status']=='Update available' for r in updates) else 'No updates',
                             lastSuccessfulCheck=time.time() if not errors else self.status.get('lastSuccessfulCheck'),updates=updates,
                             accessibleProjects=projects)
        except (ProviderError,ValueError,KeyError,TypeError) as e:
            self.status=dict(self.status,status=e.code if isinstance(e,ProviderError) else 'Invalid server metadata')
        self.history.save_setting('discovery',self.status)
        return self.status

    def download(self,ident):
        tx=self.history.get(ident)
        if tx['state']!='Available':raise Rejected('Download requires an available transaction')
        doc=tx['document'];manifest=self.manifest(doc['project'],doc['channel'],doc['envelope'])
        self.cancel.clear();self.history.transition(ident,'Downloading')
        try:
            self.artifacts.download(manifest,doc['url'],self.cancel,lambda n,total:self.progress.update(transaction=ident,bytes=n,total=total))
            self.history.transition(ident,'Downloaded');self.history.transition(ident,'Verifying')
            self.manifest(doc['project'],doc['channel'],doc['envelope']);verify_file(self.artifacts.path(manifest),manifest)
            self.history.transition(ident,'Verified')
        except Exception:
            self.history.transition(ident,'Cancelled' if self.cancel.is_set() else 'Verification Failed',error='Download cancelled' if self.cancel.is_set() else 'Download or verification failed; retry with a fresh check')
            raise
        finally:self.progress={}

    def prepare(self,ident,uid,safety):
        tx=self.history.get(ident)
        if tx['state']!='Verified':raise Rejected('Download and signature verification must complete first')
        doc=tx['document'];m=self.manifest(doc['project'],doc['channel'],doc['envelope'])
        self.safe(safety);self.engine.preflight(self.artifacts.path(m),m,self.policy(doc['project']))
        token=secrets.token_urlsafe(32)
        self.plans={k:v for k,v in self.plans.items() if v['expires']>time.monotonic()}
        self.plans[token]=dict(uid=uid,id=ident,expires=time.monotonic()+120,sha256=m['sha256'])
        return dict(approval=token,transaction=ident,version=m['version'],package=m['package'],expiresIn=120,
                    recovery='Versioned application only' if m['type']=='versioned-bundle' else 'Manual Debian recovery; no atomic rollback')

    @staticmethod
    def safe(s):
        if s.get('callActive') is not False or s.get('recording') is not False or s.get('criticalActivity') is not False:
            raise Rejected('Activity is active or unknown; defer installation')
        if type(s.get('battery')) not in (int,float) or s['battery']<40:
            raise Rejected('Battery must be at least 40%; unknown battery state is unsafe')

    def install(self,token,uid,safety,inhibit):
        plan=self.plans.pop(token,None)
        if not plan or plan['uid']!=uid or plan['expires']<time.monotonic():raise Rejected('Approval expired, consumed or belongs to another caller')
        self.safe(safety)
        ident=plan['id'];tx=self.history.get(ident);doc=tx['document']
        if tx['state']!='Verified':raise Rejected('Transaction changed after preparation')
        m=self.manifest(doc['project'],doc['channel'],doc['envelope']);policy=self.policy(doc['project'])
        if plan['sha256']!=m['sha256']:raise Rejected('Plan identity changed')
        recovery=None;activated=False
        # Inhibitor acquisition must succeed before entering Preparing.
        with inhibit():
            self.history.transition(ident,'Preparing')
            try:
                data_point=self.backup.request(ident,doc['project'])
                # Persist the verified reference before any application activation.
                self.history.patch(ident,dict(dataRecoveryPoint=data_point))
                path=self.artifacts.path(m);recovery=self.engine.prepare(path,m,policy)
                self.history.transition(ident,'Installing',dict(recovery=recovery))
                activated=True;self.engine.activate(m,recovery,path)
                self.history.transition(ident,'Health Checking')
                health=self.engine.health(m,policy)
                backup_result=self.backup.result(ident,'healthy')
                self.history.transition(ident,'Completed',dict(health=health,backupResult=backup_result))
            except Exception:
                self.backup.result(ident,'failed')
                if activated and recovery and recovery.get('automatic'):
                    try:
                        result=self.engine.rollback(m,policy,recovery)
                        self.history.transition(ident,'Rolled Back',dict(recoveryResult=result),error='Installation health failed; previous application restored and checked')
                    except Exception:self.history.transition(ident,'Manual Intervention Required',error='Installation and recovery failed; use independent SSH recovery')
                else:self.history.transition(ident,'Recovery Required' if activated else 'Installation Failed',error='Installation failed; inspect local recovery record')
                raise Rejected('Installation failed; inspect history and recovery status') from None
        return self.history.get(ident)

    def import_offline(self,project,channel,envelope,source):
        m=self.manifest(project,channel,envelope);self.engine.component(m,self.policy(project))
        self.artifacts.import_file(m,source)
        ident=self.history.create(dict(project=project,channel=channel,envelope=envelope,manifest=m,url='',offline=True))
        for state in ('Available','Downloading','Downloaded','Verifying','Verified'):self.history.transition(ident,state)
        return ident
