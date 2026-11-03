#!/usr/bin/python3
"""Root system bus worker; all private details require administrator authorization."""
import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parent))
from concurrent.futures import ThreadPoolExecutor
import json
import os
import time
import dbus
import dbus.service
from dbus.mainloop.glib import DBusGMainLoop
from gi.repository import GLib
from client import core
from security import BackupError
from authorization import graphical_process

NAME='com.etherneco.EtherBackup1';PATH='/com/etherneco/EtherBackup1'
def dump(d):return json.dumps(d,allow_nan=False,separators=(',',':'))

class Service(dbus.service.Object):
    def __init__(self):
        self.bus=dbus.SystemBus();self.name=dbus.service.BusName(NAME,self.bus,do_not_queue=True)
        super().__init__(self.bus,PATH)
        self.pool=ThreadPoolExecutor(max_workers=1);self.busy=False;self.authorizing=False
        self.state=dict(ready=True,status='Recovery not tested',engine='restic',encrypted=True,fullSystemRecoveryTested=False)
        self.last_notice={}

    @dbus.service.signal(NAME,signature='s')
    def Changed(self,state):pass
    @dbus.service.signal(NAME,signature='s')
    def Event(self,kind):pass

    @dbus.service.method(NAME,in_signature='',out_signature='s')
    def GetState(self):
        # Global signals contain no file paths, repository locations or private history.
        return dump(dict(self.state,busy=self.busy,authorizing=self.authorizing))

    def notice(self,kind):
        if time.monotonic()-self.last_notice.get(kind,-10000)<3600:return
        self.last_notice[kind]=time.monotonic();self.Event(kind)

    @dbus.service.method(NAME,in_signature='s',out_signature='',sender_keyword='sender')
    def ReportEvent(self,kind,sender):
        if int(self.bus.get_unix_user(sender))!=0:raise dbus.DBusException('Administrator required',name=NAME+'.Denied')
        if kind not in ('backup-completed','backup-failed','verification-failed','recovery-point-created','restore-completed'):
            raise dbus.DBusException('Unknown event',name=NAME+'.Rejected')
        try:
            status=core().status();self.state={k:status[k] for k in ('ready','status','engine','encrypted','fullSystemRecoveryTested')}
        except Exception:pass
        self.notice(str(kind));self.Changed(self.GetState())

    def authorize(self,sender,action,operation,success,failure):
        if self.busy or self.authorizing:
            failure(dbus.DBusException('Backup service busy',name=NAME+'.Busy'));return
        self.authorizing=True
        try:
            authority=dbus.Interface(self.bus.get_object('org.freedesktop.PolicyKit1','/org/freedesktop/PolicyKit1/Authority'),'org.freedesktop.PolicyKit1.Authority')
            uid=int(self.bus.get_unix_user(sender))
        except Exception:
            self.authorizing=False;failure(dbus.DBusException('Authorization unavailable',name=NAME+'.Denied'));return
        def subject():
            if int(self.bus.get_unix_user(sender))!=uid:raise BackupError('Caller changed')
            if uid==0:return ('system-bus-name',{'name':dbus.String(sender,variant_level=1)})
            # EtherLock sets the logind LockedHint only after enforcement succeeds.
            manager=dbus.Interface(self.bus.get_object('org.freedesktop.login1','/org/freedesktop/login1'),'org.freedesktop.login1.Manager')
            # Session services and an adopted shell need not have a per-PID
            # graphical session. Resolve this authenticated UID's display session.
            user=manager.GetUser(dbus.UInt32(uid),timeout=3)
            userprops=dbus.Interface(self.bus.get_object('org.freedesktop.login1',user),'org.freedesktop.DBus.Properties')
            display=userprops.Get('org.freedesktop.login1.User','Display',timeout=3)
            if not display[0]:raise BackupError('No graphical session')
            session=display[1]
            props=dbus.Interface(self.bus.get_object('org.freedesktop.login1',session),'org.freedesktop.DBus.Properties')
            values=props.GetAll('org.freedesktop.login1.Session',timeout=3)
            if not values.get('Active',False) or values.get('LockedHint',True) or int(values.get('User',(-1,))[0])!=uid:
                raise BackupError('Active unlocked display session required')
            # Adopted shells can belong to the launcher's SSH cgroup. Derive
            # the session from the bus-authenticated UID, never from arguments.
            # Polkit then uses that session's existing administrator auth agent.
            process=graphical_process(uid,str(values['Scope']))
            return ('unix-process',{'pid':dbus.UInt32(process['pid'],variant_level=1),
                    'start-time':dbus.UInt64(process['start'],variant_level=1),'uid':dbus.Int32(uid,variant_level=1)})
        try:auth_subject=subject()
        except Exception:
            self.authorizing=False;failure(dbus.DBusException('Active unlocked session required',name=NAME+'.Denied'));return
        def denied(error):self.authorizing=False;failure(error)
        def allowed(result):
            self.authorizing=False
            try:
                if not result[0] or subject()!=auth_subject:raise BackupError('Administrator authorization in the same unlocked session required')
            except Exception:
                failure(dbus.DBusException('Administrator authorization required',name=NAME+'.Denied'));return
            self.busy=True;self.Changed(self.GetState())
            def worker():
                value=None;error=None;status=None
                try:
                    c=core();value=operation(c);status=c.status()
                except Exception as e:error=str(e) if isinstance(e,BackupError) else 'Backup operation failed; consult administrator diagnostics'
                def finish():
                    self.busy=False
                    if status:self.state={k:status[k] for k in ('ready','status','engine','encrypted','fullSystemRecoveryTested')}
                    if error:self.state['status']='Operation failed'
                    self.Changed(self.GetState())
                    # Core reports meaningful backup/restore events once. Validation
                    # errors stay with the requesting caller rather than duplicating notices.
                    if error:failure(dbus.DBusException(error,name=NAME+'.Rejected'))
                    else:success(dump(value))
                    return False
                GLib.idle_add(finish)
            self.pool.submit(worker)
        try:
            authority.CheckAuthorization(auth_subject,
                'com.etherneco.etherbackup.'+action,{},dbus.UInt32(1),'',reply_handler=allowed,error_handler=denied,timeout=60)
        except Exception:denied(dbus.DBusException('Authorization unavailable',name=NAME+'.Denied'))

    @dbus.service.method(NAME,in_signature='',out_signature='s',sender_keyword='sender',async_callbacks=('success','failure'))
    def Inspect(self,sender,success,failure):self.authorize(sender,'inspect',lambda c:c.status(True),success,failure)
    @dbus.service.method(NAME,in_signature='ss',out_signature='s',sender_keyword='sender',async_callbacks=('success','failure'))
    def Backup(self,profile,destination,sender,success,failure):self.authorize(sender,'manage',lambda c:c.backup(str(profile),str(destination)),success,failure)
    @dbus.service.method(NAME,in_signature='ss',out_signature='s',sender_keyword='sender',async_callbacks=('success','failure'))
    def Verify(self,ident,level,sender,success,failure):self.authorize(sender,'manage',lambda c:c.verify(str(ident),str(level)),success,failure)
    @dbus.service.method(NAME,in_signature='ss',out_signature='s',sender_keyword='sender',async_callbacks=('success','failure'))
    def Preview(self,ident,prefix,sender,success,failure):self.authorize(sender,'restore',lambda c:c.preview(str(ident),str(prefix)),success,failure)
    @dbus.service.method(NAME,in_signature='ssb',out_signature='s',sender_keyword='sender',async_callbacks=('success','failure'))
    def Restore(self,ident,prefix,confirmed,sender,success,failure):self.authorize(sender,'restore',lambda c:c.restore(str(ident),str(prefix),bool(confirmed)),success,failure)
    @dbus.service.method(NAME,in_signature='s',out_signature='s',sender_keyword='sender',async_callbacks=('success','failure'))
    def Protect(self,ident,sender,success,failure):self.authorize(sender,'manage',lambda c:c.protect(str(ident)) or dict(protected=True),success,failure)
    @dbus.service.method(NAME,in_signature='s',out_signature='s',sender_keyword='sender',async_callbacks=('success','failure'))
    def RecoveryInfo(self,ident,sender,success,failure):self.authorize(sender,'inspect',lambda c:c.recovery_info(str(ident)),success,failure)

if __name__=='__main__':
    os.umask(0o077);DBusGMainLoop(set_as_default=True);service=Service();GLib.MainLoop().run()
