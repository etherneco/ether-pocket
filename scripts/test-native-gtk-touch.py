"""Phone-only integration check: XI2 touchscreen -> GTK kinetic scrolling."""
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import time

if len(sys.argv) > 1 and sys.argv[1] == '--probe':
    import gi
    gi.require_version('Gtk', '3.0')
    from gi.repository import Gtk, GLib, Gdk
    events = {}
    def dispatch(event, data):
        name = event.type.value_nick
        events[name] = events.get(name, 0) + 1
        Gtk.main_do_event(event)
    Gdk.event_handler_set(dispatch, None)
    window = Gtk.Window(title='EtherPocket GTK native touch test')
    window.fullscreen()
    scroller = Gtk.ScrolledWindow()
    scroller.set_kinetic_scrolling(True)
    label = Gtk.Label(label='GTK native touch scroll\n' * 300)
    scroller.add(label)
    window.add(scroller)
    window.connect('destroy', Gtk.main_quit)
    window.show_all()

    def report():
        adj = scroller.get_vadjustment()
        Path(sys.argv[2]).write_text(json.dumps({'gtkScrollY': adj.get_value(),
            'upper': adj.get_upper(), 'page': adj.get_page_size(),
            'window': list(window.get_size()), 'events': events}))
        return True

    GLib.timeout_add(300, report)
    Gtk.main()
else:
    from importlib.util import spec_from_file_location, module_from_spec
    spec = spec_from_file_location('touch', Path(__file__).with_name('test-native-touch.py'))
    touch = module_from_spec(spec)
    spec.loader.exec_module(touch)
    env = dict(os.environ, HOME='/home/mobian', DISPLAY=':0',
               XAUTHORITY='/home/mobian/.Xauthority', XDG_RUNTIME_DIR='/run/user/1000')
    with tempfile.TemporaryDirectory(prefix='etherpocket-gtk-touch-') as folder:
        os.chown(folder, 1000, 1000)
        result = Path(folder) / 'result.json'
        with touch.touch_device() as ui:
            time.sleep(2)
            proc = subprocess.Popen(['runuser', '-u', 'mobian', '--', 'python3',
                                     __file__, '--probe', str(result)], env=env)
            try:
                deadline = time.monotonic() + 15
                while not result.exists() and time.monotonic() < deadline:
                    time.sleep(.3)
                assert result.exists(), 'GTK window did not start'
                time.sleep(2)
                # Existing keyboard/dock windows may cover the lower display.
                target = subprocess.check_output(['xdotool', 'search', '--name',
                    '^EtherPocket GTK native touch test$'], env=env, text=True).split()[-1]
                subprocess.run(['xdotool', 'windowactivate', '--sync', target], env=env, check=True)
                time.sleep(.5)
                touch.swipe(ui, start_y=1600)
                time.sleep(3)
                data = json.loads(result.read_text())
                print(json.dumps(data), flush=True)
                assert data['gtkScrollY'] > 100, data
            finally:
                proc.terminate()
                proc.wait(timeout=10)
