"""Isolated interpreter entry point with a fixed, root-installed module path."""
import os
import runpy
import sys
sys.path.insert(0, '/usr/share/ethercredentials')
# RuntimeDirectory is recreated by systemd; remove stale socket after a crash.
try:
    os.unlink('/run/ethercredentials/control')
except FileNotFoundError:
    pass
runpy.run_module('service', run_name='__main__')
