"""Read-only, credential-free REST/MCP audit; only public data is retained."""
from pathlib import Path
import json
import sys
ROOT=Path(__file__).resolve().parent.parent
sys.path.insert(0,str(ROOT/'etherupdate'))
from provider import Provider


if __name__=='__main__':
    provider=Provider();projects=provider.projects()
    families=('etherpocket','ethershell','etherhardware','etherpower','etheraudio','etherphone','ethernotifications','etherlock','ethercamera','etherlocation','etherupdate','ethermobile','ethersms','ethershare','etherkeyboard')
    matching=[p for p in projects if any((p['slug'] or '').replace('-','').startswith(f) for f in families)]
    output=dict(projects=projects,etherpocketProjects=matching,mcp=provider.mcp_discover(),releases=[])
    # A real existing ARM64 release establishes the serializer independently of
    # the absence of public EtherPocket projects. It is never treated as eligible.
    for project in [p for p in projects if p['slug']=='etherprocess-linux-arm64']+matching:
        release=provider.latest(project['slug'],'Stable')
        if release:output['releases'].append(release.__dict__)
    (ROOT/'evidence/etherupdate-contract-audit.json').write_text(json.dumps(output,indent=2)+'\n',encoding='utf-8')
    print(json.dumps(dict(projects=len(projects),etherpocketProjects=len(matching),releases=len(output['releases']),tools=len(output['mcp']['tools']['tools']))))
