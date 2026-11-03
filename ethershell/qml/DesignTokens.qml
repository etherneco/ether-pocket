import QtQuick
EtherPalette {
    dark: Core.preferences.dark
    property bool contrast: Core.preferences.highContrast
    property bool reduced: !Core.preferences.animations || Core.preferences.lowPower
    property real glass: contrast || Core.preferences.lowPower ? 1 : Number(Core.preferences.transparency)
    accent: Core.preferences.accent
    property int radius: contrast ? 12 : 24
    property int motion: reduced ? 0 : 170
    property real fontScale: Number(Core.preferences.fontScale)
}
