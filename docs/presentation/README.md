# EtherPocket capability presentation

- [English PowerPoint presentation](EtherPocket.en.pptx)
- [Polish PowerPoint presentation](EtherPocket.pptx)

Each version contains six slides, approximately 3–5 minutes. Content status: 3 November 2026. The English version is a separate translation, including speaker notes, and preserves the original screenshots and design. Slide text is editable. Sources and material limitations are included in the speaker notes. The outline below is in English.

## 1. EtherPocket: Linux in your pocket

EtherPocket runs native ARM64 Linux on a phone with a touch desktop and Linux applications. The reference device is the OnePlus 7 Pro 5G GM1920. The project remains an engineering port.

## 2. A touch desktop for Linux

EtherShell combines an application launcher, window controls, settings and quick controls. The on-screen keyboard responds to editing, and layouts adapt to screen width. Mobian/Debian, systemd, Xorg and Qt 6 provide the runtime. Android has a separate system in the dual-boot configuration.

## 3. Files and basic multimedia

EtherFiles manages files, trash and previews, with SFTP, SMB and WebDAV support. A USB exchange disk transfers data to Windows. EtherCamera uses the rear IMX586 for preview, JPEG and H.264. Autofocus and full stock-camera quality remain outside the verified scope.

## 4. Offline maps

EtherMAP supports MBTiles, saved places, tracks and GPX. Routing and search providers require configuration. Displaying a map does not require a GNSS fix. GNSS sessions observed satellites, but a valid position remains unverified.

## 5. Internet and Windows integration

EtherMobile shows LTE session progress and actual interface status. The 3 November report confirms HTTPS 200 through epcell0 using the current giffgaff.com/IPv4 configuration after a service restart, without another reboot. EtherPocket Control provides X11 viewing and input from Windows over SSH, Unicode text and PNG screenshots. It does not forward audio.

## 6. Project status and development

Working elements include the desktop, files, offline maps, basic camera capture and LTE data. Further gates include call audio, a GNSS fix, sensors, suspend, GPU and glasses. Backups and releases require commissioning. No completion dates are promised.

## Image provenance and sources

The images in `images/` are reviewed copies of screenshots from isolated on-device test sessions on 29 October 2026. They do not represent a new demonstration session. Originals remain in the local `evidence/ui-polish/` archive. The map retains its attribution: © OpenStreetMap contributors, ODbL 1.0. [Map data terms](https://www.openstreetmap.org/copyright).

Technical references include the [project overview](../PROJECT.md), [capability status](../STATUS.md), [interface](../ui-polish-2026-10-29.rst), [camera](../ethercamera-spectra-driver-2026-10-20.rst), [maps](../ethermap-device-delivery-2026-10-21.rst), [LTE](../mobile-data-progress-2026-11-03.rst) and [Windows control](../etherpocket-control-2026-10-29.rst). More specific references are also included in the slide notes.
