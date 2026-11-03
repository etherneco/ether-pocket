"""SSH transport and bounded JPEG framing, independent of the Windows GUI."""
import base64
import hashlib
import json
from pathlib import Path
import re
import subprocess
import sys

CREATE_NO_WINDOW = getattr(subprocess, 'CREATE_NO_WINDOW', 0)


def ssh_command(host, key, known_hosts):
    if not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9.\-]{0,252}', host):
        raise ValueError('Nieprawidłowy adres telefonu')
    for path in (key, known_hosts):
        if not Path(path).is_file():
            raise ValueError('Nie znaleziono pliku: ' + str(path))
    return ['ssh.exe' if sys.platform == 'win32' else 'ssh', '-T', '-i', str(key),
            '-o', 'IdentitiesOnly=yes', '-o', 'BatchMode=yes',
            '-o', 'StrictHostKeyChecking=yes', '-o', 'UserKnownHostsFile=' + str(known_hosts),
            '-o', 'ConnectTimeout=8', '-o', 'ServerAliveInterval=5', '-o', 'ServerAliveCountMax=2',
            'root@' + host]


def install_agent(ssh, source):
    payload = base64.b64encode(source).decode()
    script = f'''import base64,hashlib,pathlib
assert pathlib.Path('/etc/etherpocket/disk-identity').read_text().strip()=='GM1920-548cb338-mobian-sda21'
p=pathlib.Path('/usr/local/lib/etherpocket-control/agent.py')
assert not p.is_symlink()
data=base64.b64decode({payload!r})
assert hashlib.sha256(data).hexdigest()=={hashlib.sha256(source).hexdigest()!r}
if not p.exists() or p.read_bytes()!=data:
 p.parent.mkdir(parents=True,exist_ok=True)
 temp=p.with_suffix('.new');assert not temp.is_symlink()
 temp.write_bytes(data);temp.chmod(0o644);temp.replace(p)
'''
    result = subprocess.run(ssh + ['python3 -'], input=script.encode(), capture_output=True,
                            timeout=25, creationflags=CREATE_NO_WINDOW)
    if result.returncode:
        raise RuntimeError(result.stderr.decode(errors='replace').strip() or 'Nie można przygotować telefonu')


def frames(stream):
    """Yield complete JPEGs; reject truncated or unbounded streams."""
    buffer = bytearray()
    while True:
        chunk = stream.read1(65536) if hasattr(stream, 'read1') else stream.read(65536)
        if not chunk:
            if buffer:
                raise ValueError('Przerwany strumień obrazu')
            return
        buffer.extend(chunk)
        if len(buffer) > 16 * 1024 * 1024:
            raise ValueError('Nieprawidłowy strumień obrazu')
        while True:
            start = buffer.find(b'\xff\xd8')
            if start < 0:
                if len(buffer) > 1:
                    del buffer[:-1]
                break
            end = buffer.find(b'\xff\xd9', start + 2)
            if end < 0:
                if start:
                    del buffer[:start]
                break
            yield bytes(buffer[start:end + 2])
            del buffer[:end + 2]


def map_pointer(x, y, bounds, remote):
    left, top, width, height = bounds
    if width <= 0 or height <= 0 or not (left <= x < left + width and top <= y < top + height):
        return None
    return min(remote[0]-1, int((x-left)*remote[0]/width)), min(remote[1]-1, int((y-top)*remote[1]/height))
