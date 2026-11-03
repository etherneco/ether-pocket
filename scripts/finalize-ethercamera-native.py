"""Bind the native rear-camera delivery to packages, sources and real evidence."""
from pathlib import Path
import hashlib,io,json,re,subprocess,tarfile
ROOT=Path(__file__).resolve().parent.parent
def read(name):return json.loads((ROOT/name).read_text(encoding='utf8'))
def sha(name):return hashlib.sha256((ROOT/name).read_bytes()).hexdigest()
def package_files(name):
    raw=subprocess.check_output(['wsl','-d','EtherPocketBuild','--','dpkg-deb','--fsys-tarfile','/mnt/c/projects.local/mobiam/'+name])
    result={}
    with tarfile.open(fileobj=io.BytesIO(raw)) as tar:
        for entry in tar:
            if entry.isfile():result[entry.name.removeprefix('./')]=hashlib.sha256(tar.extractfile(entry).read()).hexdigest()
    return result
if __name__=='__main__':
    camera='build/ethercamera_0.4.0_arm64.deb';driver='build/ethercamera-spectra_0.2.0_arm64.deb';audio='build/etheraudio_0.1.1_arm64.deb'
    installed=read('evidence/ethercamera-install.json');native=read('evidence/ethercamera-spectra-capture-install.json');sound=read('evidence/etheraudio-install.json')
    assert installed['packageSha256']==sha(camera) and native['packageSha256']==sha(driver) and sound['packageSha256']==sha(audio)
    assert installed['before']==installed['after'] and sound['before']==sound['after']
    assert 'Ran 36 tests' in installed['tests'] and 'OK' in installed['tests']
    assert 'Ran 22 tests' in sound['tests'] and 'OK' in sound['tests']
    state=read('evidence/ethercamera-device-verification.json');final=read('evidence/ethercamera-native-final-state.json')
    assert state['packageVersion']['stdout']=='0.4.0' and state['state']['ready'] and not state['state']['active']
    assert not state['idle']['openCameraNodes'] and not final['openCameraNodes']
    assert state['services']['exit']==0 and 'wlan0:wifi:connected' in state['network']['stdout']
    for name,digest in state['sourceHashes'].items():assert sha('ethercamera/'+name)==digest,name
    contents=package_files(camera);worker=package_files(driver)
    for name in state['sourceHashes']:assert contents['usr/share/ethercamera/'+name]==sha('ethercamera/'+name),name
    assert contents['usr/bin/ethercamera-app']==state['captureBinarySha256']
    assert worker['usr/libexec/ethercamera/ethercamera-spectra-capture']==final['workerSha256']
    assert final['owners']==read('evidence/ethercamera-spectra-rear-probe.json')['before']['services']
    ui=read('evidence/ethercamera-physical-ui/result.json');assert not ui['error']
    for key in ['physical camera available','JPEG fd displayed','photo saved','video finalized and released','consent required','cancel never starts capture']:assert ui[key],key
    av=read('evidence/ethercamera-spectra-av-playback.json');assert av['decodeExit']==0 and not av['decodeStderr']
    streams={s['codec_name']:s for s in av['streams']};assert set(streams)=={'h264','aac'}
    assert streams['h264']['pix_fmt']=='yuv420p' and int(streams['h264']['nb_frames'])>60
    assert abs(float(streams['h264']['duration'])-float(streams['aac']['duration']))<0.5
    for report in ['capture','media']:
        cases=read('evidence/ethercamera-'+report+'-arm64/acceptance.json')
        if report=='capture':assert len(cases)==9 and all(not r['error'] for r in cases.values())
    files=[camera,driver,audio,'evidence/ethercamera-install.json','evidence/etheraudio-install.json',
        'evidence/ethercamera-spectra-capture-install.json','evidence/ethercamera-device-verification.json',
        'evidence/ethercamera-native-final-state.json','evidence/ethercamera-physical-ui/result.json',
        'evidence/ethercamera-spectra-av-playback.json','evidence/ethercamera-rear-brightened.jpg',
        'evidence/ethercamera-rear-uncovered.jpg','evidence/ethercamera-spectra-final-arm64-tests.txt',
        'docs/ethercamera-spectra-driver-2026-10-20.rst']
    files += [str(p.relative_to(ROOT)).replace('\\','/') for p in (ROOT/'ethercamera/spectra').glob('*.cpp')]
    files += ['ethercamera/spectra/'+n for n in ['transport.h','image.h','module_profile.py','capture_profile.py','CMakeLists.txt']]
    result=dict(schemaVersion=2,date='2026-10-20',version='0.4.0',nativeDriverVersion='0.2.0',audioVersion='0.1.1',task='07/11',
        releaseComplete=False,basicRearCaptureImplemented=True,physicalFrameVerified=True,usableSceneInspected=True,
        disposition='Native rear IMX586 preview, photos and video implemented; full smartphone quality and Task 07 acceptance remain incomplete',
        physicalCamera='rear-main Sony IMX586, slot 0 / CSIPHY 1',rawMode=dict(width=4000,height=3000,bits=10,stride=5008),
        output=dict(width=640,height=480,videoOutputFps=15,videoMaximumSeconds=60,physicalFramesMayBeRepeated=True),
        lowLightProcessing='Black level subtraction, bounded automatic software gain/gamma and Bayer area averaging',
        tests=dict(cameraPythonAmd64=36,cameraPythonArm64=36,audioPython=22,nativeCppSuites=2,moduleParser=3,offlineCaptureUiArm64=9,physicalCaptureUi=True,audioVideoDecoded=True),
        unchangedSystemOwners=final['owners'],noCameraDescriptorsAfterTests=True,
        limitations=['Fixed sensor exposure and lens position; no autofocus','No calibrated colour/white balance, OIS, HDR or flash',
            'Other rear sensors and front pop-up unsupported','Orientation, physical label/document scanning and suspend/resume not accepted',
            'No native Spectra website bridge; no stock camera quality or full Task 07 acceptance'],
        artifacts={n:dict(bytes=(ROOT/n).stat().st_size,sha256=sha(n)) for n in files})
    target=ROOT/'evidence/ethercamera-delivery.json'
    previous=read('evidence/ethercamera-delivery.json')
    if previous.get('version')=='0.3.0':(ROOT/'evidence/ethercamera-0.3-delivery.json').write_text(json.dumps(previous,indent=2)+'\n',encoding='utf8')
    target.write_text(json.dumps(result,indent=2)+'\n',encoding='utf8')
    (ROOT/'evidence/ethercamera-spectra-delivery.json').write_text(json.dumps(result,indent=2)+'\n',encoding='utf8')
    print(json.dumps({k:v for k,v in result.items() if k!='artifacts'},indent=2))
