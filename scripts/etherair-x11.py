#!/usr/bin/env python3
"""EtherAIR X11 integration tools. Uses the logged-in user's X authority."""
import argparse
import json
import logging
import os
from pathlib import Path
import re
import subprocess
import time

LOG = logging.getLogger("etherair-x11")


def run(argv, check=True):
    result = subprocess.run(argv, text=True, capture_output=True, timeout=20)
    if check and result.returncode:
        raise RuntimeError(f"{argv[0]} failed: {result.stderr.strip()}")
    return result


def require_x11():
    # An environment value alone does not prove an actual Xorg server. Diagnose
    # also captures loginctl, X server vendor and process names for review.
    if os.environ.get("XDG_SESSION_TYPE") != "x11" or not os.environ.get("DISPLAY"):
        raise RuntimeError("Run inside the native X11 session (XDG_SESSION_TYPE=x11).")
    if os.environ.get("WAYLAND_DISPLAY"):
        raise RuntimeError("A Wayland display is active; native Xorg is required.")


def parse_outputs(text):
    outputs = []
    current = None
    for line in text.splitlines():
        match = re.match(r"^(\S+) (connected|disconnected)\b(.*)", line)
        if match:
            name, status, rest = match.groups()
            geometry = re.search(r"(\d+)x(\d+)\+(\d+)\+(\d+)", rest)
            current = {"name": name, "connected": status == "connected",
                       "primary": "primary" in rest.split(), "modes": [],
                       "preferred": None, "current_mode": None,
                       "geometry": tuple(map(int, geometry.groups())) if geometry else None}
            outputs.append(current)
        elif current:
            mode = re.match(r"^\s+(\d+x\d+\S*)\s+(.+)", line)
            if mode:
                current["modes"].append(mode[1])
                if "+" in mode[2]:
                    current["preferred"] = mode[1]
                if "*" in mode[2]:
                    current["current_mode"] = mode[1]
    return outputs


def snapshot():
    return parse_outputs(run(["xrandr", "--query"]).stdout)


def choose_outputs(outputs, internal=None, external=None):
    connected = [o for o in outputs if o["connected"]]
    phones = [o for o in connected if o["name"] == internal] if internal else [
        o for o in connected if re.match(r"^(DSI|eDP|LVDS)(-|\d)", o["name"])]
    if len(phones) != 1:
        raise RuntimeError("Cannot identify one phone panel; specify --internal from xrandr --query.")
    phone = phones[0]
    others = [o for o in connected if o is not phone and
              not o["name"].lower().startswith("virtual")]
    if external:
        others = [o for o in others if o["name"] == external]
        if not others:
            raise RuntimeError(f"Requested external output {external} is not connected.")
    if len(others) > 1:
        raise RuntimeError("Multiple external outputs; specify --external. EDID identity is not assumed.")
    return phone, others[0] if others else None


def preferred_mode(output):
    if "1920x1080" in output["modes"]:
        return "1920x1080"
    if output["preferred"]:
        return output["preferred"]
    raise RuntimeError(f"{output['name']} has no advertised preferred mode.")


def display_command(outputs, layout="extend", internal=None, external=None, rotation="normal"):
    phone, glasses = choose_outputs(outputs, internal, external)
    mode = ["--mode", phone["current_mode"]] if phone.get("current_mode") else ["--auto"]
    argv = ["xrandr", "--output", phone["name"], *mode, "--primary", "--rotate", rotation,
            "--pos", "0x0", "--scale", "1x1", "--transform", "none"]
    if glasses:
        argv += ["--output", glasses["name"], "--mode", preferred_mode(glasses),
                 "--rotate", "normal", "--scale", "1x1", "--transform", "none"]
        if layout == "mirror":
            # Same origin alone crops when resolutions differ. Scale the phone
            # framebuffer to the external output to mirror the entire desktop.
            if not phone["geometry"]:
                raise RuntimeError("Enable the phone panel before selecting mirror mode.")
            if not phone.get("current_mode"):
                raise RuntimeError("Cannot determine the panel's current advertised mode.")
            dimensions = re.match(r"^(\d+)x(\d+)", phone["current_mode"])
            if not dimensions:
                raise RuntimeError("Cannot determine the advertised panel mode dimensions.")
            width, height = map(int, dimensions.groups())
            if rotation in ("left", "right"):
                width, height = height, width
            argv += ["--scale-from", f"{width}x{height}", "--same-as", phone["name"]]
        else:
            argv += ["--right-of", phone["name"]]
    for output in outputs:
        if not output["connected"] and output["geometry"]:
            argv += ["--output", output["name"], "--off"]
    return argv


def apply_display(args):
    command = display_command(snapshot(), args.layout, args.internal, args.external, args.rotation)
    if args.dry_run:
        print(json.dumps(command))
    else:
        run(command)
        if args.touch:
            phone, _ = choose_outputs(snapshot(), args.internal, args.external)
            map_touch(args.touch, phone["name"], args.rotation, args.calibration)


ROTATIONS = {
    "normal": (1, 0, 0, 0, 1, 0, 0, 0, 1),
    "left": (0, -1, 1, 1, 0, 0, 0, 0, 1),
    "right": (0, 1, 0, -1, 0, 1, 0, 0, 1),
    "inverted": (-1, 0, 1, 0, -1, 1, 0, 0, 1),
}


def multiply(a, b):
    return tuple(sum(a[row * 3 + k] * b[k * 3 + col] for k in range(3))
                 for row in range(3) for col in range(3))


def touch_matrix(geometry, screen, rotation, calibration=ROTATIONS["normal"]):
    width, height, x, y = geometry
    sw, sh = screen
    region = (width / sw, 0, x / sw, 0, height / sh, y / sh, 0, 0, 1)
    return multiply(multiply(region, ROTATIONS[rotation]), calibration)


def map_touch(device, output, rotation, calibration=ROTATIONS["normal"]):
    text = run(["xrandr", "--query"]).stdout
    monitor = next((o for o in parse_outputs(text) if o["name"] == output), None)
    screen = re.search(r"current (\d+) x (\d+)", text)
    if not monitor or not monitor["geometry"] or not screen:
        raise RuntimeError("Touch mapping requires an active output and framebuffer geometry.")
    values = touch_matrix(monitor["geometry"], tuple(map(int, screen.groups())), rotation, calibration)
    run(["xinput", "set-prop", device, "Coordinate Transformation Matrix", *map(str, values)])


def resume_clock():
    # Linux CLOCK_MONOTONIC excludes suspended time; BOOTTIME includes it.
    if hasattr(time, "CLOCK_BOOTTIME"):
        return time.clock_gettime(time.CLOCK_BOOTTIME)
    return time.time()


def watch(args):
    previous = None
    last_time = resume_clock()
    while True:
        try:
            outputs = snapshot()
            # Ignore changing positions; watch connector state and EDID modes.
            state = tuple((o["name"], o["connected"], tuple(o["modes"])) for o in outputs)
            now = resume_clock()
            resumed = now - last_time > args.interval * 3
            last_time = now
            if state != previous or resumed:
                apply_display(args)
                previous = state  # A failed change is retried on the next poll.
                LOG.info("Applied %s layout", args.layout)
        except (RuntimeError, OSError, subprocess.TimeoutExpired) as error:
            LOG.warning("Display setup blocked: %s", error)
        time.sleep(args.interval)


def renderer_status(text):
    line = re.search(r"OpenGL renderer string:\s*(.+)", text)
    if not line:
        return "unverified"
    renderer = line[1].lower()
    if any(word in renderer for word in ("llvmpipe", "softpipe", "swrast", "software")):
        return "software-rendering-limitation"
    if ("adreno" in renderer or "fd640" in renderer) and "direct rendering: Yes" in text:
        return "adreno-candidate-review-kernel-and-xorg-logs"
    return "unverified-renderer"


def power_report():
    report = {}
    for base, attrs in (("/sys/class/power_supply", ("type", "status", "capacity", "temp")),
                        ("/sys/class/thermal", ("type", "temp"))):
        for node in Path(base).glob("*"):
            values = {}
            for attr in attrs:
                try:
                    values[attr] = (node / attr).read_text().strip()
                except OSError:
                    pass
            if values:
                report[str(node)] = values
    return report


def diagnose(args):
    commands = {
        "kernel": ["uname", "-a"], "architecture": ["dpkg", "--print-architecture"],
        "glxinfo": ["glxinfo", "-B"], "eglinfo": ["eglinfo"],
        "xrandr": ["xrandr", "--query"], "providers": ["xrandr", "--listproviders"],
        "xinput": ["xinput", "list"], "extensions": ["xdpyinfo", "-queryExtensions"],
        "ewmh": ["xprop", "-root", "_NET_SUPPORTED", "_NET_NUMBER_OF_DESKTOPS"],
        "workspaces": ["wmctrl", "-d"], "processes": ["ps", "-eo", "comm,args"],
        "drm": ["ls", "-l", "/dev/dri"], "kernel_logs": ["journalctl", "-b", "-k", "--no-pager"],
        "lightdm_logs": ["journalctl", "-b", "-u", "lightdm", "--no-pager"],
    }
    session = os.environ.get("XDG_SESSION_ID")
    if session:
        commands["login_session"] = ["loginctl", "show-session", session,
                                      "-p", "Type", "-p", "Remote", "-p", "Seat"]
    report = {"session_type": os.environ.get("XDG_SESSION_TYPE"), "commands": {},
              "power": power_report(), "acceptance": "manual-physical-validation-required"}
    for name, command in commands.items():
        try:
            result = run(command, check=False)
            report["commands"][name] = {"returncode": result.returncode,
                                        "stdout": result.stdout, "stderr": result.stderr}
        except (OSError, subprocess.TimeoutExpired) as error:
            report["commands"][name] = {"error": str(error)}
    report["gpu"] = renderer_status(report["commands"].get("glxinfo", {}).get("stdout", ""))
    report["connectors"] = {}
    for connector in Path("/sys/class/drm").glob("card*-*"):
        values = {}
        for attr in ("status", "modes", "enabled"):
            try:
                values[attr] = (connector / attr).read_text()
            except OSError as error:
                values[attr] = {"error": str(error)}
        report["connectors"][connector.name] = values
    report["xorg_logs"] = {}
    candidates = list(Path("/var/log").glob("Xorg.*.log"))
    candidates += list((Path.home() / ".local/share/xorg").glob("Xorg.*.log"))
    for path in candidates:
        try:
            report["xorg_logs"][str(path)] = path.read_text(errors="replace")
        except OSError as error:
            report["xorg_logs"][str(path)] = {"error": str(error)}
    Path(args.output).write_text(json.dumps(report, indent=2) + "\n")
    print(f"Evidence saved to {args.output}; GPU: {report['gpu']}")


def mobile(args):
    run(["xfconf-query", "-c", "xsettings", "-p", "/Xft/DPI", "-n", "-t", "int", "-s", str(args.dpi)])
    run(["xfconf-query", "-c", "xfce4-desktop", "-p", "/desktop-icons/icon-size",
         "-n", "-t", "uint", "-s", str(args.icon_size)])
    run(["wmctrl", "-n", str(args.workspaces)])
    print(f"DPI and {args.icon_size}px desktop icons set. Use EtherPocket launcher or onboard for X11 keyboard.")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="action", required=True)
    for name in ("display", "watch"):
        command = sub.add_parser(name)
        command.add_argument("--layout", choices=("extend", "mirror"), default="extend")
        command.add_argument("--internal")
        command.add_argument("--external")
        command.add_argument("--touch", help="Exact xinput device name or numeric ID")
        command.add_argument("--rotation", choices=ROTATIONS, default="normal")
        command.add_argument("--calibration", nargs=9, type=float, default=ROTATIONS["normal"])
        command.add_argument("--dry-run", action="store_true")
        if name == "watch":
            command.add_argument("--interval", type=float, default=3)
    rotation = sub.add_parser("rotate")
    rotation.add_argument("--output", required=True)
    rotation.add_argument("--touch", required=True)
    rotation.add_argument("--rotation", choices=ROTATIONS, required=True)
    rotation.add_argument("--calibration", nargs=9, type=float, default=ROTATIONS["normal"],
                          help="Normalized 3x3 calibration matrix; use the same values with watch")
    diagnostics = sub.add_parser("diagnose")
    diagnostics.add_argument("--output", default="evidence-x11.json")
    settings = sub.add_parser("mobile")
    settings.add_argument("--dpi", type=int, default=180)
    settings.add_argument("--workspaces", type=int, default=4)
    settings.add_argument("--icon-size", type=int, default=48)
    workspace = sub.add_parser("workspace")
    workspace.add_argument("index", type=int, help="Zero-based EWMH workspace index")
    sub.add_parser("power")
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO)
    if args.action == "power":
        print(json.dumps(power_report(), indent=2))
        return
    require_x11()
    if args.action == "display":
        apply_display(args)
    elif args.action == "watch":
        if args.interval < 1:
            parser.error("--interval must be at least 1 second")
        watch(args)
    elif args.action == "rotate":
        run(["xrandr", "--output", args.output, "--rotate", args.rotation])
        map_touch(args.touch, args.output, args.rotation, args.calibration)
    elif args.action == "diagnose":
        diagnose(args)
    elif args.action == "mobile":
        if not 72 <= args.dpi <= 480 or not 1 <= args.workspaces <= 32 or not 24 <= args.icon_size <= 160:
            parser.error("DPI must be 72..480; workspaces 1..32; icon size 24..160")
        mobile(args)
    elif args.action == "workspace":
        if args.index < 0:
            parser.error("workspace index cannot be negative")
        run(["wmctrl", "-s", str(args.index)])


if __name__ == "__main__":
    try:
        main()
    except (RuntimeError, OSError, subprocess.TimeoutExpired) as error:
        raise SystemExit(str(error))
