Panel brightness slider repair
==============================

Installed on the GM1920 on 2026-10-17. Core previously selected the first
alphabetical backlight, the unused PMIC WLED ``backlight`` (4095 maximum),
instead of the DSI ``panel0-backlight`` (1023 maximum). Both sysfs files
were root-owned and mode 0644, so the desktop slider was disabled.

Core now prefers the actual panel and uses the active desktop session's
logind SetBrightness method when direct writes are unavailable. No sysfs
permission changes or privileged helper are needed. It validates input,
reports failures, and refreshes telemetry immediately after applying the
change. Percent conversion uses rounding; the slider minimum is clamped
to 1 percent so an accidental minimum does not black out the display.

Built with scripts/build-ethershell-soft-blank.sh, retaining the active
compiled UI resources, then installed with scripts/deploy-soft-blank.py.
The active executable and persistent user launcher now use
``/opt/ethershell2/2.0.1-7b446a1157ed-soft-32adcc7a/usr/bin/ethershell``.
The previous stage ``2.0.1-7b446a1157ed-soft-efd6782b`` remains available.

ethershell/tools/brightness_test.py ran as uid 1000 against the running
shell's control socket. All seven level/clamping checks and invalid-input
check passed; the unused WLED was unchanged. Evidence is recorded in
evidence/brightness-2026-10-17.json.

A real XTest mouse drag on the visible Brightness slider changed the panel
from 931 down to 92 (out of 1023). This also verifies that the UI is enabled
and connected to the backend; evidence/brightness-slider-drag-2026-10-17.json.
The screenshot evidence/brightness-slider-2026-10-17.png shows the enabled
control at 20 percent before the drag test. Hardware readback confirms the
requested brightness, not a human measurement of perceived luminance.

All seven existing software blank/wake checks also passed after installation
(evidence/brightness-soft-blank-2026-10-17.json). Panel brightness stayed at
205/1023 after the cycles. The screen was left awake with the control open
and brightness at 20 percent.
