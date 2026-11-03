"""Verify Debian metadata and exact runtime sources without installing on a phone."""
import hashlib
import io
import json
from pathlib import Path
import subprocess
import tarfile

ROOT=Path(__file__).resolve().parents[1]
def digest(data):return hashlib.sha256(data).hexdigest()

if __name__=='__main__':
    result={}
    for package,version,files in [('ethermap','0.1.0',['backend.py','domain.py','network.py']),('etherlocation','0.1.1',['core.py','service.py','identity.py','ip_provider.py','providers.py','maps.py','gnss.py','client.py'])]:
        path=ROOT/f'build/{package}_{version}_arm64.deb'
        control=subprocess.check_output(['dpkg-deb','--field',str(path)],text=True)
        assert 'Architecture: arm64' in control and f'Package: {package}' in control and f'Version: {version}' in control
        archive=subprocess.check_output(['dpkg-deb','--fsys-tarfile',str(path)])
        checked={}
        with tarfile.open(fileobj=io.BytesIO(archive)) as tar:
            for name in files:
                data=tar.extractfile(f'./usr/share/{package}/{name}').read()
                assert data==(ROOT/package/name).read_bytes(),name
                checked[name]=digest(data)
            if package=='ethermap':
                binary=tar.extractfile('./usr/bin/ethermap').read()
                assert b'--interaction-test' not in binary,'Acceptance driver must be compiled out of production'
                assert b'/usr/libexec/etherlocation-qmi' not in binary,'Map UI must not open GNSS hardware'
                assert 'etherlocation (>= 0.1.1)' in control
                for source,target in [('build/ethermap-westminster-osm.mbtiles','./usr/share/ethermap/maps/westminster.mbtiles'),('build/ethermap-westminster.osm','./usr/share/doc/ethermap/osm/ethermap-westminster.osm')]:
                    assert tar.extractfile(target).read()==(ROOT/source).read_bytes()
        result[package]=dict(version=version,architecture='arm64',sha256=digest(path.read_bytes()),runtimeSourceHashes=checked)
    (ROOT/'evidence/ethermap-package-verification.json').write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps({p:dict(version=r['version'],sha256=r['sha256'],verifiedSources=len(r['runtimeSourceHashes'])) for p,r in result.items()},indent=2))
