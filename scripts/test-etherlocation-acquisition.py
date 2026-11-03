"""One bounded five-minute real acquisition attempt; never logs coordinates."""
from pathlib import Path
import argparse,json,runpy,subprocess
ROOT=Path(__file__).resolve().parent.parent
SSH=runpy.run_path(str(ROOT/'scripts/deploy-ethermobile.py'))['SSH']
SOURCE=r'''
import hashlib,json,pathlib,subprocess
backend='/usr/libexec/etherlocation-qmi'
p=subprocess.run(['runuser','-u','mobian','--','env','LANG=C.UTF-8',backend,'--test-seconds','300','--diagnostic'],capture_output=True,text=True,timeout=335)
events=[json.loads(line) for line in p.stdout.splitlines()]
print(json.dumps(dict(durationSeconds=300,exit=p.returncode,nativeSha256=hashlib.sha256(pathlib.Path(backend).read_bytes()).hexdigest(),events=events,stderr=p.stderr,coordinates='redacted',placement='Existing phone placement; no outdoor or cold-start assumption'),indent=2))
'''
if __name__=='__main__':
 parser=argparse.ArgumentParser();parser.add_argument('--clear-sky',action='store_true');args=parser.parse_args()
 if args.clear_sky:SOURCE=SOURCE.replace('Existing phone placement; no outdoor or cold-start assumption','User-confirmed clear sky view; no cold-start assumption')
 p=subprocess.run(SSH+['python3 -'],input=SOURCE.encode(),capture_output=True,timeout=350)
 if p.returncode:raise RuntimeError(p.stderr.decode(errors='replace'))
 data=json.loads(p.stdout);(ROOT/('evidence/etherlocation-clear-sky-test.json' if args.clear_sky else 'evidence/etherlocation-five-minute-test.json')).write_text(json.dumps(data,indent=2)+'\n',encoding='utf-8')
 print(json.dumps(dict(exit=data['exit'],fixes=sum(e['event']=='fix' for e in data['events']),satelliteReports=sum(e['event']=='satellites' for e in data['events']),maxReportedSatellites=max([len(e['satellites']) for e in data['events'] if e['event']=='satellites'] or [0]),resourcesReleased=any(e['event']=='released' for e in data['events'])),indent=2))
