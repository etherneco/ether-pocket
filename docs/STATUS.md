# EtherPocket capability status

Prepared on **3 November 2026**. This matrix reflects the latest available reports, rather than a new hardware test session. Dates refer to supporting evidence. Older sections of `README.rst` are historical and may describe resolved blockers.

| Feature | Verified scope | Remaining limitations | Source |
| --- | --- | --- | --- |
| Linux and dual boot | Native ARM64 boot, touch, Android/Linux selection | GM1920-specific port, no universal image | [15 Oct](dualboot-2026-10-15.rst) |
| EtherShell and appearance | Touch settings, multiple layouts, light/dark themes | Further application adaptation | [29 Oct](ui-polish-2026-10-29.rst) |
| On-screen keyboard | Automatic opening and tested focus/keyboard policy | Physical attachment remains a separate test | [29 Oct](etherkeyboard-2026-10-29.rst) |
| LTE | Start/stop through the UI backend and HTTPS 200 through epcell0 | giffgaff.com/IPv4, roaming blocked, no further reboot in this test | [3 Nov](mobile-data-progress-2026-11-03.rst) |
| Voice calls | A real call reached Active | Two-way audio, VoLTE and emergency calling unverified | [21 Oct](etherphone-real-call-2026-10-21.rst) |
| Files and servers | Local operations and controlled SFTP/SMB/WebDAV tests | Further touch and target-server acceptance | [17 Oct](etherfiles-network-2026-10-17.rst) |
| USB Storage | Bidirectional Windows transfers and conflict handling | Correct disk ejection required | [16 Oct](usb-storage-2026-10-16.rst) |
| Camera | Rear IMX586, RAW, JPEG and H.264 recording | AF/OIS/HDR/flash and other cameras unverified | [20 Oct](ethercamera-spectra-driver-2026-10-20.rst) |
| Offline maps | ARM64 rendering, MBTiles, tracks and GPX | Online providers and publication require configuration | [21 Oct](ethermap-device-delivery-2026-10-21.rst) |
| GNSS location | Sessions and observed satellites | No verified position fix | [20 Oct](etherlocation-delivery-2026-10-20.rst) |
| Bluetooth | Power control and nearby discovery | Pairing, audio/HID and cold boot require acceptance | [17 Oct](bluetooth-driver-2026-10-17.rst) |
| Power | Brightness, profiles, screen blanking and wake | Suspend blocked, no full endurance test | [19 Oct](etherpower-delivery-2026-10-19.rst) |
| Sensors | Service, permissions and diagnostics | Motion, light, proximity and automatic rotation unverified | [21 Oct](ethersensors-delivery-2026-10-21.rst) |
| Backups | Restic encryption and selected restore checks | Storage/password commissioning needed, no full-system recovery | [21 Oct](etherbackup-delivery-2026-10-21.rst) |
| Updates | Coordinator and independent Ed25519 trust | No production release, keys or mappings | [Overview](etherupdate.rst) |
| Windows Control | Viewing, input, Unicode, PNG and reconnect | No audio, clipboard or video recording | [29 Oct](etherpocket-control-2026-10-29.rst) |
| Glasses / external display | Configuration code and patches | No verified glasses output | [History](../README.rst) |
| GPU | Desktop booted with llvmpipe | Hardware acceleration unverified | [History](../README.rst) |

## Updating this matrix

Each update should identify a dated report, device configuration, test result and limits of the conclusion. Simulated tests, QML fixtures and system interface detection do not replace physical functional testing. Historical test counts must not be combined into a single current result.

[Polish version](STATUS.pl.md).
