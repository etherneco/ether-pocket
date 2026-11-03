#!/usr/bin/env python3
"""Download a digest-verified official Debian AMD64 layer for a WSL build host.

This is ONLY the build host. It is not the phone's target root filesystem.
"""
import hashlib
import json
from pathlib import Path
import urllib.request

out = Path('build/host')
out.mkdir(parents=True, exist_ok=True)
token_url = 'https://auth.docker.io/token?service=registry.docker.io&scope=repository:library/debian:pull'
with urllib.request.urlopen(token_url, timeout=30) as response:
    token = json.load(response)['token']
headers = {'Authorization': 'Bearer ' + token,
           'Accept': 'application/vnd.oci.image.index.v1+json, application/vnd.oci.image.manifest.v1+json, application/vnd.docker.distribution.manifest.list.v2+json, application/vnd.docker.distribution.manifest.v2+json'}
registry = 'https://registry-1.docker.io/v2/library/debian/'


def manifest(reference):
    with urllib.request.urlopen(urllib.request.Request(registry + 'manifests/' + reference, headers=headers), timeout=30) as response:
        raw = response.read()
        digest = response.headers['Docker-Content-Digest']
    if hashlib.sha256(raw).hexdigest() != digest.removeprefix('sha256:'):
        raise RuntimeError('Manifest hash mismatch')
    return json.loads(raw), digest


index, index_digest = manifest('trixie-slim')
platform = next(item for item in index['manifests'] if item['platform'].get('os') == 'linux' and item['platform'].get('architecture') == 'amd64')
image, image_digest = manifest(platform['digest'])
if len(image['layers']) != 1:
    raise RuntimeError('Expected a single Debian rootfs layer; do not import an overlay chain.')
layer = image['layers'][0]
digest = layer['digest']
path = out / 'debian-amd64-rootfs.tar.gz'
request = urllib.request.Request(registry + 'blobs/' + digest, headers=headers)
hash_state = hashlib.sha256()
with urllib.request.urlopen(request, timeout=60) as response, path.open('wb') as stream:
    while chunk := response.read(1024 * 1024):
        hash_state.update(chunk)
        stream.write(chunk)
if hash_state.hexdigest() != digest.removeprefix('sha256:'):
    raise RuntimeError('Rootfs digest mismatch')
(out / 'origin.json').write_text(json.dumps({'purpose': 'WSL AMD64 cross-build host only; not phone OS', 'repository': 'docker.io/library/debian', 'tag': 'trixie-slim', 'index_digest': index_digest, 'image_digest': image_digest, 'layer': layer}, indent=2) + '\n')
print(path, digest, path.stat().st_size, flush=True)
