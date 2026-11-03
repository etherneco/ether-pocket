EtherShell Settings 2.0 audit
============================

Baseline: active staged EtherShell 2.0.2, caa0ce1f1c174aa8a6910e25f54c80a9f292745fda66826ac7244cbd62283ca0.
Source is not a Git checkout. No AGENTS.md found in the workspace.

Existing pages and callbacks
---------------------------

Experience.qml: Settings (appearance/navigation/input/device actions), Network &
Internet (Mobile Network and external NM editor), MobileNetworkSettings.qml
(nine cellular sections). Main.qml is the legacy shell presentation and also
contains Settings, Network and the shared mobile module. EtherControl is a
separate existing shell window; EtherDock remains outside the Settings content.

Appearance: themeMode, accent, scale, fontScale, transparency, highContrast,
animations, lowPower, previews, wallpaper (apply/gradient). Core.setting persists
schema-1 preferences; dark mode also calls the existing application-theme tool.
Navigation: Pocket.setEnabled, gestures, edgeBack, dockAutoHide, sidebarPinned,
dockOrder rotation, desktop fallback/quit. Input: EN/PL, autoKeyboard,
keyboardScale, terminalFontSize; Keyboard.qml and Core input/focus integration.
Device actions: Core.control network-settings, bluetooth-settings,
display-settings, power-settings. These currently launch established native
editors. Existing brightness, volume/mute, rotate, display-profile, lock and
workspace controls are also retained.

Mobile: status/modem selection, connect/disconnect/reconnect, selected APN,
autoconnect/roaming, complete APN editor/duplicate/delete/secrets/rollback,
PIN/PUK/lock management, SIM slots, scan/register, supported modes/rollback,
usage options/counters and Doctor. Source of truth remains shared Mobile with
asynchronous NM/MM D-Bus, NM keyfiles/secrets and Core UI preferences.

Wi-Fi: Core.networks from non-scanning NM listing, explicit scan, radio control,
connectWifi with password on stdin; existing connection editor for advanced
profiles. Bluetooth: Core owns one Bluetooth object using the existing BlueZ
provider and pairing agent; expose this instance rather than instantiate another.
Display: Core.displays from xrandr, verified panel0 backlight/logind brightness,
EtherAir rotation/layout and Pocket external-display/window handling.
Sound: Media volume/mute and existing pactl/pavucontrol integration. Battery:
Core telemetry reads actual power-supply capacity/status/temperature. Apps:
Core.apps desktop catalog and Distributor existing service/catalog. System:
Core hostname/kernel/memory/load. Notifications: Core notices and existing
notification server. Gallery, app launcher, store, keyboard, window menus,
surface handling and XFCE fallback are separate working features to preserve.

Existing reusable visual components: DesignTokens/EtherPalette, GlassPanel,
TouchAction, GestureStrip, SurfaceHeader. The current full-screen root scales
the entire logical canvas with unit/factor. Settings must use a bounded effective
phone width, independent of physical portrait resolution, with its own compact
tokens; preserve the surrounding shell's scale behaviour.

New work is a shared SettingsWorkspace embedded in both existing presentations,
lazy category content, a searchable route catalog, shared mobile controls and
targeted missing reads/actions in Core. No new Settings app, modem/Bluetooth
manager, package manager, root GUI or unrestricted command interface is added.
Unimplemented hotspot/VPN/proxy/security/enterprise capabilities must be visibly
identified; established advanced native tools may remain explicit fallbacks.
