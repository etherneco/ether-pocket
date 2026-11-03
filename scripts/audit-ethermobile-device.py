"""Run the read-only Doctor over the existing pinned device SSH connection."""
from pathlib import Path
import argparse
import json
import subprocess

ROOT = Path(__file__).resolve().parent.parent
SSH = ['ssh', '-i', str(ROOT/'build/etherpocket_ed25519'), '-o',
       'UserKnownHostsFile='+str(ROOT/'build/mobian-known-hosts'), '-o',
       'BatchMode=yes', '-o', 'ConnectTimeout=8', 'root@10.77.0.2']

if __name__ == '__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output',type=Path)
    args=parser.parse_args()
    p = subprocess.run(SSH + ['python3 -'], input=(ROOT/'scripts/ethermobile-doctor.py').read_bytes(),
                       capture_output=True, check=True, timeout=150)
    data = json.loads(p.stdout)
    target = args.output or ROOT/'evidence'/('ethermobile-audit-' + data['time_utc'][:10] + '.json')
    target.write_text(json.dumps(data, indent=2) + '\n', encoding='utf-8')
    print(target)
    for stage in data['stages']:
        print(stage['status'] + ': ' + stage['stage'])
