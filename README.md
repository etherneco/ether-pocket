# EtherPocket

**Native ARM64 Linux on a phone, with a touch desktop and an integrated application suite.**

EtherPocket turns a phone into a pocket computer running Mobian/Debian. It boots its own Linux kernel, an Xorg session and EtherShell, a Qt 6/QML interface. Applications and services run directly on Linux. The project also includes hardware integration, diagnostics and remote desktop control from Windows over SSH.

The current reference device is the **OnePlus 7 Pro 5G GM1920**. This repository contains the source code and documentation for an engineering port. Feature readiness depends on the device, drivers and configuration.

## Explore the project

- [Detailed overview, architecture and use cases](docs/PROJECT.md)
- [Verified capabilities and remaining limitations](docs/STATUS.md)
- [Short PowerPoint presentation (Polish)](docs/presentation/EtherPocket.pptx)
- [Presentation outline and demonstration notes](docs/presentation/README.md)
- [Contribution guide](CONTRIBUTING.md)
- [Deployment history and earlier reports](README.rst)

## Capabilities

| Area | Components | Scope |
| --- | --- | --- |
| Touch desktop | EtherShell, EtherKeyboard | XDG application launcher, settings, quick controls, window management and on-screen keyboard |
| Files and data exchange | EtherFiles, USB Storage | File operations, trash, previews, SFTP/SMB/WebDAV and a USB exchange disk |
| Internet | EtherMobile, EtherShare | Modem integration, connection progress, LTE diagnostics and controlled connection sharing |
| Multimedia | EtherCamera, EtherAudio | Basic rear IMX586 photo/video capture, audio policy and microphone controls |
| Maps | EtherMAP, EtherLocation | Offline maps, saved places, tracks, GPX and location permissions |
| Communication | EtherPhone, EtherSMS, EtherNotifications | Call and messaging interfaces, contacts, history and notification center |
| System management | EtherHardware, EtherPower, EtherSensors | Hardware diagnostics, power management and sensor capability registry |
| Protection and updates | EtherLock, EtherCredentials, EtherBackup, EtherUpdate | Session locking, credentials, encrypted backups and update verification |
| Windows integration | EtherPocket Control | View and control the actual X11 desktop over SSH |

**Status as documented on 3 November 2026:** that day's report confirms HTTPS through the LTE interface `epcell0`. A real voice call reached Active, but two-way audio remains unverified. A valid GNSS fix, AR glasses, GPU acceleration and suspend still require acceptance testing. An application interface alone does not establish working hardware support. See the [status matrix](docs/STATUS.md) for dates and scope.

## Architecture

The system uses Mobian/Debian ARM64, systemd and Xorg. EtherShell and the Qt/QML applications communicate with separate services and adapters over D-Bus. Integrations include NetworkManager, ModemManager/QMI, BlueZ, PipeWire/WirePlumber, PAM and PolicyKit. Scripts build Debian packages, manage deployments and record verification results. XFCE provides a recovery desktop. Android retains its own system and kernel in the dual-boot configuration.

## Getting started

```sh
git clone https://github.com/etherneco/ether-pocket.git
cd ether-pocket
python -m unittest discover -s tests -p test_x11.py
python -m unittest discover -s etherpocket-control -p test_transport.py
```

These tests use the Python standard library and do not connect to a phone. Modem status tests require Linux/POSIX:

```sh
python3 -m unittest discover -s tests -p test_mobile_data_status.py
PYTHONPATH=scripts python3 -m unittest discover -s tests -p test_ethermobile_data_cleanup.py
```

Device packages require a Linux build environment with Qt 6, CMake/Ninja and component-specific dependencies. `scripts/build-etherfiles-cross.sh` provides an EtherFiles cross-compilation example. See the [EtherFiles documentation](etherfiles/README.rst) for environment requirements. There is no single installer for the entire system. Deployment scripts may assume a specific device and the author's local environment.

## Repository layout

- `ether*/`: applications, services, D-Bus definitions, packaging and component tests.
- `scripts/`: builds, diagnostics, deployments and verification.
- `kernel/`, `xorg/`, `config/`: system patches and configuration.
- `tests/`: host-side tooling and integration tests without physical hardware.
- `docs/`: project documentation and dated technical reports.
- `assets/`: project artwork.

Local `build/`, `sources/`, `tools/`, `recovery/` directories and raw `evidence/` materials are excluded from the published source. Historical reports may reference files available only in the local archive. Vendor firmware, keys and partition backups are not included.

## Contributing and licensing

Report bugs and propose changes through [Issues](https://github.com/etherneco/ether-pocket/issues). See [CONTRIBUTING.md](CONTRIBUTING.md) for contribution guidance and [SECURITY.md](SECURITY.md) for vulnerability reporting.

A repository-wide license has not yet been established. Do not assume all code can be redistributed under a single license. Check the rights covering each component and patch, including material derived from other projects, before redistribution. This repository setup does not change existing license notices.
