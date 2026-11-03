#!/usr/bin/python3
"""Scoped PolicyKit helper for Debian diagnostic tools; no driver/firmware repair.

Root revalidates candidate and simulated transaction. Only fresh installs of the
reviewed tool set and explicitly reviewed libraries are allowed; no removals or
upgrades of existing packages. APT's normal authentication remains mandatory.
"""
import json
import os
import re
import sys
import subprocess
from core import command

TOOLS = {'iw': 'Read-only wireless capability inspection',
         'v4l-utils': 'Read-only video capability inspection',
         'mesa-utils': 'OpenGL/EGL inspection in your graphical session',
         'alsa-utils': 'ALSA inspection and explicit user media tests',
         'pulseaudio-utils': 'Session audio inspection and explicit user media tests'}
DEPENDENCIES = {'libv4l-0t64', 'libv4lconvert0t64', 'libv4l2rds0t64', 'libpci3',
    'libnl-3-200', 'libnl-genl-3-200', 'libasound2t64', 'libatopology2t64',
    'libfftw3-single3', 'libsamplerate0', 'libspeexdsp1', 'libpulsedsp',
    'mesa-utils-bin', 'libgl1', 'libegl1', 'libglu1-mesa', 'libglx0', 'libglvnd0',
    'libpulse0', 'libasyncns0', 'libsndfile1', 'libwrap0'}


def plan(package):
    if package not in TOOLS:
        raise ValueError('Package is outside the reviewed userspace tool list')
    code, arch = command(['dpkg', '--print-architecture'])
    if code or arch.strip() != 'arm64':
        raise ValueError('This repair policy is reviewed only for Debian ARM64')
    code, os_release = command(['dpkg-query', '-W', '-f=${Version}', 'base-files'])
    if code or not os_release.startswith('13'):
        raise ValueError('Debian 13 base-files is required')
    code, policy = command(['apt-cache', 'policy', package])
    match = re.search(r'Candidate:\s+(\S+)', policy)
    candidate = match.group(1) if match else ''
    if code or not candidate or candidate == '(none)' or not re.fullmatch(r'[\w.+:~\-]+', candidate):
        raise ValueError('No authenticated repository candidate is available')
    # Restrict package source to Debian trixie; do not trust arbitrary third-party binaries.
    block = re.search(r'^[ ]{1,5}(?:\*\*\*\s*)?' + re.escape(candidate) + r'\s+\d+\n((?:[ ]{8}[^\n]+\n?)*)', policy, re.M)
    if not block or not re.search(r'https?://(?:deb\.debian\.org/debian|security\.debian\.org/debian-security)\s+trixie(?:[-/\w]*)', block.group(1)):
        raise ValueError('Candidate must come from the configured Debian trixie repositories')
    code, simulation = command(['apt-get', '--simulate', '--no-remove', '--no-install-recommends',
                               'install', package + '=' + candidate], timeout=20)
    if code or re.search(r'^Remv ', simulation, re.M):
        raise ValueError('APT cannot safely resolve this transaction')
    installs = re.findall(r'^Inst (\S+)(?:\s+\[([^\]]+)\])?\s+\(([^ ]+)', simulation, re.M)
    for name, old, version in installs:
        if name.split(':')[0] not in TOOLS.keys() | DEPENDENCIES or old:
            raise ValueError('Transaction would modify existing or unreviewed packages; use separate maintenance')
    return {'package': package, 'candidate': candidate, 'purpose': TOOLS[package],
            'architecture': 'arm64', 'transaction': [{'package': n, 'version': v} for n, old, v in installs],
            'requirements': 'Administrator authentication; authenticated Debian repository; no kernel/vendor firmware changes',
            'alreadyInstalled': not installs}


def main():
    if os.geteuid() == 0:
        os.environ.clear()
        os.environ.update(PATH='/usr/sbin:/usr/bin:/sbin:/bin', LC_ALL='C',
                          DEBIAN_FRONTEND='noninteractive', HOME='/root')
    try:
        if len(sys.argv) == 2 and sys.argv[1] == '--list':
            print(json.dumps(TOOLS))
            return
        if len(sys.argv) == 3 and sys.argv[1] == '--plan':
            print(json.dumps(plan(sys.argv[2])))
            return
        if len(sys.argv) != 3 or os.geteuid() != 0:
            raise ValueError('Usage: etherhardware-repair PACKAGE REVIEWED_VERSION (through PolicyKit)')
        package, reviewed = sys.argv[1:]
        reviewed_plan = plan(package)
        if reviewed_plan['candidate'] != reviewed:
            raise ValueError('Candidate changed; review the new plan')
        argv = ['apt-get', '--assume-yes', '--no-remove', '--no-upgrade', '--no-install-recommends',
                '-o', 'APT::Get::AllowUnauthenticated=false',
                '-o', 'Acquire::AllowInsecureRepositories=false', 'install', package + '=' + reviewed]
        # Never kill APT/dpkg midway through an authorized transaction.
        code = subprocess.run(argv, stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL,
                              stderr=subprocess.DEVNULL).returncode
        print(json.dumps({'success': code == 0, 'package': package,
                          'message': 'Installation completed; recheck hardware' if code == 0 else 'APT failed; inspect the system package log'}))
        if code:
            sys.exit(1)
    except ValueError as e:
        print(json.dumps({'success': False, 'message': str(e)}))
        sys.exit(2)


if __name__ == '__main__':
    main()
