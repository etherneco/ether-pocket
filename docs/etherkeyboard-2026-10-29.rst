Automatic EtherKeyboard
======================

EtherShell opens EtherKeyboard when an editable field gains focus and no typing
keyboard is present in Linux input devices. Native shell fields use Qt input
method queries; other accessible applications use the existing AT-SPI listener.
Automatic opening respects the Keyboard & Input preference and home lock.
The dock keyboard button remains available for manual use.

Input detection checks Enter, A, Z and Space capabilities, so power, volume,
headset and touch buttons are not mistaken for typing keyboards. It rescans
every 750 ms. Connecting a keyboard closes an automatically opened EtherKeyboard;
disconnecting it opens EtherKeyboard when an editor remains focused. Manually
opened keyboards retain their existing behaviour.

Native Qt focus takes precedence over delayed accessibility events. Settings
editors can reopen the keyboard on another tap, and their scrolling helper uses
a distinct name so it does not call Qt's built-in ensureVisible with missing
arguments on other editors.

Verification
------------

``ethershell/tools/keyboard_input_test.cpp`` exercises 32/64-bit input bitmaps,
non-keyboard buttons, invalid data and input device addition/removal. Build it
with a native C++17 compiler and Qt6Core through pkg-config.

``scripts/verify-etherkeyboard.py`` runs the ARM64 binary on the handset in a
private X11 session, checking native editor focus, preference changes, blur,
manual opening, keyboard attachment/removal and the existing Settings suite.
Attachment/removal uses a private input-capability fixture accepted only in
development mode; it does not insert input devices into the live session.
This verifies policy and detection without claiming a physical USB/Bluetooth
keyboard plug test. AT-SPI support remains application dependent.

``scripts/activate-etherkeyboard.py`` requires successful acceptance of the
exact binary and switches the existing session launcher with rollback on startup
failure. Evidence is saved in ``evidence/etherkeyboard-qa.json`` and
``evidence/etherkeyboard-deployment.json``.
