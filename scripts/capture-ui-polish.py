"""Capture the real phone through the EtherPocket Control agent."""
from pathlib import Path
import io,json,subprocess,sys
ROOT=Path(__file__).resolve().parent.parent
sys.path.insert(0,str(ROOT/'etherpocket-control'))
from transport import frames,ssh_command
from PIL import Image
ssh=ssh_command('10.77.0.2',ROOT/'build/etherpocket_ed25519',ROOT/'build/mobian-known-hosts')
p=subprocess.Popen(ssh+['exec runuser -u mobian -- env DISPLAY=:0 XAUTHORITY=/home/mobian/.Xauthority python3 /usr/local/lib/etherpocket-control/agent.py 2'],stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=subprocess.PIPE)
try:
 metadata=json.loads(p.stdout.readline())
 if len(sys.argv)==4:
  for event in [dict(type='move',x=int(sys.argv[2]),y=int(sys.argv[3])),dict(type='button',button=1,down=True),dict(type='button',button=1,down=False)]:
   p.stdin.write((json.dumps(event)+'\n').encode());p.stdin.flush()
 stream=frames(p.stdout)
 for _ in range(3):jpeg=next(stream)
 image=Image.open(io.BytesIO(jpeg));image.load()
 target=ROOT/'evidence/ui-polish'/('live-'+sys.argv[1]+'.png');image.save(target)
 p.stdin.write(b'{"type":"stop"}\n');p.stdin.flush()
 p.communicate(timeout=8)
 print(json.dumps(dict(capture=str(target),display=metadata,exit=p.returncode)))
finally:
 if p.poll() is None:p.kill();p.wait()
