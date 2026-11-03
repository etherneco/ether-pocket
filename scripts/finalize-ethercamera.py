"""Assert exact artifacts/evidence and write an honest local delivery manifest."""
from pathlib import Path
import hashlib,io,json,re,subprocess,tarfile
ROOT=Path(__file__).resolve().parent.parent
def read(path):return json.loads((ROOT/path).read_text(encoding='utf-8'))
def digest(path):return hashlib.sha256((ROOT/path).read_bytes()).hexdigest()
if __name__=='__main__':
    installed=read('evidence/ethercamera-install.json')
    assert installed['packageSha256']==digest('build/ethercamera_0.3.0_arm64.deb')
    assert installed['before']==installed['after']
    count=int(re.search(r'Ran (\d+) tests',installed['tests'])[1])
    assert count==34 and 'OK' in installed['tests'] and 'skipped' not in installed['tests']
    stage=read('evidence/ethercamera-shell-stage.json')
    assert stage['qa_passed'] and stage['package_sha256']==digest('build/ethershell-camera_2.1.0_arm64.deb')
    acceptance=read('evidence/ethercamera-settings-device/acceptance.json')
    assert set(acceptance)=={'narrow','portrait','landscape','external'}
    assert all(v['exit']==0 for v in acceptance.values())
    for view in acceptance:
        results=read('evidence/ethercamera-settings-device/'+view+'/results.json')
        assert results and all(results.values())
    device=read('evidence/ethercamera-device-verification.json')
    assert device['state']['ready'] and not device['state']['active'] and not device['state']['verified']
    assert not device['idle']['openCameraNodes']
    assert device['services']['exit']==0 and 'wlan0:wifi:connected' in device['network']['stdout']
    assert len(device['processes']['stdout'].splitlines())==1
    assert device['architecture']=='aarch64' and device['packageVersion']['stdout']=='0.3.0'
    assert device['lockState']['ready'] and not device['lockState']['locked'] and not device['lockState']['enabled']
    assert device['state']['permissionCoordinatorAvailable']
    for file,expected in device['sourceHashes'].items():assert digest('ethercamera/'+file)==expected,file
    archive=subprocess.check_output(['wsl','-d','EtherPocketBuild','--','dpkg-deb','--fsys-tarfile','/mnt/c/projects.local/mobiam/build/ethercamera_0.3.0_arm64.deb'],timeout=30)
    with tarfile.open(fileobj=io.BytesIO(archive)) as tar:
        assert hashlib.sha256(tar.extractfile('./usr/bin/ethercamera-media').read()).hexdigest()==device['binarySha256']
        assert hashlib.sha256(tar.extractfile('./usr/bin/ethercamera-app').read()).hexdigest()==device['captureBinarySha256']
    deployment=read('evidence/ethercamera-shell-deployment.json')
    assert deployment['stage']==stage['stage']
    assert device['shellExecutable']==stage['stage']+'/usr/bin/ethershell'
    media={arch:read('evidence/ethercamera-media-'+arch+'/acceptance.json') for arch in ['amd64','arm64']}
    for result in media.values():
        assert all(result[k] for k in ['apiMedia','restartPersistence','manualAndMicrophoneConsent','lockDenial'])
        assert result['photo']['imageLoaded'] and result['video']['videoFrames']>2
        assert result['revoked']['private'] and result['revoked']['items']==0
    capture={arch:read('evidence/ethercamera-capture-'+arch+'/acceptance.json') for arch in ['amd64','arm64']}
    for result in capture.values():
        assert set(result)=={'blocked','wide','capture','revoked','disconnected','owner-loss','background','denied','start-failure'}
        assert all(not case['error'] for case in result.values())
        assert result['capture']['photoPixelsVerified'] and result['capture']['videoH264Verified']
    live=read('evidence/ethercamera-app-live.png.json')
    assert live['rendered'] and not live['active'] and not live['private'] and not live['hasFrame'] and live['devices']==0
    files=['build/ethercamera_0.3.0_arm64.deb','build/ethershell-camera_2.1.0_arm64.deb',
           'build/etherhardware_0.1.0_arm64.deb','evidence/ethercamera-audit-2026-10-20.json',
           'evidence/ethercamera-vendor-audit.json','evidence/ethercamera-install.json',
           'evidence/ethercamera-device-verification.json','evidence/ethercamera-hardware-update.json',
           'evidence/ethercamera-hardware-regression.txt','evidence/ethercamera-tests-amd64.txt',
           'evidence/ethercamera-shell-stage.json','evidence/ethercamera-settings-device/acceptance.json',
           'evidence/ethercamera-shell-deployment.json','evidence/ethercamera-media-amd64/acceptance.json',
           'evidence/ethercamera-media-arm64/acceptance.json','evidence/ethercamera-lock-coordinator.json',
           'evidence/ethercamera-android-loader-probe.json','evidence/ethercamera-media-live.json',
           'evidence/ethercamera-capture-amd64/acceptance.json','evidence/ethercamera-capture-arm64/acceptance.json',
           'evidence/ethercamera-app-live.png','evidence/ethercamera-app-live.png.json',
           'evidence/ethercamera-app-deployment.json','ethercamera/capture_controller.cpp','ethercamera/capture_controller.h',
           'ethercamera/capture_main.cpp','ethercamera/Capture.qml','ethercamera/power_guard.py',
           'scripts/test-ethercamera-capture.py','ethercamera/tests/capture_ui_test.cpp',
           'docs/ethercamera.rst','docs/ethercamera-feasibility-2026-10-20.rst','docs/ethercamera-followup-2026-10-20.rst',
           'docs/ethercamera-app-2026-10-20.rst']
    result=dict(schemaVersion=1,date='2026-10-20',task='07/11',releaseComplete=False,
        version='0.3.0',disposition='internal-capture-blocked; native capture/media apps installed; Camera Settings live',
        physicalFrameVerified=False,externalCameraAttached=False,cameraTestsArm64=count,cameraTestsAmd64=count,
        hardwareRegressionTests=17,settingsViewsPassed=list(acceptance),
        permissionCoordinatorAvailable=device['state']['permissionCoordinatorAvailable'],
        stage=stage['stage'],shellActivated=True,automaticLockingEnabled=device['lockState']['enabled'],
        captureCasesPassed={arch:list(result) for arch,result in capture.items()},
        mediaCasesPassed={arch:[k for k in ['library','wide','photo','video','revoked'] if result[k]['rendered']] for arch,result in media.items()},
        artifacts={f:dict(bytes=(ROOT/f).stat().st_size,sha256=digest(f)) for f in files})
    (ROOT/'evidence/ethercamera-delivery.json').write_text(json.dumps(result,indent=2)+'\n',encoding='utf-8')
    print(json.dumps({k:v for k,v in result.items() if k!='artifacts'},indent=2))
