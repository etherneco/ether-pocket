#!/usr/bin/python3
"""Independent administrator CLI. Secrets are entered on the terminal, never printed."""
import argparse
import getpass
import json
import os
from pathlib import Path
import sys
sys.path.insert(0,str(Path(__file__).resolve().parent))
from core import Core
from platform_state import power, inhibit, capture, scheduled_allowed
from security import BackupError, atomic, credential, identifier, lock, private, protected

def load():return protected('/etc/etherbackup/policy.json')
def notify(kind):
    try:
        import dbus
        bus=dbus.SystemBus(private=True)
        try:
            n='com.etherneco.EtherBackup1'
            dbus.Interface(bus.get_object(n,'/com/etherneco/EtherBackup1'),n).ReportEvent(kind,timeout=3)
        finally:bus.close()
    except Exception:pass

def core():return Core('/var/lib/etherbackup',load(),safety=power,inhibit=inhibit,metadata=capture,notify=notify)

def init_repository(c,name,confirmed):
    if not confirmed:raise BackupError('Confirm repository initialization and independent recovery password retention')
    config=c.config['destinations'].get(name)
    if not config:raise BackupError('Destination not commissioned')
    path=Path(config['passwordFile'])
    if not path.exists():
        if path.parent!=Path('/etc/etherbackup/credentials'):raise BackupError('New passwords must be in the protected credentials directory')
        private(path.parent)
        value=getpass.getpass('New recovery password (retain independently): ')
        if len(value.encode())<16 or len(value.encode())>4095 or '\n' in value or value!=getpass.getpass('Repeat recovery password: '):raise BackupError('Passwords differ or length invalid')
        fd=os.open(path,os.O_WRONLY|os.O_CREAT|os.O_EXCL|os.O_NOFOLLOW,0o600)
        with os.fdopen(fd,'w') as f:f.write(value+'\n');f.flush();os.fsync(f.fileno())
        del value
    with lock(c.directory/'job.lock'):
        engine,_=c.engine(name);engine.init()
    return dict(initialized=True,encrypted=True,independentRecoveryKeyRequired=True)

def main():
    parser=argparse.ArgumentParser(prog='etherbackup',description=__doc__)
    sub=parser.add_subparsers(dest='command',required=True)
    sub.add_parser('status');sub.add_parser('list')
    sub.add_parser('usb-devices')
    p=sub.add_parser('commission-usb');p.add_argument('name');p.add_argument('mount');p.add_argument('--confirm',action='store_true')
    for cmd in ('init','backup','retention'):
        p=sub.add_parser(cmd);p.add_argument('destination')
        if cmd=='backup':p.add_argument('--profile',default='personal')
        if cmd=='init':p.add_argument('--confirm-independent-password',action='store_true')
    p=sub.add_parser('verify');p.add_argument('point');p.add_argument('--level',choices=['metadata','integrity','sample','drill'],default='sample')
    for cmd in ('preview','restore','recovery-info','protect'):
        p=sub.add_parser(cmd);p.add_argument('point')
        if cmd in ('preview','restore'):p.add_argument('--path',default='')
        if cmd=='restore':p.add_argument('--confirm',action='store_true')
    p=sub.add_parser('export-key');p.add_argument('destination');p.add_argument('output');p.add_argument('--confirm',action='store_true')
    p=sub.add_parser('pre-update');p.add_argument('transaction');p.add_argument('components',nargs='+')
    p=sub.add_parser('update-result');p.add_argument('transaction');p.add_argument('result',choices=['healthy','failed','rolled-back'])
    sub.add_parser('scheduled')
    args=parser.parse_args()
    if os.geteuid()!=0:raise BackupError('Run as administrator; CLI diagnostics contain private backup details')
    c=core();cmd=args.command
    if cmd=='status':result=c.status(details=True)
    elif cmd=='list':result=c.records()
    elif cmd=='usb-devices':
        from destinations import usb_candidates
        result=usb_candidates()
    elif cmd=='commission-usb':
        if not args.confirm:raise BackupError('Explicit confirmation required to save the USB destination')
        from destinations import usb_configuration
        destination=usb_configuration(args.name,args.mount)
        with lock(c.directory/'job.lock'):
            config=load()
            if args.name in config['destinations']:raise BackupError('Destination already exists; refusing to replace access configuration')
            config['destinations'][args.name]=destination;atomic('/etc/etherbackup/policy.json',config)
        result=dict(saved=True,name=args.name,next='Run etherbackup init NAME --confirm-independent-password in a local private terminal',formatted=False)
    elif cmd=='init':result=init_repository(c,args.destination,args.confirm_independent_password)
    elif cmd=='backup':result=c.backup(args.profile,args.destination)
    elif cmd=='verify':result=c.verify(args.point,args.level)
    elif cmd=='preview':result=c.preview(args.point,args.path)
    elif cmd=='restore':result=c.restore(args.point,args.path,args.confirm)
    elif cmd=='retention':result=c.retain(args.destination)
    elif cmd=='protect':c.protect(args.point);result=dict(protected=True)
    elif cmd=='recovery-info':result=c.recovery_info(args.point)
    elif cmd=='export-key':
        if not args.confirm:raise BackupError('Explicit key export confirmation required')
        config=c.config['destinations'].get(args.destination)
        if not config:raise BackupError('Unknown destination')
        src=credential(config['passwordFile']);target=Path(args.output)
        from security import open_source
        fd=open_source(target.parent,directory=True)
        try:
            info=os.fstat(fd)
            if info.st_uid!=0 or info.st_mode&0o077:raise BackupError('Export directory must be administrator-owned and private')
            out=os.open(target.name,os.O_WRONLY|os.O_CREAT|os.O_EXCL|os.O_NOFOLLOW,0o600,dir_fd=fd)
            with os.fdopen(out,'wb') as dst,open(src,'rb') as source:
                dst.write(source.read());dst.flush();os.fsync(dst.fileno())
        finally:os.close(fd)
        result=dict(exported=True,warning='Retain separately from both handset and repository; loss of all passwords makes encrypted data unrecoverable')
    elif cmd=='pre-update':
        identifier(args.transaction)
        destination=c.config.get('updateDestination')
        if not destination:raise BackupError('Pre-update backup destination not commissioned')
        row=c.backup('applications',destination,args.components,args.transaction)
        result={k:row[k] for k in ('id','snapshot','destination','sampleVerified','verifiedAt')}
    elif cmd=='update-result':result=c.update_result(args.transaction,args.result)
    elif cmd=='scheduled':
        schedule=scheduled_allowed(c.config,power())
        result=c.backup(schedule.get('profile','personal'),schedule['destination'])
        if c.config.get('retention',{}).get('automatic'):c.retain(schedule['destination'])
    print(json.dumps(result,allow_nan=False,indent=2))

if __name__=='__main__':
    os.umask(0o077)
    try:main()
    except BackupError as e:print(str(e),file=sys.stderr);sys.exit(1)
    except Exception:print('Backup operation failed; consult private administrator diagnostics',file=sys.stderr);sys.exit(1)
