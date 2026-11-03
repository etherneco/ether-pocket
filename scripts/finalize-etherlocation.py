"""Verify exact packaged/deployed sources and write an honest release manifest."""
from pathlib import Path
import hashlib,io,json,re,runpy,subprocess,tarfile
ROOT=Path(__file__).resolve().parent.parent
SSH=runpy.run_path(str(ROOT/'scripts/deploy-ethermobile.py'))['SSH']
def read(p):return json.loads((ROOT/p).read_text(encoding='utf-8'))
def sha(p):return hashlib.sha256((ROOT/p).read_bytes()).hexdigest()
if __name__=='__main__':
    installed=read('evidence/etherlocation-install.json');device=read('evidence/etherlocation-device/result.json');stage=read('evidence/etherlocation-shell-stage.json');deployment=read('evidence/etherlocation-shell-deployment.json');runtime=read('evidence/etherlocation-runtime-verification.json')
    acquisition=read('evidence/etherlocation-clear-sky-test.json')
    quality=read('evidence/etherlocation-quality-test.json')
    assert quality['exit']==0 and any(e['event']=='released' for e in quality['events'])
    qualityReports=[e for e in quality['events'] if e['event']=='report-quality']
    assert acquisition['exit']==0 and any(e['event']=='released' for e in acquisition['events'])
    events=runtime['events']+read('evidence/etherlocation-five-minute-test.json')['events']+acquisition['events']+quality['events']
    assert installed['before']==installed['after'] and stage['qa_passed']
    assert stage['package_sha256']==sha('build/ethershell-location_2.1.0_arm64.deb')
    assert deployment['stage']==stage['stage'] and deployment['settings_route']=='location'
    assert device['historyNeverCreated'] and all(device['negativeTests'].values())
    defaults=read('evidence/etherlocation-defaults-install.json')['state']['config']
    assert not defaults['enabled'] and not defaults['history'] and not defaults['networkAuthorized']
    assert not device['state']['config']['history'] and not device['state']['active']
    assert device['map']['exit']==0 and not device['map']['stderr'] and not device['helperProcesses']
    assert runtime['exit']==0 and any(e['event']=='stop' and e['acknowledged'] for e in runtime['events']) and any(e['event']=='released' for e in runtime['events'])
    for name,path in [('etherlocation.deb','build/etherlocation_0.1.0_arm64.deb'),('ethercamera.deb','build/ethercamera_0.4.1_arm64.deb'),('etherhardware.deb','build/etherhardware_0.1.1_arm64.deb')]:assert installed['hashes'][name]==sha(path)
    source={str(p.relative_to(ROOT)).replace('\\','/'):sha(str(p.relative_to(ROOT))) for p in (ROOT/'etherlocation').glob('*.py')}
    source.update({'ethercamera/'+n:sha('ethercamera/'+n) for n in ['service.py','location_metadata.py']})
    remote=r'''
import hashlib,json,pathlib
files=FILES
print(json.dumps({f:hashlib.sha256((pathlib.Path('/usr/share')/f).read_bytes()).hexdigest() for f in files}))
'''.replace('FILES',repr(list(source)))
    output=subprocess.check_output(SSH+['python3 -'],input=remote.encode(),timeout=20)
    assert json.loads(output)==source,'Installed sources differ from delivery'
    archive=subprocess.check_output(['wsl','-d','EtherPocketBuild','--','dpkg-deb','--fsys-tarfile','/mnt/c/projects.local/mobiam/build/etherlocation_0.1.0_arm64.deb'])
    with tarfile.open(fileobj=io.BytesIO(archive)) as tar:
        assert hashlib.sha256(tar.extractfile('./usr/libexec/etherlocation-qmi').read()).hexdigest()==acquisition['nativeSha256']
        for file,digest in source.items():
            if file.startswith('etherlocation/'):assert hashlib.sha256(tar.extractfile('./usr/share/'+file).read()).hexdigest()==digest
    artifacts=['build/etherlocation_0.1.0_arm64.deb','build/ethercamera_0.4.1_arm64.deb','build/etherhardware_0.1.1_arm64.deb','build/ethershell-location_2.1.0_arm64.deb','build/etherlocation-world-overview.mbtiles','evidence/etherlocation-hardware-audit.json','evidence/etherlocation-native-fix-test.json','evidence/etherlocation-runtime-verification.json','evidence/etherlocation-five-minute-test.json','evidence/etherlocation-hardware-integration.json','evidence/etherlocation-install.json','evidence/etherlocation-device/result.json','evidence/etherlocation-device/offline-map.png','evidence/etherlocation-shell-stage.json','evidence/etherlocation-shell-deployment.json','docs/etherlocation.rst','docs/etherlocation-feasibility-2026-10-20.rst','docs/etherlocation-delivery-2026-10-20.rst']
    artifacts+=['evidence/etherlocation-clear-sky-test.json','evidence/etherlocation-defaults-install.json','evidence/etherlocation-catalog-regression.json','evidence/etherlocation-settings-full-regression-device/acceptance.json']
    artifacts+=['evidence/etherlocation-quality-test.json','docs/etherlocation-followup-2026-10-21.rst','scripts/test-etherlocation-quality.py']
    result=dict(schemaVersion=1,task='08/11',version='0.1.0',deliveryDate='2026-10-21',releaseComplete=False,
        latestAcquisition=dict(successfulFixes=sum(e['event']=='fix' for e in quality['events']),positionReports=len(qualityReports),technologyMasks=sorted(set(e['technologyMask'] for e in qualityReports if 'technologyMask' in e)),maximumUncertaintyMetres=max([e['majorMetres'] for e in qualityReports if 'majorMetres' in e] or [0]),report='docs/etherlocation-followup-2026-10-21.rst'),
        delivered=['Real Qualcomm LOC/QRTR provider','Managed location API and backend permissions','Precise/approximate privacy transforms','Existing gpsd/GeoClue adapters','Native offline raster MBTiles viewer and licensed region storage/downloads','Optional bounded history and exports','Local geofencing','Opt-in camera GPS EXIF','Existing Settings and Quick Settings integration','Redacted diagnostics','ARM64 Debian packages and existing distributor catalogue entry'],
        defaults=dict(location=False,history=False,networkPositioning=False,background=False),
        currentUserConfiguration=device['state']['config'],
        internalGnssOperational=False,realFixObtained=any(e['event']=='fix' for e in events),
        maximumReportedSatellites=max([len(e['satellites']) for e in events if e['event']=='satellites'] or [0]),reportedConstellations=sorted(set(s['constellation'] for e in events if e['event']=='satellites' for s in e['satellites'] if s.get('constellation'))),
        tests=dict(locationHost=34,locationDevice=int(re.search(r'Ran (\d+) tests',installed['tests'])[1]),locationDeviceSkipped=1,cameraHost=39,cameraDevice=int(re.search(r'Ran (\d+) tests',installed['cameraTests'])[1]),hardwareHost=18,hardwareDevice=18,shellViews=['narrow','portrait','landscape','external'],liveApiDenials=len(device['negativeTests']),softwareOfflineMap=True,catalogCacheMigration=read('evidence/etherlocation-catalog-regression.json')['exit']==0),
        limitations=['No verified real GNSS fix; no operational claim','No outdoor/cold/warm acquisition acceptance','No attached external receiver test','Online GeoClue not exercised','Firefox/EtherBrowser origin bridge deferred; no browser grants bypassed','Routing and turn-by-turn navigation deferred','Physical geofence transitions and suspend/resume not accepted','Battery-only power measurements unavailable while USB-connected','Same-UID X11/direct hardware access is outside managed API isolation','No remote distributor publication or reboot acceptance'],
        noEtherFleetIntegration=True,sourceHashes=source,artifacts={p:dict(bytes=(ROOT/p).stat().st_size,sha256=sha(p)) for p in artifacts})
    (ROOT/'evidence/etherlocation-delivery.json').write_text(json.dumps(result,indent=2)+'\n',encoding='utf-8')
    print(json.dumps({k:v for k,v in result.items() if k not in ('artifacts','sourceHashes')},indent=2))
