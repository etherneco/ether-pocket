#!/usr/bin/python3
"""Keep the downstream modem subsystem available for its WLAN protection domain."""
import os
import signal

fd = os.open('/dev/subsys_modem', os.O_RDONLY)
while True:
    signal.pause()
