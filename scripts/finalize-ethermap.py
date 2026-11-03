"""Record exact local deliverables and outstanding Task 12 acceptance gates."""
import hashlib
import json
from pathlib import Path
import re

ROOT=Path(__file__).resolve().parents[1]
def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()
def log(name):return (ROOT/'build'/name).read_text(encoding='utf-8')

if __name__=='__main__':
    ui=json.loads((ROOT/'evidence/ethermap-native/result.json').read_text())
    assert all(v['exit']==0 and v['screenshot'] and not v['stderr'] for v in ui['views'].values())
    assert ui['interactions']['exit']==0 and ui['locationService']['exit']==0
    assert 'PASS:' in log('ethermap-catalog-native.log')
    tests={}
    for key,name in [('maps','ethermap-tests.log'),('location','ethermap-location-tests.log')]:
        data=log(name);assert '\nOK' in data and 'FAILED' not in data
        tests[key]=int(re.search(r'Ran (\d+) tests',data)[1])
    artifacts=['build/ethermap_0.1.0_arm64.deb','build/etherlocation_0.1.1_arm64.deb','build/ethershell-map_2.1.0_arm64.deb','build/ethermap-westminster-osm.mbtiles','build/ethermap-westminster.osm','docs/ethermap.rst','evidence/ethermap-native/result.json','evidence/ethermap-osm-dataset.json','evidence/ethermap-package-verification.json','build/ethermap-tests.log','build/ethermap-location-tests.log','build/ethermap-catalog-native.log','build/ethermap-build.log','build/etherlocation-map-build.log','build/ethermap-shell-build.log']
    artifacts += ['evidence/ethermap-native/'+n+'.png' for n in ui['views']]
    source=list((ROOT/'ethermap').rglob('*.py'))+list((ROOT/'ethermap').glob('*.qml'))+list((ROOT/'ethermap').glob('*.cpp'))+list((ROOT/'ethermap').glob('*.txt'))
    source += [ROOT/p for p in ['etherlocation/core.py','etherlocation/service.py','etherlocation/identity.py','etherlocation/ip_provider.py','etherlocation/tiles.h','etherlocation/map_main.cpp','etherlocation/LocationPage.qml','etherlocation/CMakeLists.txt','ethershell/src/distributor.cpp','scripts/build-ethermap.sh','scripts/build-etherlocation.sh','scripts/test-ethermap-native.py','scripts/prepare-ethermap-osm-region.py']]
    result=dict(schemaVersion=1,task='12',date='2026-10-21',application='EtherMAP',version='0.1.0',releaseComplete=False,deviceInstalled=False,remotePublished=False,
        implemented=['Actual OSM raster map rendering with Qt6 and shared EtherLocation MBTiles renderer','Pan/zoom/rotation, device accuracy regions, separate manual/saved markers and segmented trails','EtherLocation-only device positioning and opt-in parallel GeoClue fallback','Consented asynchronous IP estimates, cached/stale attribution, timeout and rate limits','Follow mode, explicit private local recording, segmented SQLite tracks and GPX import/export','Licensed offline MBTiles import/checksummed transfer/pause/Range resume/storage/deletion','Offline coordinate/place searches and configurable consented Nominatim geocoding','Profile-specific consented OSRM routing with real route geometry and maneuvers','Approximate/precise permission boundary, lock masking, foreground/background grants, suspend gaps, stationary/saver intervals','Existing notifications, launcher, Location settings and distributor catalogue integration'],
        defaults=dict(history=False,background=False,precise=False,ipConsent=False,onlineTiles=False,externalSearchRouting=False),
        tests=dict(**tests,nativeViews=list(ui['views']),nativeInteractionChecks=7,realOfflineOSM=True,networkDisabled=True,realIsolatedLocationService=True,catalogCacheMigration=True),
        blockers=['Phone SSH connection closed before authentication at 10.77.0.2; no device installation attempted','No verified internal or external GNSS fix or physical movement/suspend/battery/boot regression acceptance','No commissioned production IP/geocoding/routing endpoints or real VPN acceptance','Repository EtherUpdate policy has no commissioned component mappings or trusted publisher keys; no signed remote publication','MapLibre vector renderer, vector datasets, graphical area download selection and offline routing/navigation are not implemented','GeoClue cannot independently identify Wi-Fi versus cellular provenance; no separate database/scanner is claimed'],
        noGoogleMaps=True,noEtherFleetIntegration=True,
        sourceHashes={str(p.relative_to(ROOT)).replace('\\','/'):sha(p) for p in source},
        artifacts={p:dict(bytes=(ROOT/p).stat().st_size,sha256=sha(ROOT/p)) for p in artifacts})
    installed=ROOT/'evidence/ethermap-device-install.json'
    if installed.exists():
        deployment=json.loads(installed.read_text())
        device=json.loads((ROOT/'evidence/ethermap-device/result.json').read_text())
        live=json.loads((ROOT/'evidence/ethermap-live/result.json').read_text())
        shell=json.loads((ROOT/'evidence/ethermap-shell-deployment.json').read_text())
        stage=json.loads((ROOT/'evidence/ethermap-shell-stage.json').read_text())
        assert deployment['hashes']['ethermap.deb']==sha(ROOT/'build/ethermap_0.1.0_arm64.deb')
        assert deployment['hashes']['etherlocation.deb']==sha(ROOT/'build/etherlocation_0.1.1_arm64.deb')
        assert deployment['servicesUnchanged'] and stage['qa_passed'] and shell['stage']==stage['stage']
        assert stage['package_sha256']==sha(ROOT/'build/ethershell-map_2.1.0_arm64.deb')
        assert all(v['exit']==0 and not v['stderr'] for v in device['views'].values())
        assert live['identity']=='ethermap' and not live['trackDatabaseCreated'] and all(s=='active' for s in live['services'])
        result['deviceInstalled']=True
        result['deviceAcceptance']=dict(versions=device['packages'],views=list(device['views']),apiDenials=len(device['negativeTests']),shellStage=shell['stage'],liveProcess=live['pid'],historyCreated=live['locationHistoryCreated'],tracksCreated=live['trackDatabaseCreated'],servicesPreserved=True)
        result['tests']['deviceSuites']={name:int(re.search(r'Ran (\d+) tests',data)[1]) for name,data in deployment['tests'].items()}
        result['blockers']=[b for b in result['blockers'] if not b.startswith('Phone SSH')]
        for name in ['evidence/ethermap-device-audit.json','evidence/ethermap-device-install-initial.json','evidence/ethermap-device-install.json','evidence/ethermap-device/result.json','evidence/ethermap-live/result.json','evidence/ethermap-live/live-map.png','evidence/ethermap-shell-stage.json','evidence/ethermap-shell-deployment.json','evidence/ethermap-settings-device/acceptance.json','docs/ethermap-device-delivery-2026-10-21.rst']:
            path=ROOT/name;result['artifacts'][name]=dict(bytes=path.stat().st_size,sha256=sha(path))
        for name in ['scripts/deploy-ethermap.py','scripts/stage-ethermap-shell.py','scripts/activate-ethermap-shell.py','scripts/verify-ethermap-device.py','scripts/launch-ethermap-device.py']:
            result['sourceHashes'][name]=sha(ROOT/name)
    target=ROOT/'evidence/ethermap-delivery.json';target.write_text(json.dumps(result,indent=2)+'\n',encoding='utf-8')
    print(json.dumps({k:result[k] for k in ('releaseComplete','deviceInstalled','remotePublished','tests','blockers')},indent=2))
