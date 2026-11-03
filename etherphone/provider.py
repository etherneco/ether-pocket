"""Adapter to EtherMobile's existing system ModemManager owner; no QMI writes."""
from abc import ABC, abstractmethod
from core import PhoneError

MM='org.freedesktop.ModemManager1'
ROOT='/org/freedesktop/ModemManager1'
MODEM=MM+'.Modem'
VOICE=MODEM+'.Voice'
CALL=MM+'.Call'

def sim_is_ready(path, unlock_required, modem_state):
    # PIN2/PUK2 protect secondary SIM facilities (for example FDN editing),
    # not the primary SIM unlock. Never submit or guess a PIN2 to place a call.
    return str(path) not in ('', '/') and int(unlock_required) in (1, 3, 5) and int(modem_state) >= 6

class Provider(ABC):
    @abstractmethod
    def snapshot(self):pass
    @abstractmethod
    def dial(self,number):pass
    @abstractmethod
    def command(self,path,action,tone=''):pass

class ModemManagerProvider(Provider):
    def __init__(self):
        import dbus
        from pathlib import Path
        self.dbus=dbus;self.bus=dbus.SystemBus(private=True)
        self.boot=Path('/proc/sys/kernel/random/boot_id').read_text().strip()
        self.selected='';self.generation='';self.known=set()

    def interface(self,path,iface):
        return self.dbus.Interface(self.bus.get_object(MM,path,introspect=False),iface)

    def snapshot(self):
        owner=str(self.bus.get_name_owner(MM))
        if owner!=self.generation:self.known.clear();self.generation=owner
        objects=self.interface(ROOT,'org.freedesktop.DBus.ObjectManager').GetManagedObjects(timeout=5)
        modems=sorted(str(p) for p,i in objects.items() if MODEM in i)
        # No guessed slot switching. Prefer the previous modem while it exists.
        if self.selected not in modems:self.selected=modems[0] if modems else ''
        interfaces=objects.get(self.selected,{})
        m=interfaces.get(MODEM,{})
        v=interfaces.get(VOICE,{})
        sim=str(m.get('Sim','/'))
        registration=int(interfaces.get(MODEM+'.Modem3gpp',{}).get('RegistrationState',0))
        state={'modem':bool(m),'voice':VOICE in interfaces,'simReady':sim_is_ready(sim,m.get('UnlockRequired',0),m.get('State',0)),
            'registered':registration in (1,5),'registration':registration,
            'modemState':int(m.get('State',0)),'emergencyOnly':bool(v.get('EmergencyOnly',False)),
            'simSlots':len(m.get('SimSlots',[])), 'modemCount':len(modems)}
        calls={}
        for path in v.get('Calls',[]):
            path=str(path)
            props=objects.get(path,{}).get(CALL)
            if props is None:props=self.interface(path,'org.freedesktop.DBus.Properties').GetAll(CALL,timeout=3)
            calls[self.boot+'|'+owner+'|'+path]={'path':path,'props':dict(props)}
        self.known={c['path'] for c in calls.values()}
        return state,calls

    def dial(self,n):
        if not self.selected:raise PhoneError('Modem disappeared')
        path=str(self.interface(self.selected,VOICE).CreateCall(self.dbus.Dictionary({'number':self.dbus.String(n)},signature='sv'),timeout=15))
        if not path.startswith(ROOT+'/Call/'):raise PhoneError('Invalid call object returned by backend')
        # A created object is not a connected call. Only observations update state.
        self.known.add(path)
        # An error/timeout can race with a successful modem start. Preserve the
        # backend object for observation and explicit user hangup; never delete
        # a possibly connected call or automatically retry an ambiguous Start.
        self.interface(path,CALL).Start(timeout=20)
        return path

    def command(self,path,action,tone=''):
        if path not in self.known:raise PhoneError('Call is no longer exported by the selected modem')
        api=self.interface(path,CALL)
        if action=='answer':api.Accept(timeout=15)
        elif action in ('end','decline'):api.Hangup(timeout=15)
        elif action=='dtmf':
            import re
            if not re.fullmatch(r'[0-9A-D*#]',tone):raise PhoneError('Select one DTMF tone')
            api.SendDtmf(tone,timeout=5)
        else:raise PhoneError('Unsupported call control')
