#!/usr/bin/env python3
"""Render the real Settings module in an authenticated private X11 test session.

No mock modem and no network/radio mutation. System D-Bus stays real; session
D-Bus, app preferences, usage files, X11 and runtime sockets are isolated.
"""
import argparse
import json
import os
from pathlib import Path
import secrets
import signal
import subprocess
import tempfile
import time
from types import SimpleNamespace

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--binary',required=True)
    parser.add_argument('--output',type=Path,required=True)
    parser.add_argument('--size',default='480x1000x24')
    parser.add_argument('--suite',choices=['mobile','settings'],default='mobile')
    parser.add_argument('--desktop',action='store_true')
    args=parser.parse_args()
    if os.geteuid()==0:raise SystemExit('Run test UI as an unprivileged user.')
    if Path('/tmp/.X11-unix/X93').exists():raise SystemExit('Display :93 is occupied; nothing changed.')
    args.output.mkdir(parents=True,exist_ok=True)
    with tempfile.TemporaryDirectory(prefix='ethershell-mobile-ui-') as folder:
        root=Path(folder);auth=root/'Xauthority';auth.touch(mode=0o600)
        subprocess.run(['xauth','-f',str(auth),'add',':93','MIT-MAGIC-COOKIE-1',secrets.token_hex(16)],check=True,capture_output=True)
        runtime=root/'runtime';runtime.mkdir(mode=0o700)
        env=os.environ.copy();env.update({'DISPLAY':':93','XAUTHORITY':str(auth),'XDG_RUNTIME_DIR':str(runtime),
            'XDG_CONFIG_HOME':str(root/'config'),'XDG_CACHE_HOME':str(root/'cache'),'XDG_DATA_HOME':str(root/'data'),'XDG_STATE_HOME':str(root/'state'),
            'ETHERSHELL_CONFIG_DIR':str(root/'config/ethershell'),'ETHERSHELL_NESTED_CONFIRMED':'1',
            'ETHERSHELL_DEVELOPMENT':'1','ETHERSHELL_MOBILE_TEST_OUTPUT':str(args.output.resolve()),'LANG':'C.UTF-8',
            # GTK's platform theme must not mount GVFS into the private runtime;
            # it outlives the private bus and prevents TemporaryDirectory cleanup.
            'GIO_USE_VFS':'local','GVFS_DISABLE_FUSE':'1'})
        env.pop('SESSION_MANAGER',None);env.pop('DBUS_SESSION_BUS_ADDRESS',None);env.pop('STATE_DIRECTORY',None)
        if args.desktop:env['ETHERSHELL_DESKTOP_TEST']='1'
        with (args.output/'xserver.log').open('w') as log:
            server=subprocess.Popen(['Xvfb',':93','-screen','0',args.size,'-nolisten','tcp','-auth',str(auth)],env=env,stdout=log,stderr=log)
            try:
                for _ in range(50):
                    if server.poll() is not None:raise RuntimeError('Private X server exited.')
                    if subprocess.run(['xdpyinfo'],env=env,capture_output=True).returncode==0:break
                    time.sleep(.1)
                else:raise RuntimeError('Private X server did not become ready.')
                # Desktop service grandchildren may retain inherited pipe FDs
                # after the test exits. Wait for the actual private session and
                # log to a file, then stop only that disposable process group.
                with (args.output/'session.log').open('wb') as session_log:
                    child=subprocess.Popen(['dbus-run-session','--',args.binary,'--development','--'+args.suite+'-ui-test','--safe-mode'],env=env,stdout=session_log,stderr=subprocess.STDOUT,start_new_session=True)
                    try:
                        code=child.wait(timeout=90)
                    finally:
                        try:os.killpg(child.pid,signal.SIGTERM)
                        except ProcessLookupError:pass
                        if child.poll() is None:
                            try:child.wait(timeout=3)
                            except subprocess.TimeoutExpired:
                                os.killpg(child.pid,signal.SIGKILL);child.wait(timeout=3)
                captured=(args.output/'session.log').read_bytes()
                process=SimpleNamespace(returncode=code,stdout=captured,stderr=captured)
                print('UI exit:',process.returncode)
                if process.returncode:print((process.stdout+process.stderr).decode(errors='replace')[-9000:])
                results=json.loads((args.output/'results.json').read_text()) if (args.output/'results.json').exists() else {}
                print(json.dumps(results,indent=2))
                assert process.returncode==0 and results and all(results.values()),'Settings UI acceptance failed'
                assert not any(path in process.stderr for path in (b'qrc:/qml/',b'qrc:/etherfingerprint/',b'qrc:/etherbackup/',b'qrc:/etherhardware/',b'qrc:/etherpower/',b'qrc:/etheraudio/',b'qrc:/ethercamera/',b'qrc:/etherlocation/',b'qrc:/etherupdate/',b'qrc:/etherphone/',b'qrc:/ethernotifications/')),'QML warning: inspect session.log'
            finally:
                server.terminate()
                try:server.wait(timeout=5)
                except subprocess.TimeoutExpired:server.kill();server.wait(timeout=5)

if __name__=='__main__':main()
