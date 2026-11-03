"""Build-host Qt checks. Fixtures contain diagnostic metadata only, never matches."""
import json
import os
from pathlib import Path
import shutil
import subprocess

ROOT = Path(__file__).resolve().parents[1]
binary = '/opt/etherpocket/etherfingerprint-ui-test/fingerprint-ui-check'
out = ROOT/'evidence/etherfingerprint-manager-ui'
out.mkdir(exist_ok=True)
results = {}
cases = [(str(width)+'-'+theme, width, height, {'FP_TEST_DARK': '1'} if theme == 'dark' else {})
         for width, height in [(320,800),(360,800),(480,960),(1000,600),(1920,1080)] for theme in ['light','dark']]
cases += [('large-text',360,800,{'FP_TEST_LARGE_TEXT':'1'}),
          ('service-unavailable',360,800,{'FP_TEST_SERVICE_GONE':'1'}),
          ('sensor-unavailable',360,800,{'FP_TEST_NO_SENSOR':'1'}),
          ('motion-enabled',360,800,{'FP_TEST_MOTION':'1'}),
          ('scaled-symbol',360,800,{'FP_TEST_SCALE':'3.6'})]
for name,width,height,extra in cases:
    env = dict(os.environ, QT_QPA_PLATFORM='offscreen', QT_QUICK_BACKEND='software', LANG='C.UTF-8', **extra)
    p = subprocess.run([binary,str(ROOT/'etherfingerprint'),str(width),str(height)],env=env,capture_output=True,text=True)
    results[name] = {'exit':p.returncode,'log':p.stdout+p.stderr}
    source = ROOT/'etherfingerprint/tests/ui'/('preview-'+str(width)+('-dark' if extra.get('FP_TEST_DARK') else '-light')+'.png')
    if source.exists(): shutil.copyfile(source,out/(name+'.png'))
    print(name+': '+str(p.returncode),flush=True)
(out/'results.json').write_text(json.dumps(results,indent=2)+'\n')
assert all(v['exit']==0 for v in results.values()), results
