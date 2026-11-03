"""EtherPocket Control — Windows desktop companion."""
import ctypes
import io
import json
import os
from pathlib import Path
import queue
import subprocess
import sys
import threading
import time
import tkinter as tk
from tkinter import filedialog, messagebox, ttk

from PIL import Image, ImageTk
from transport import CREATE_NO_WINDOW, frames, install_agent, map_pointer, ssh_command

ASSETS = Path(__file__).resolve().parent
BASE = Path(sys.executable).parent if getattr(sys, 'frozen', False) else ASSETS.parent
CONFIG = Path(os.environ.get('LOCALAPPDATA', str(Path.home()))) / 'EtherPocketControl' / 'connection.json'


class App:
    def __init__(self, root):
        self.root = root
        root.title('EtherPocket Control')
        root.geometry('1050x900'); root.minsize(760, 580)
        root.configure(bg='#101722')
        self.process = None; self.worker = None; self.generation = 0
        self.events = queue.Queue(); self.latest = queue.Queue(maxsize=1)
        self.last_image = None; self.photo = None; self.remote = (1, 1)
        self.bounds = (0, 0, 0, 0); self.last_move = 0; self.received = 0
        self.ready = False; self.held = set(); self.last_render = 0
        style = ttk.Style(); style.theme_use('clam')
        style.configure('TFrame', background='#101722')
        style.configure('TLabel', background='#101722', foreground='#e2eaf5', font=('Segoe UI', 10))
        style.configure('TButton', font=('Segoe UI', 10), padding=(12, 7))
        style.configure('TCheckbutton', background='#101722', foreground='#e2eaf5')
        style.configure('Title.TLabel', font=('Segoe UI', 20, 'bold'))
        style.configure('Hint.TLabel', foreground='#9eafc3')
        header = ttk.Frame(root, padding=(20, 15)); header.pack(fill='x')
        ttk.Label(header, text='EtherPocket Control', style='Title.TLabel').pack(side='left')
        ttk.Label(header, text='Pulpit telefonu przez USB / SSH', style='Hint.TLabel').pack(side='right')
        toolbar = ttk.Frame(root, padding=(20, 0, 20, 10)); toolbar.pack(fill='x')
        self.connect_button = ttk.Button(toolbar, text='Połącz', command=self.connect)
        self.connect_button.pack(side='left')
        ttk.Button(toolbar, text='Rozłącz', command=self.disconnect).pack(side='left', padx=6)
        ttk.Button(toolbar, text='Zrzut ekranu', command=self.screenshot).pack(side='left')
        ttk.Button(toolbar, text='Ustawienia', command=self.settings).pack(side='left', padx=6)
        self.control = tk.BooleanVar(value=True)
        ttk.Checkbutton(toolbar, text='Sterowanie', variable=self.control, command=self.release).pack(side='right')
        self.canvas = tk.Canvas(root, bg='#080c12', highlightthickness=0, takefocus=True)
        self.canvas.pack(fill='both', expand=True, padx=20)
        self.placeholder = self.canvas.create_text(300, 200, text='Podłącz EtherPocket przez USB\ni wybierz „Połącz”.',
            fill='#9eafc3', font=('Segoe UI', 16), justify='center')
        self.image_item = self.canvas.create_image(0, 0, anchor='nw')
        self.canvas.bind('<Configure>', self.resize)
        self.canvas.bind('<Motion>', self.move)
        for button in (1, 2, 3):
            self.canvas.bind(f'<ButtonPress-{button}>', lambda e, b=button: self.button(e, b, True))
            self.canvas.bind(f'<ButtonRelease-{button}>', lambda e, b=button: self.button(e, b, False))
        self.canvas.bind('<MouseWheel>', self.wheel)
        self.canvas.bind('<KeyPress>', self.key_down)
        self.canvas.bind('<KeyRelease>', self.key_up)
        self.canvas.bind('<FocusOut>', lambda e: self.release())
        footer = ttk.Frame(root, padding=(20, 10)); footer.pack(fill='x')
        self.status = tk.StringVar(value='Gotowy. Połączenie wymaga zaufanego klucza SSH telefonu.')
        ttk.Label(footer, textvariable=self.status, wraplength=1000).pack(anchor='w')
        ttk.Label(footer, text='Kliknij obraz, aby pisać. Przeciąganie = gest. Kółko = przewijanie. Zrzuty zapisują się na komputerze.', style='Hint.TLabel').pack(anchor='w', pady=(4, 0))
        self.config = {'host': '10.77.0.2', 'key': str(BASE/'build/etherpocket_ed25519'),
                       'known_hosts': str(BASE/'build/mobian-known-hosts'), 'fps': 8}
        for path in (BASE/'connection.json', CONFIG):
            if path.exists():
                try:
                    values = json.loads(path.read_text(encoding='utf-8-sig'))
                    self.config.update({k: v for k, v in values.items() if k in self.config})
                except (OSError, ValueError):
                    pass
        root.protocol('WM_DELETE_WINDOW', self.close)
        root.after(30, self.poll)

    def connect(self):
        if self.worker and self.worker.is_alive():
            return
        try:
            ssh = ssh_command(self.config['host'], self.config['key'], self.config['known_hosts'])
            fps = max(1, min(15, int(self.config['fps'])))
        except (ValueError, OSError) as error:
            messagebox.showerror('Połączenie', str(error)); return
        self.disconnect()
        generation = self.generation
        self.status.set('Łączenie z EtherPocket…')
        self.connect_button.configure(state='disabled')
        self.worker = threading.Thread(target=self.receive, args=(generation, ssh, fps), daemon=True)
        self.worker.start()

    def receive(self, generation, ssh, fps):
        process = None
        errors = bytearray()
        try:
            install_agent(ssh, (ASSETS/'agent.py').read_bytes())
            if generation != self.generation:
                return
            command = 'exec runuser -u mobian -- env DISPLAY=:0 XAUTHORITY=/home/mobian/.Xauthority python3 /usr/local/lib/etherpocket-control/agent.py ' + str(fps)
            process = subprocess.Popen(ssh+[command], stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                stderr=subprocess.PIPE, creationflags=CREATE_NO_WINDOW)
            self.process = process
            def drain():
                for block in iter(lambda: process.stderr.read(1024), b''):
                    errors.extend(block)
                    if len(errors) > 8192:
                        del errors[:-8192]
            threading.Thread(target=drain, daemon=True).start()
            header = process.stdout.readline(4096)
            metadata = json.loads(header)
            if metadata.get('version') != 1 or not (0 < metadata['width'] <= 16384 and 0 < metadata['height'] <= 16384):
                raise ValueError('Nieprawidłowy rozmiar pulpitu')
            self.events.put((generation, 'connected', metadata))
            for jpeg in frames(process.stdout):
                if generation != self.generation:
                    break
                image = Image.open(io.BytesIO(jpeg)); image.load()
                try:
                    self.latest.get_nowait()
                except queue.Empty:
                    pass
                self.latest.put((generation, image))
            if generation == self.generation:
                raise RuntimeError(errors.decode(errors='replace').strip() or 'Telefon zakończył przesyłanie obrazu')
        except Exception as error:
            detail = str(error)
            if errors:
                detail += '\n' + errors.decode(errors='replace').strip()
            self.events.put((generation, 'error', detail[-1800:]))
        finally:
            if process:
                try:
                    process.stdin.close()
                    process.wait(timeout=4)
                except (OSError, subprocess.TimeoutExpired):
                    process.kill()
            self.events.put((generation, 'done', None))

    def send(self, event):
        process = self.process
        if not process or process.poll() is not None:
            return
        try:
            process.stdin.write((json.dumps(event, ensure_ascii=True)+'\n').encode())
            process.stdin.flush()
        except (OSError, ValueError):
            pass

    def poll(self):
        try:
            while True:
                generation, kind, data = self.events.get_nowait()
                if generation != self.generation:
                    continue
                if kind == 'connected':
                    self.remote = (data['width'], data['height']); self.ready = True
                    self.received = 0; self.last_render = time.monotonic()
                    self.canvas.itemconfigure(self.placeholder, state='hidden')
                    self.status.set(f'Połączono • pulpit {self.remote[0]} × {self.remote[1]} • oczekiwanie na obraz')
                elif kind == 'error':
                    self.status.set('Błąd: '+data); self.ready = False
                elif kind == 'done':
                    self.connect_button.configure(state='normal'); self.ready = False
        except queue.Empty:
            pass
        try:
            generation, image = self.latest.get_nowait()
            if generation == self.generation:
                self.last_image = image; self.render(); self.received += 1
                if self.received % 8 == 0:
                    self.status.set(f'Połączono • {self.remote[0]} × {self.remote[1]} • obraz {image.width} × {image.height} • '+('sterowanie aktywne' if self.control.get() else 'tylko podgląd'))
        except queue.Empty:
            pass
        self.root.after(30, self.poll)

    def render(self):
        if self.last_image is None:
            return
        width, height = max(1, self.canvas.winfo_width()), max(1, self.canvas.winfo_height())
        scale = min(width/self.last_image.width, height/self.last_image.height)
        size = (max(1, int(self.last_image.width*scale)), max(1, int(self.last_image.height*scale)))
        left, top = (width-size[0])//2, (height-size[1])//2
        self.bounds = (left, top, *size)
        self.photo = ImageTk.PhotoImage(self.last_image.resize(size, Image.Resampling.BILINEAR))
        self.canvas.itemconfigure(self.image_item, image=self.photo)
        self.canvas.coords(self.image_item, left, top)

    def resize(self, event):
        self.canvas.coords(self.placeholder, event.width/2, event.height/2)
        self.render()

    def position(self, event):
        if not self.control.get() or not self.ready:
            return None
        return map_pointer(event.x, event.y, self.bounds, self.remote)

    def move(self, event):
        if time.monotonic()-self.last_move < .025:
            return
        pos = self.position(event)
        if pos:
            self.send(dict(type='move', x=pos[0], y=pos[1])); self.last_move = time.monotonic()

    def button(self, event, button, down):
        pos = self.position(event)
        if down and pos:
            self.canvas.focus_set()
            self.send(dict(type='move', x=pos[0], y=pos[1]))
            self.held.add(button)
            self.send(dict(type='button', button=button, down=True))
        elif not down and button in self.held:
            self.send(dict(type='button', button=button, down=False)); self.held.discard(button)

    def wheel(self, event):
        if self.position(event):
            for _ in range(min(5, max(1, abs(event.delta)//120))):
                button = 4 if event.delta > 0 else 5
                self.send(dict(type='button', button=button, down=True))
                self.send(dict(type='button', button=button, down=False))
        return 'break'

    def key_down(self, event):
        if not self.ready or not self.control.get():
            return 'break'
        # Text uses xdotool's Unicode mapping; shortcuts use real key states.
        if event.char and event.char.isprintable() and (ord(event.char[0]) > 127 or not event.state & (4 | 0x20000)):
            self.send(dict(type='text', text=event.char))
        else:
            self.send(dict(type='key', key=event.keysym, down=True))
        return 'break'

    def key_up(self, event):
        if self.ready and self.control.get():
            self.send(dict(type='key', key=event.keysym, down=False))
        return 'break'

    def release(self):
        self.send(dict(type='release')); self.held.clear()

    def disconnect(self):
        self.release(); self.send(dict(type='stop'))
        self.generation += 1; self.ready = False
        process = self.process; self.process = None
        if process:
            def reap():
                try:
                    process.wait(timeout=4)
                except subprocess.TimeoutExpired:
                    process.kill()
            threading.Thread(target=reap, daemon=True).start()
        self.connect_button.configure(state='normal')
        self.status.set('Rozłączono. Obraz zatrzymany.')

    def screenshot(self):
        if self.last_image is None:
            messagebox.showinfo('Zrzut ekranu', 'Najpierw połącz się z telefonem.'); return
        path = filedialog.asksaveasfilename(title='Zapisz zrzut EtherPocket', defaultextension='.png',
            initialfile=time.strftime('EtherPocket-%Y%m%d-%H%M%S.png'), filetypes=[('PNG', '*.png')])
        if path:
            self.last_image.save(path); self.status.set('Zapisano: '+path)

    def settings(self):
        window = tk.Toplevel(self.root); window.title('Połączenie z EtherPocket'); window.resizable(False, False)
        frame = ttk.Frame(window, padding=20); frame.pack(fill='both')
        fields = {}
        for row, (key, label) in enumerate([('host', 'Adres telefonu'), ('key', 'Klucz prywatny SSH'), ('known_hosts', 'Zaufane klucze hosta'), ('fps', 'Klatki/s (1–15)')]):
            ttk.Label(frame, text=label).grid(row=row*2, column=0, sticky='w', pady=(8, 3))
            value = tk.StringVar(value=str(self.config[key])); fields[key] = value
            ttk.Entry(frame, textvariable=value, width=65).grid(row=row*2+1, column=0, sticky='ew')
            if key in ('key', 'known_hosts'):
                def choose(v=value):
                    name = filedialog.askopenfilename(parent=window)
                    if name: v.set(name)
                ttk.Button(frame, text='Wybierz…', command=choose).grid(row=row*2+1, column=1, padx=(6, 0))
        def save():
            try:
                values = {k: v.get().strip() for k, v in fields.items()}
                values['fps'] = int(values['fps'])
                if not 1 <= values['fps'] <= 15: raise ValueError('FPS musi być od 1 do 15')
                ssh_command(values['host'], values['key'], values['known_hosts'])
                CONFIG.parent.mkdir(parents=True, exist_ok=True)
                CONFIG.write_text(json.dumps(values, indent=2), encoding='utf-8')
                self.config = values; window.destroy()
            except (ValueError, OSError) as error:
                messagebox.showerror('Ustawienia', str(error), parent=window)
        ttk.Button(frame, text='Zapisz', command=save).grid(row=9, column=0, sticky='e', pady=(15, 0))
        window.transient(self.root); window.grab_set()

    def close(self):
        self.disconnect(); self.root.destroy()


if __name__ == '__main__':
    if sys.platform == 'win32':
        ctypes.windll.shcore.SetProcessDpiAwareness(1)
    root = tk.Tk(); app = App(root)
    if '--self-test' in sys.argv:
        output = Path(sys.argv[sys.argv.index('--self-test')+1])
        deadline = time.monotonic()+45
        def check_live():
            if app.received >= 8 or time.monotonic() > deadline:
                report = {'ok': app.received >= 8, 'frames': app.received, 'remote': app.remote,
                          'status': app.status.get(), 'frozen': bool(getattr(sys, 'frozen', False))}
                if app.last_image is not None:
                    app.last_image.save(output.with_suffix('.png'))
                output.write_text(json.dumps(report, indent=2), encoding='utf-8')
                app.close()
            else:
                root.after(100, check_live)
        root.after(200, app.connect); root.after(300, check_live)
    elif '--connect' in sys.argv:
        root.after(200, app.connect)
    root.mainloop()
