#!/usr/bin/env python3
"""Audit a kernel .config for initial native Debian/Xorg prerequisites."""
import argparse
import gzip
import json
from pathlib import Path
import re

REQUIRED = {
    "CONFIG_VT": "Local LightDM/Xorg virtual-terminal allocation",
    "CONFIG_VT_CONSOLE": "Local virtual-terminal console and recovery",
    "CONFIG_DEVTMPFS": "Native Linux device-node provisioning",
    "CONFIG_UNIX98_PTYS": "Terminal emulators and remote shell PTYs",
    "CONFIG_INPUT_EVDEV": "Xorg libinput input events",
    "CONFIG_UNIX": "X11 UNIX sockets",
    "CONFIG_SYSVIPC": "X11 shared-memory facilities",
    "CONFIG_TMPFS": "Native runtime filesystem",
    "CONFIG_EXT4_FS": "Planned native root filesystem support",
}


def read_config(path):
    data = Path(path).read_bytes()
    if data.startswith(b"\x1f\x8b"):
        data = gzip.decompress(data)
    settings = {}
    for line in data.decode().splitlines():
        enabled = re.fullmatch(r"(CONFIG_\w+)=(.*)", line)
        disabled = re.fullmatch(r"# (CONFIG_\w+) is not set", line)
        if enabled:
            settings[enabled[1]] = enabled[2]
        elif disabled:
            settings[disabled[1]] = "n"
    return settings


def audit(settings):
    return {
        "scope": "Initial configuration prerequisites; not complete kernel/board validation",
        "missing": {key: reason for key, reason in REQUIRED.items() if settings.get(key) != "y"},
        "graphics": {key: settings.get(key, "absent") for key in
                     ("CONFIG_DRM", "CONFIG_DRM_MSM", "CONFIG_DRM_MSM_DSI_STAGING",
                      "CONFIG_QCOM_KGSL", "CONFIG_DRM_FBDEV_EMULATION")},
        "limitations": ["Kconfig does not prove GPU driver ABI, panel, touch or USB-C/DP support.",
                        "Verify firmware, device tree, runtime ioctls and visible physical output."],
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("config")
    parser.add_argument("--output")
    args = parser.parse_args()
    result = audit(read_config(args.config))
    text = json.dumps(result, indent=2) + "\n"
    if args.output:
        Path(args.output).write_text(text)
    print(text, end="")
    raise SystemExit(1 if result["missing"] else 0)
