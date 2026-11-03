#!/usr/bin/python3
"""Exercise the real QML UI against disposable files on a private Xvfb server.

Run as a normal user under dbus-run-session, with --binary and --output.
No files outside the temporary fixture/config directories are managed.
"""
import argparse
import json
import os
from pathlib import Path
import subprocess
import tempfile
import time


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--binary', required=True)
    parser.add_argument('--output', required=True)
    args = parser.parse_args()
    if os.geteuid() == 0:
        raise SystemExit('Run the UI test as an unprivileged user.')
    output = Path(args.output)
    output.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix='etherfiles-ui-') as work:
        work = Path(work)
        data = work/'files'
        data.mkdir()
        (data/'original.txt').write_text('EtherFiles UI transfer test\n')
        environment = os.environ.copy()
        runtime = work/'runtime'
        runtime.mkdir(mode=0o700)
        environment.pop('WAYLAND_DISPLAY', None)
        environment.update(DISPLAY=':96', LANG='C.UTF-8', QT_QPA_PLATFORM='xcb', QT_QUICK_BACKEND='software',
                           XDG_RUNTIME_DIR=str(runtime),
                           XDG_CONFIG_HOME=str(work/'config'), XDG_CACHE_HOME=str(work/'cache'),
                           XDG_DATA_HOME=str(work/'data'))
        if Path('/tmp/.X11-unix/X96').exists():
            raise SystemExit('Private test display :96 is already occupied.')
        server = subprocess.Popen(['Xvfb', ':96', '-screen', '0', '1400x1000x24', '-nolisten', 'tcp'], env=environment)
        process = None
        results = {}
        log = (output/'qml.log').open('w')

        def run(*command):
            return subprocess.run(command, env=environment, check=True, capture_output=True, text=True).stdout.strip()

        def wait_for(predicate, timeout=8):
            deadline = time.monotonic()+timeout
            while time.monotonic() < deadline:
                if predicate():
                    return True
                if process and process.poll() is not None:
                    raise RuntimeError('Application exited; inspect qml.log')
                time.sleep(.1)
            raise AssertionError('Timed out waiting for UI result')

        def key(sequence):
            run('xdotool', 'key', '--clearmodifiers', sequence)
            time.sleep(.25)

        def type_text(text):
            run('xdotool', 'type', '--clearmodifiers', '--delay', '1', '--', text)

        def navigate(path):
            key('ctrl+l')
            type_text(str(path))
            key('Return')
            time.sleep(.4)
            # Return focus to the file area before sending file shortcuts.
            run('xdotool', 'mousemove', '--window', window, '500', '600', 'click', '1')

        try:
            time.sleep(.4)
            process = subprocess.Popen([args.binary, str(data)], env=environment, stdout=log, stderr=log)
            wait_for(lambda: subprocess.run(['xdotool', 'search', '--name', '^EtherFiles$'], env=environment, capture_output=True).returncode == 0)
            window = run('xdotool', 'search', '--name', '^EtherFiles$').splitlines()[0]
            run('xdotool', 'windowfocus', window)
            time.sleep(.8)
            key('ctrl+a')
            key('F2')
            key('ctrl+a')
            type_text('renamed.txt')
            key('Return')
            wait_for(lambda: (data/'renamed.txt').exists())
            results['rename_via_keyboard_and_dialog'] = not (data/'original.txt').exists()
            key('ctrl+shift+n')
            type_text('destination')
            key('Return')
            wait_for(lambda: (data/'destination').is_dir())
            results['create_folder_via_dialog'] = True
            # Select just the text file via filename search (the folder sorts first).
            navigate(data)
            run('xdotool', 'mousemove', '--window', window, '450', '325', 'click', '1')
            key('ctrl+c')
            navigate(data/'destination')
            key('ctrl+v')
            wait_for(lambda: (data/'destination/renamed.txt').exists())
            results['clipboard_copy_paste'] = (data/'destination/renamed.txt').read_text() == (data/'renamed.txt').read_text()
            key('ctrl+a')
            key('ctrl+x')
            navigate(data)
            # Rename the original first so moving the copied file has no collision.
            (data/'renamed.txt').rename(data/'original-kept.txt')
            key('F5')
            key('ctrl+v')
            wait_for(lambda: not (data/'destination/renamed.txt').exists())
            results['clipboard_cut_move'] = (data/'renamed.txt').exists()
            key('ctrl+t')
            key('ctrl+w')
            key('ctrl+shift+t')
            results['tabs_keyboard_smoke'] = process.poll() is None
            run('scrot', '--overwrite', str(output/'desktop.png'))
            run('xdotool', 'windowsize', window, '430', '860')
            time.sleep(.7)
            run('scrot', '--overwrite', str(output/'pocket.png'))
            results['adaptive_resize_smoke'] = process.poll() is None
            if not all(results.values()):
                raise AssertionError(results)
        finally:
            if process:
                process.terminate()
                try:
                    process.wait(timeout=8)
                except subprocess.TimeoutExpired:
                    process.kill()
                    process.wait()
            server.terminate()
            server.wait(timeout=5)
            log.close()
            (output/'results.json').write_text(json.dumps(results, indent=2)+'\n')
        print(json.dumps(results, indent=2))


if __name__ == '__main__':
    main()
