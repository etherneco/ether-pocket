"""Local trust policy. Network metadata never supplies keys or commands."""
import base64
import hashlib
import json
import os
from pathlib import Path
import re
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey
from cryptography.exceptions import InvalidSignature


class Rejected(ValueError):
    pass


def protected_json(path):
    path = Path(path)
    for item in (path, *path.parents):
        st = item.stat()
        if st.st_uid != 0 or st.st_mode & 0o022:
            raise Rejected('Configuration and its parents must be root-owned and not writable by other users')
    return json.loads(path.read_text())


def identifier(value):
    if not isinstance(value, str) or not re.fullmatch(r'[a-z0-9][a-z0-9+.-]{0,99}', value):
        raise Rejected('Invalid component identifier')
    return value


def verify_envelope(envelope, keys, project, channel, device):
    """Sign exact UTF-8 bytes; no ambiguous cross-language canonicalization."""
    try:
        key_id = envelope['key_id']
        key = keys[key_id]
        if key.get('revoked') or project not in key['projects']:
            raise Rejected('Signing key revoked or outside its project scope')
        payload = base64.b64decode(envelope['payload'], validate=True)
        if len(payload) > 65536:
            raise Rejected('Signed manifest too large')
        Ed25519PublicKey.from_public_bytes(base64.b64decode(key['public_key'], validate=True)).verify(
            base64.b64decode(envelope['signature'], validate=True), payload)
        def unique(pairs):
            result = {}
            for k, v in pairs:
                if k in result: raise Rejected('Duplicate manifest key')
                result[k] = v
            return result
        m = json.loads(payload, object_pairs_hook=unique)
        if m['schema'] != 1 or m['project'] != project or m['channel'] != channel:
            raise Rejected('Signed release identity mismatch')
        identifier(m['package'])
        if not isinstance(m['version'], str) or not re.fullmatch(r'[0-9][A-Za-z0-9.+:~_-]{0,99}', m['version']):
            raise Rejected('Invalid version')
        if m['type'] not in ('versioned-bundle', 'deb'):
            raise Rejected('Unsupported update type; boot, kernel and firmware updates are prohibited')
        if not re.fullmatch('[0-9a-f]{64}', m['sha256']) or type(m['size']) is not int or not 0 < m['size'] <= 1024**3:
            raise Rejected('Invalid signed artifact size or digest')
        for field in ('architecture', 'distribution', 'distribution_major', 'device_family', 'kernel_abi'):
            if m['compatibility'][field] != device.get(field):
                raise Rejected('Incompatible ' + field)
        if m.get('dependencies') and not isinstance(m['dependencies'], dict):
            raise Rejected('Dependencies must map package names to minimum Debian versions')
        return m
    except (KeyError, TypeError, InvalidSignature, ValueError) as e:
        if isinstance(e, Rejected): raise
        raise Rejected('Untrusted or malformed signed manifest') from None


def verify_file(path, manifest):
    digest = hashlib.sha256()
    size = 0
    with open(path, 'rb') as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b''):
            digest.update(chunk); size += len(chunk)
    if size != manifest['size'] or digest.hexdigest() != manifest['sha256']:
        raise Rejected('Artifact size or SHA-256 mismatch')


def atomic(path, data):
    path = Path(path)
    temporary = path.with_suffix('.new')
    with open(temporary, 'wb') as stream:
        stream.write(data); stream.flush(); os.fsync(stream.fileno())
    os.replace(temporary, path)
    fd = os.open(path.parent, os.O_RDONLY | getattr(os, 'O_DIRECTORY', 0))
    try: os.fsync(fd)
    finally: os.close(fd)
