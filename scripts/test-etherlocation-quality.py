"""Build a separate redacted probe; never replace the installed GNSS provider."""
from pathlib import Path
import collections, hashlib, json, runpy, subprocess

ROOT = Path(__file__).resolve().parent.parent
SSH = runpy.run_path(str(ROOT/'scripts/deploy-ethermobile.py'))['SSH']
PROBE = ROOT/'build/etherlocation-quality-probe'
EXTRA = r'''
  QJsonObject quality{{"event","report-quality"}};
  gfloat major,minor,pdop,hdop,vdop; guint64 stamp; guint8 confidence;
  QmiLocReliability reliability; QmiLocTechnologyUsed technology; GArray *used=nullptr;
  if(qmi_indication_loc_position_report_output_get_horizontal_uncertainty_elliptical_major(output,&major,nullptr)&&std::isfinite(major))quality["majorMetres"]=major;
  if(qmi_indication_loc_position_report_output_get_horizontal_uncertainty_elliptical_minor(output,&minor,nullptr)&&std::isfinite(minor))quality["minorMetres"]=minor;
  if(qmi_indication_loc_position_report_output_get_utc_timestamp(output,&stamp,nullptr))quality["ageSeconds"]=g_get_real_time()/1e6-stamp/1000.;
  if(qmi_indication_loc_position_report_output_get_horizontal_confidence(output,&confidence,nullptr))quality["confidencePercent"]=confidence;
  if(qmi_indication_loc_position_report_output_get_horizontal_reliability(output,&reliability,nullptr))quality["reliability"]=qmi_loc_reliability_get_string(reliability);
  if(qmi_indication_loc_position_report_output_get_technology_used(output,&technology,nullptr))quality["technologyMask"]=int(technology);
  if(qmi_indication_loc_position_report_output_get_satellites_used(output,&used,nullptr)&&used)quality["satellitesUsed"]=int(used->len);
  if(qmi_indication_loc_position_report_output_get_dop(output,&pdop,&hdop,&vdop,nullptr)&&std::isfinite(hdop))quality["hdop"]=hdop;
  send(quality);
'''

if __name__ == '__main__':
    PROBE.mkdir(exist_ok=True)
    source=(ROOT/'etherlocation/qmi_gnss.cpp').read_text(encoding='utf-8')
    assert source.count(' if(diagnostic){') == 1
    (PROBE/'probe.cpp').write_text(source.replace(' if(diagnostic){',' if(diagnostic){'+EXTRA),encoding='utf-8',newline='\n')
    (PROBE/'CMakeLists.txt').write_text('''cmake_minimum_required(VERSION 3.16)
project(GnssQualityProbe LANGUAGES CXX)
set(CMAKE_CXX_STANDARD 17)
find_package(Qt6 REQUIRED COMPONENTS Core)
find_package(PkgConfig REQUIRED)
pkg_check_modules(QMI REQUIRED IMPORTED_TARGET qmi-glib qrtr-glib)
add_executable(probe probe.cpp)
target_link_libraries(probe PRIVATE Qt6::Core PkgConfig::QMI)
''',encoding='utf-8',newline='\n')
    subprocess.run(['wsl','-d','EtherPocketBuild','--','cmake','-S','/mnt/c/projects.local/mobiam/build/etherlocation-quality-probe','-B','/opt/etherpocket/gnss-quality-probe','-G','Ninja','-DCMAKE_TOOLCHAIN_FILE=/mnt/c/projects.local/mobiam/ethershell/cmake/debian-arm64.cmake'],check=True)
    subprocess.run(['wsl','-d','EtherPocketBuild','--','cmake','--build','/opt/etherpocket/gnss-quality-probe'],check=True)
    subprocess.run(['wsl','-d','EtherPocketBuild','--','cp','/opt/etherpocket/gnss-quality-probe/probe','/mnt/c/projects.local/mobiam/build/etherlocation-quality-probe/probe'],check=True)
    binary=(PROBE/'probe').read_bytes(); digest=hashlib.sha256(binary).hexdigest()
    remote='/tmp/etherlocation-quality-'+digest[:16]
    subprocess.run(SSH+['umask 077; cat > '+remote+'; chmod 755 '+remote],input=binary,check=True)
    script=r'''
import collections,hashlib,json,pathlib,subprocess
probe=PROBE
try:
 assert hashlib.sha256(pathlib.Path(probe).read_bytes()).hexdigest()==DIGEST
 assert subprocess.run(['pgrep','-f','^/usr/libexec/etherlocation-qmi'],capture_output=True).returncode==1,'GNSS is already in use'
 p=subprocess.run(['runuser','-u','mobian','--',probe,'--diagnostic','--test-seconds','300'],capture_output=True,text=True,timeout=335)
 events=[json.loads(line) for line in p.stdout.splitlines()]
 print(json.dumps(dict(durationSeconds=300,exit=p.returncode,probeSha256=DIGEST,coordinates='redacted',events=events,stderr=p.stderr)))
finally:pathlib.Path(probe).unlink(missing_ok=True)
'''.replace('PROBE',repr(remote)).replace('DIGEST',repr(digest))
    p=subprocess.run(SSH+['python3 -'],input=script.encode(),capture_output=True,timeout=350,check=True)
    data=json.loads(p.stdout)
    assert data['exit']==0 and any(e['event']=='released' for e in data['events'])
    (ROOT/'evidence/etherlocation-quality-test.json').write_text(json.dumps(data,indent=2)+'\n',encoding='utf-8')
    quality=[e for e in data['events'] if e['event']=='report-quality']
    summary=dict(fixes=sum(e['event']=='fix' for e in data['events']),reports=len(quality),statusCounts=dict(collections.Counter(e['status'] for e in data['events'] if e['event']=='report-validity')))
    for field in ['majorMetres','minorMetres','ageSeconds','confidencePercent','reliability','technologyMask','satellitesUsed','hdop']:
        values=[e[field] for e in quality if field in e]
        summary[field]=dict(min=min(values),max=max(values)) if values else None
    print(json.dumps(summary,indent=2))
