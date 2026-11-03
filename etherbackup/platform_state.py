"""Reuse EtherPower/logind and record read-only recovery metadata."""
from contextlib import contextmanager,closing
import json
import os
from pathlib import Path
import platform
import subprocess
from security import BackupError

def power():
    try:
        import dbus
        bus=dbus.SystemBus(private=True)
        try:
            n='com.etherneco.EtherPower1'
            data=json.loads(str(dbus.Interface(bus.get_object(n,'/com/etherneco/EtherPower1'),n).GetState(timeout=5)))
        finally:bus.close()
        if not data.get('ready'):raise ValueError()
        # Cached service samples must be recent. The power service uses ISO UTC stamps.
        from datetime import datetime,timezone
        stamp=datetime.fromisoformat(data['timestamp'].replace('Z','+00:00'))
        age=(datetime.now(timezone.utc)-stamp).total_seconds()
        if not -10<=age<=180:raise ValueError()
        battery=data.get('capacity');temp=data.get('cpuTemperatureC');bt=data.get('batteryTemperatureC')
        if type(battery) not in (int,float) or type(bt) not in (int,float):raise ValueError()
        if battery<20:return dict(allowed=False,reason='Low battery; backup deferred')
        if data.get('thermalWarning') or bt>=45 or (type(temp) in (int,float) and temp>=80):
            return dict(allowed=False,reason='Thermal limit; backup deferred until cool')
        return dict(allowed=True,charging=data.get('externalPower') is True,battery=battery)
    except Exception:return dict(allowed=False,reason='Fresh EtherPower telemetry unavailable')

@contextmanager
def inhibit():
    import dbus
    bus=dbus.SystemBus(private=True);fd=None
    try:
        manager=dbus.Interface(bus.get_object('org.freedesktop.login1','/org/freedesktop/login1'),'org.freedesktop.login1.Manager')
        fd=manager.Inhibit('sleep:shutdown','EtherBackup','Backup/verification/restore in progress','block',timeout=5).take()
        yield
    finally:
        if fd is not None:os.close(fd)
        bus.close()

def capture():
    def run(args):
        p=subprocess.run(args,capture_output=True,text=True,timeout=15)
        if p.returncode:raise BackupError('Recovery metadata discovery failed')
        if len(p.stdout)>8*1024**2:raise BackupError('Recovery metadata exceeds limit')
        return p.stdout
    releases=[]
    # Only signed release identity fields already accepted by EtherUpdate are retained.
    try:
        import sqlite3
        with closing(sqlite3.connect('file:/var/lib/etherupdate/history.sqlite?mode=ro',uri=True,timeout=5)) as db:
            for (raw,) in db.execute("SELECT document FROM transactions WHERE state='Completed' ORDER BY updated DESC LIMIT 100"):
                doc=json.loads(raw);m=doc.get('manifest',{});env=doc.get('envelope',{})
                releases.append({k:m.get(k) for k in ('project','package','version','sha256','channel','dependencies','compatibility')})
                releases[-1]['signingKeyId']=env.get('key_id');releases[-1]['signedEnvelope']=env
    except (OSError,ValueError,sqlite3.Error):pass
    return dict(deviceCompatibility='oneplus7pro',architecture=platform.machine(),kernel=platform.release(),
                osRelease=Path('/etc/os-release').read_text(),
                partitions=json.loads(run(['lsblk','-J','-b','-o','NAME,PKNAME,SIZE,FSTYPE,UUID,PARTLABEL,MOUNTPOINTS,TYPE'])),
                mounts=json.loads(run(['findmnt','-J'])),packages=run(['dpkg-query','-W','-f','${binary:Package}\t${Version}\t${Architecture}\n']),
                accountMetadata=run(['getent','passwd']),groupMetadata=run(['getent','group']),
                releaseAuthority='https://autoupddate.etherneco.com',releases=releases,
                bareMetalRecoveryTested=False,recoveryMethod='Independent trusted host required; see packaged recovery guide')

def scheduled_allowed(config,safety):
    schedule=config.get('schedule',{})
    if not schedule.get('enabled'):raise BackupError('Automatic backups disabled')
    if schedule.get('chargingOnly',True) and not safety.get('charging'):raise BackupError('Waiting for charging')
    if schedule.get('wifiConnection'):
        p=subprocess.run(['nmcli','-t','-f','UUID,TYPE','connection','show','--active'],capture_output=True,text=True,timeout=10)
        if p.returncode or schedule['wifiConnection']+':802-11-wireless' not in p.stdout.splitlines():raise BackupError('Waiting for selected Wi-Fi connection')
    return schedule
