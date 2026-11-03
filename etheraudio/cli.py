#!/usr/bin/python3
"""Diagnostics and a bounded raw 16-kHz mono S16LE capture pipe for EtherSpeech."""
import argparse
import json
import os
import select
import sys
import time
import dbus

def main():
    parser=argparse.ArgumentParser()
    sub=parser.add_subparsers(dest='command',required=True)
    sub.add_parser('state')
    sub.add_parser('report')
    sub.add_parser('refresh')
    command=sub.add_parser('command');command.add_argument('action');command.add_argument('target');command.add_argument('json',nargs='?',default='{}')
    capture=sub.add_parser('capture');capture.add_argument('--source',default='');capture.add_argument('--purpose',default='Explicit user recording');capture.add_argument('--seconds',type=int,default=60);capture.add_argument('--consent',action='store_true')
    args=parser.parse_args()
    api=dbus.Interface(dbus.SessionBus().get_object('com.etherneco.EtherAudio1','/com/etherneco/EtherAudio1'),'com.etherneco.EtherAudio1')
    if args.command in ('state','report'):print(api.GetState())
    elif args.command=='refresh':api.Refresh()
    elif args.command=='command':print(api.Command(args.action,args.target,args.json,timeout=45))
    else:
        if not args.consent:parser.error('capture requires --consent after explicit user interaction')
        if not 1<=args.seconds<=60:parser.error('capture duration must be 1 to 60 seconds')
        state=json.loads(str(api.GetState()))
        source=args.source or state.get('default-source','')
        token,handle=api.StartCapture(source,args.purpose,args.consent,dbus.UInt32(args.seconds))
        fd=handle.take()
        ended=False
        def stop(*ignored):
            nonlocal ended
            ended=True
            try:api.StopCapture(token)
            except dbus.DBusException:pass
        import signal
        signal.signal(signal.SIGTERM,stop);signal.signal(signal.SIGINT,stop)
        try:
            deadline=time.monotonic()+args.seconds+2
            while not ended and time.monotonic()<deadline:
                if not select.select([fd],[],[],.25)[0]:continue
                chunk=os.read(fd,32768)
                if not chunk:break
                sys.stdout.buffer.write(chunk);sys.stdout.buffer.flush()
        finally:stop();os.close(fd)

if __name__=='__main__':
    try:main()
    except (dbus.DBusException,BrokenPipeError,ValueError) as e:
        print(str(e),file=sys.stderr);sys.exit(1)
