#!/usr/bin/python3
"""Desktop-only capture/input agent. Transport is an authenticated SSH pipe."""
import ctypes
import ctypes.util
import json
import os
from pathlib import Path
import re
import signal
import subprocess
import sys
import threading


def main():
    if Path('/etc/etherpocket/disk-identity').read_text().strip() != 'GM1920-548cb338-mobian-sda21':
        raise RuntimeError('Unexpected EtherPocket identity')
    if os.getuid() != 1000:
        raise RuntimeError('Run as the desktop user')
    x = ctypes.CDLL(ctypes.util.find_library('X11'))
    xt = ctypes.CDLL(ctypes.util.find_library('Xtst'))
    x.XInitThreads()
    x.XOpenDisplay.argtypes = [ctypes.c_char_p]; x.XOpenDisplay.restype = ctypes.c_void_p
    display = x.XOpenDisplay(b':0')
    if not display:
        raise RuntimeError('Desktop display unavailable')
    x.XDefaultScreen.argtypes = [ctypes.c_void_p]
    x.XDisplayWidth.argtypes = x.XDisplayHeight.argtypes = [ctypes.c_void_p, ctypes.c_int]
    x.XFlush.argtypes = x.XCloseDisplay.argtypes = [ctypes.c_void_p]
    x.XStringToKeysym.argtypes = [ctypes.c_char_p]; x.XStringToKeysym.restype = ctypes.c_ulong
    x.XKeysymToKeycode.argtypes = [ctypes.c_void_p, ctypes.c_ulong]; x.XKeysymToKeycode.restype = ctypes.c_uint
    xt.XTestFakeMotionEvent.argtypes = [ctypes.c_void_p, ctypes.c_int, ctypes.c_int, ctypes.c_int, ctypes.c_ulong]
    xt.XTestFakeButtonEvent.argtypes = xt.XTestFakeKeyEvent.argtypes = [ctypes.c_void_p, ctypes.c_uint, ctypes.c_int, ctypes.c_ulong]
    screen = x.XDefaultScreen(display)
    width, height = x.XDisplayWidth(display, screen), x.XDisplayHeight(display, screen)
    fps = max(1, min(15, int(sys.argv[1]) if len(sys.argv) > 1 else 8))
    print(json.dumps({'version': 1, 'width': width, 'height': height, 'fps': fps}), flush=True)
    process = subprocess.Popen(['ffmpeg', '-nostdin', '-hide_banner', '-loglevel', 'error',
        '-threads', '2', '-f', 'x11grab', '-draw_mouse', '1', '-framerate', str(fps),
        '-video_size', f'{width}x{height}', '-i', ':0', '-vf', 'scale=720:-2',
        '-c:v', 'mjpeg', '-threads', '2', '-q:v', '5', '-f', 'image2pipe', 'pipe:1'],
        stdin=subprocess.DEVNULL, stdout=sys.stdout.buffer)
    buttons, keys = set(), set()

    def terminate_capture():
        if process.poll() is None:
            process.terminate()
            # A disconnected viewer may no longer drain stdout. FFmpeg can be
            # blocked in write(), so SIGTERM alone is not a sufficient cleanup.
            def kill_blocked():
                try:
                    process.wait(timeout=1)
                except subprocess.TimeoutExpired:
                    process.kill()
            threading.Thread(target=kill_blocked, daemon=True).start()

    def receive():
        try:
            while process.poll() is None:
                line = sys.stdin.buffer.readline(16385)
                if not line or len(line) > 16384:
                    break
                event = json.loads(line)
                kind = event.get('type')
                if kind == 'move':
                    px = max(0, min(width - 1, int(event['x'])))
                    py = max(0, min(height - 1, int(event['y'])))
                    xt.XTestFakeMotionEvent(display, screen, px, py, 0)
                elif kind == 'button':
                    button = int(event['button'])
                    if button not in range(1, 8):
                        continue
                    down = bool(event['down'])
                    (buttons.add if down else buttons.discard)(button)
                    xt.XTestFakeButtonEvent(display, button, down, 0)
                elif kind == 'key':
                    name = str(event['key'])
                    if not re.fullmatch(r'[A-Za-z0-9_]{1,40}', name):
                        continue
                    code = x.XKeysymToKeycode(display, x.XStringToKeysym(name.encode()))
                    if code:
                        down = bool(event['down'])
                        (keys.add if down else keys.discard)(code)
                        xt.XTestFakeKeyEvent(display, code, down, 0)
                elif kind == 'text':
                    text = event.get('text', '')
                    if isinstance(text, str) and len(text) <= 2048:
                        subprocess.run(['xdotool', 'type', '--clearmodifiers', '--delay', '0', '--', text],
                                       check=True, timeout=15, stdout=subprocess.DEVNULL)
                elif kind == 'release':
                    release()
                elif kind == 'stop':
                    break
                x.XFlush(display)
        except (ValueError, KeyError, OSError, subprocess.SubprocessError):
            pass
        finally:
            release()
            terminate_capture()

    def release():
        for button in list(buttons):
            xt.XTestFakeButtonEvent(display, button, False, 0)
        for key in list(keys):
            xt.XTestFakeKeyEvent(display, key, False, 0)
        buttons.clear(); keys.clear(); x.XFlush(display)

    def stop(*unused):
        terminate_capture()
    signal.signal(signal.SIGTERM, stop)
    reader = threading.Thread(target=receive, daemon=True)
    reader.start()
    try:
        process.wait()
    finally:
        release()
        # The input reader can still be blocked on SSH stdin at this point.
        # Process exit closes the X connection after releasing held inputs.
    return process.returncode


if __name__ == '__main__':
    raise SystemExit(main())
