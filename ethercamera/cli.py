#!/usr/bin/python3
"""Managed camera client; never opens cameras without --consent."""
import argparse
import json
import os
import sys
import time
import dbus

def main():
    p=argparse.ArgumentParser(description='EtherCamera diagnostics and explicit UVC capture')
    sub=p.add_subparsers(dest='command',required=True)
    for name in ('state','refresh','report','media'):sub.add_parser(name)
    config=sub.add_parser('configure');config.add_argument('json')
    album=sub.add_parser('album');album.add_argument('reference');album.add_argument('name')
    export=sub.add_parser('export');export.add_argument('reference')
    manual=sub.add_parser('manual');manual.add_argument('format');manual.add_argument('text')
    for name in ('photo','scan','video'):
        s=sub.add_parser(name);s.add_argument('device');s.add_argument('--consent',action='store_true')
        s.add_argument('--purpose',default='Interactive camera capture')
        s.add_argument('--seconds',type=int,default=5)
        if name=='video':s.add_argument('--microphone-consent',action='store_true')
    a=p.parse_args()
    api=dbus.Interface(dbus.SessionBus().get_object('com.etherneco.EtherCamera1','/com/etherneco/EtherCamera1'),'com.etherneco.EtherCamera1')
    if a.command=='state':print(api.GetState());return
    if a.command=='refresh':print(api.Refresh());return
    if a.command=='report':print(api.DiagnosticReport());return
    if a.command=='media':print(api.ListMedia(''));return
    if a.command=='configure':print(api.Configure(a.json));return
    if a.command=='album':print(api.SetAlbum(a.reference,a.name));return
    if a.command=='export':print(api.ExportMedia(a.reference,timeout=45));return
    if a.command=='manual':print(api.ManualCode(a.format,a.text));return
    if not a.consent:p.error('Capture requires --consent after explicit user interaction')
    if not 1<=a.seconds<=60:p.error('Use 1 to 60 seconds')
    token=api.RequestSession(a.device,a.purpose,True,'{}')
    import signal
    def interrupt(*unused):raise KeyboardInterrupt
    signal.signal(signal.SIGTERM,interrupt)
    try:
        api.StartPreview(token)
        deadline=time.monotonic()+10
        while True:
            try:
                fd=api.GetFrame(token).take();os.close(fd);break
            except dbus.DBusException as e:
                if 'No fresh physical camera frame' not in str(e) or time.monotonic()>deadline:raise
                time.sleep(.1)
        if a.command=='photo':print(api.CapturePhoto(token))
        elif a.command=='video':
            if a.microphone_consent:api.StartRecordingWithAudio(token,True)
            else:api.StartRecording(token)
            time.sleep(a.seconds);print(api.StopRecording(token,timeout=15))
        else:
            job=api.Scan(token,False)
            deadline=time.monotonic()+15
            while time.monotonic()<deadline:
                result=json.loads(str(api.GetJob(job)))
                if result['state']!='running':print(json.dumps(result));break
                time.sleep(.1)
            else:raise RuntimeError('Scan timed out')
    finally:
        try:api.Release(token,timeout=15)
        except dbus.DBusException:pass

if __name__=='__main__':
    try:main()
    except (dbus.DBusException,RuntimeError,KeyboardInterrupt) as e:
        print(str(e),file=sys.stderr);sys.exit(1)
