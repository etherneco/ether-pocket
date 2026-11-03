# EtherPocket project overview

## Purpose and audience

EtherPocket develops a native Linux environment for an ARM64 phone. It combines a device-specific system port, a touch desktop and cooperating applications. The phone can serve as a mobile terminal, file browser, basic camera or device for running Linux applications. External displays and glasses are development goals that require further testing.

The project currently targets developers, Linux porting contributors and experienced testers. Support for one reference device does not imply support for other OnePlus models. The verified variant is the OnePlus 7 Pro 5G GM1920.

## Runtime environment

A custom ARM64 kernel boots native Mobian/Debian userspace. systemd manages services. The graphical session uses Xorg, while EtherShell uses Qt 6/QML and window-manager integration. The launcher starts XDG applications. XFCE remains available as a recovery environment. Dual boot allows selecting Linux or Android, each with its own kernel.

The code accommodates Qualcomm hardware and the existing vendor kernel. The presence of DRM/KMS, a render node or DisplayPort output does not establish working graphics acceleration or glasses support. The documented desktop used llvmpipe. Hardware GPU acceleration remains unverified.

## Interface and applications

**EtherShell** provides the home screen, launcher, window controls, settings and quick controls. Light and dark themes and several viewport sizes are covered by interface checks. **EtherKeyboard** opens during editing when no typing keyboard is detected. Native Qt fields use input-method queries, while accessible external applications use AT-SPI. Physical keyboard attachment remains a separate hardware acceptance test.

**EtherFiles** manages files, trash, previews and search. It offers pocket and desktop layouts, tabs and split panes, with SFTP, SMB and WebDAV support. Controlled-server tests covered incorrect credentials, changed SSH keys and rejection of untrusted TLS. The ETHERPOCKET USB exchange disk transfers files to and from Windows. Return synchronization takes place after ejection and preserves conflict copies.

**EtherCamera** includes an application, a private media library and the native Spectra capture path. Verification for the rear Sony IMX586 covered a 4000 × 3000 RAW frame, preview, JPEG capture and finalized H.264 recording. The path uses DMA buffers and software image processing. Autofocus, OIS, HDR, flash, the front camera and stock ISP quality are outside the verified scope.

**EtherMAP** displays online raster maps and local MBTiles, with saved places, tracks and GPX support. Geocoding and routing providers require configuration and appropriate terms of use. Offline map rendering works independently of obtaining a location fix. **EtherLocation** manages permissions, accuracy, optional history and geofencing. Reports confirm GNSS sessions and observed satellites, but no valid position fix.

## Networking and communication

**EtherMobile** integrates modem and connection settings. For the hardware IPA/QMI path, it controls the dedicated `ethermobile-data.service`. Other modems retain the NetworkManager path. The interface reports progress from SIM checks and registration through the APN session, addressing and DNS. It checks the service PID and actual interface before claiming a session. A recorded test on 3 November 2026 confirms HTTPS through `epcell0`. The current IPA adapter is restricted to the documented giffgaff.com APN with IPv4 and blocks roaming. This does not establish universal carrier support.

**EtherShare** implements connection-sharing mechanisms, with full hotspot acceptance still open. Historical LTE failures must be distinguished from later successful data tests. **EtherBluetooth** integrates BlueZ and driver diagnostics. Nearby discovery is verified. Audio, HID and complete pairing scenarios require further acceptance testing.

**EtherPhone** provides dialing, a call overlay, history and shared contacts. The 21 October report confirms that the recipient answered and the call reached Active, but describes absent or one-way audio. DSP voice-path calibration remains an important dependency. VoLTE, emergency calling and complete call-audio support are unverified.

**EtherSMS** provides the messaging application and shared contacts. **EtherNotifications** handles standard Linux notifications, SQLite history, grouping, actions and Do Not Disturb. Sending and receiving communication also depend on the modem and carrier services.

## System services

Components separate interfaces from services. D-Bus connects applications. PolicyKit restrictions or dedicated helpers govern privileged operations. Each component has its own dependencies and packaging.

| Service | Responsibility | Material limitation |
| --- | --- | --- |
| EtherAudio | PipeWire/WirePlumber routing, audio focus, levels and capture consent | Working multimedia audio does not establish modem call audio |
| EtherPower | Brightness, CPU/GPU profiles, history, thermal diagnostics and screen blanking | Suspend remains blocked pending verified wake recovery |
| EtherHardware | Capability discovery and readable diagnostic reports | Detecting hardware does not verify its functions |
| EtherSensors | Sensor registry, subscriptions and access control | No verified changing motion, light or proximity samples |
| EtherLock | XSecureLock enforcement, PAM and access policy | Reports describe staged deployment and outstanding physical tests |
| EtherCredentials | Separate credential management and lock integration | See component documentation for scope and threat model |
| EtherBackup | Restic encryption, incremental backups, SQLite export and restore checks | Storage and recovery passwords require independent commissioning |
| EtherUpdate | Coordination, Ed25519 signatures, history and application recovery | Production publication requires keys and component mappings |

Security reports also identify existing autologin, passwordless sudo and unencrypted ext4. This port should not be presented as a finished, secured consumer phone.

## EtherPocket Control

The Windows tool displays the phone's actual X11 desktop and forwards clicks, dragging, scrolling and Unicode text. It supports 1–15 FPS, view-only mode and PNG screenshots. Defaults are 8 FPS and a width of 720 pixels.

The transport uses SSH with known-host verification. The agent runs on the phone only during a connection. Preparing the agent uses existing administrator access. Video recording, audio forwarding and clipboard synchronization are not implemented. Another workstation requires its own authorized key and verified known_hosts file.

## Example demonstration

1. Open EtherShell and show the launcher, settings and editing with the on-screen keyboard.
2. Create a test folder in EtherFiles and show the layout at a wider window size.
3. Open a prepared offline map in EtherMAP and explain the separate GNSS status.
4. Demonstrate the rear camera in EtherCamera on a verified device, with consent.
5. Show actual LTE connection progress and the result in network settings.
6. Connect EtherPocket Control from Windows and demonstrate desktop interaction.

This scenario requires a prepared device. The documentation does not automatically start operations, calls or recordings.

## Development direction

The next technical gates include complete call audio, outdoor GNSS acceptance, sensors, safe suspend and external displays. Backup commissioning, publisher-key management and repeatable package releases also remain necessary. Further stages require documented physical-device tests. No completion dates are promised.

## Sources

Prepared on 3 November 2026 from source code and local reports. Key references are [LTE](mobile-data-progress-2026-11-03.rst), [voice calls](etherphone-real-call-2026-10-21.rst), [camera](ethercamera-spectra-driver-2026-10-20.rst), [maps](ethermap-device-delivery-2026-10-21.rst), [interface](ui-polish-2026-10-29.rst), [keyboard](etherkeyboard-2026-10-29.rst) and [Windows control](etherpocket-control-2026-10-29.rst). Preparing documentation is not a new hardware test.

[Polish version](PROJECT.pl.md).
