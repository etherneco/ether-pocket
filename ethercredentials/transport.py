"""Protected Unix transport shared by manager and EtherLock auth adapter."""
import json
import os
import socket
import stat
import struct

PATH = '/run/ethercredentials/control'


def call(request):
    info = os.stat(PATH, follow_symlinks=False)
    if not stat.S_ISSOCK(info.st_mode) or info.st_uid != 0:
        raise RuntimeError('Untrusted verifier socket')
    with socket.socket(socket.AF_UNIX) as connection:
        connection.settimeout(30)
        connection.connect(PATH)
        _, uid, _ = struct.unpack('3i', connection.getsockopt(socket.SOL_SOCKET, socket.SO_PEERCRED, 12))
        if uid != 0:
            raise RuntimeError('Untrusted verifier peer')
        connection.sendall((json.dumps(request) + '\n').encode())
        data = bytearray()
        while b'\n' not in data:
            chunk = connection.recv(4096)
            if not chunk or len(data) + len(chunk) > 8192:
                raise RuntimeError('Invalid verifier response')
            data.extend(chunk)
        result = json.loads(data)
        if result.get('ok') is not True:
            raise RuntimeError('Authentication or authorization failed; retry later')
        return result['result']
