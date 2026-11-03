"""Verify only public endpoints, using the production client's explicit headers."""
import json
import runpy
import urllib.request
from pathlib import Path

root=Path(__file__).resolve().parent.parent
module=runpy.run_path(str(root/'scripts/inspect-autoupdate.py'))
opener=urllib.request.build_opener(module['SameOriginRedirects'])
base='https://autoupddate.etherneco.com'
results=[]
projects=[]
def get(path):
    req=urllib.request.Request(base+path,headers={'User-Agent':module['USER_AGENT'],'Accept':'application/json, text/event-stream','Content-Type':'application/json'})
    with opener.open(req,timeout=20) as response:
        result={'path':path,'status':response.status,'cf-ray':response.headers.get('cf-ray'),'body':module['redact_payload'](json.load(response))}
        results.append(result)
        print(json.dumps({k:result[k] for k in ('path','status','cf-ray')}))
        return result['body']
for page in (1,2): projects.extend(get('/api/projects?page='+str(page)).get('data',[]))
selected=[p for p in projects if any(x in p.get('slug','').replace('-','').lower() for x in ('etherremote','ethermcp','etherdeck','etherair','ethertrust','etherfleet'))]
for project in selected: get('/api/releases/check?project='+project['slug']+'&channel=Stable')
(root/'build/autoupdate-public-live.json').write_text(json.dumps({'projects':selected,'requests':results},indent=2),encoding='utf-8')
