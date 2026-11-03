"""Read-only survey of the six requested application families."""
from pathlib import Path
import json
import runpy

root=Path(__file__).resolve().parent.parent
module=runpy.run_path(str(root/'scripts/inspect-autoupdate.py'))
MCP=module['MCP']
client=MCP()

def call(name,args):
    result=client.request('tools/call',{'name':name,'arguments':args})
    blocks=result.get('result',{}).get('content',[])
    for block in blocks:
        if block.get('type')=='text':
            try: return json.loads(block['text'])
            except ValueError: pass
    return result

projects=[]
for page in (1,2):
    data=call('autoupdate_api_request',{'method':'GET','path':'/api/manage/projects','query':{'page':page}})
    projects.extend(data.get('body',{}).get('data',[]))

families=('etherremote','ethermcp','etherdeck','etherair','ethertrust','etherfleet')
selected=[p for p in projects if any(f in p.get('slug','').lower().replace('-','') for f in families)]
report=[]
for project in selected:
    details=call('autoupdate_get_application',{'project_id':project['id']})
    report.append({'project':project,'details':details})
    print(json.dumps({k:project.get(k) for k in ('id','name','slug','platform','visibility')},ensure_ascii=True))
output=json.dumps(module['redact_payload'](report),indent=2,ensure_ascii=False).replace(client.secret['token'],'[REDACTED]')
(root/'build/autoupdate-survey.json').write_text(output,encoding='utf-8')
print(json.dumps({'projects_total':len(projects),'matched':len(selected)}))
