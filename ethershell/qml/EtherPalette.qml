import QtQuick
QtObject {
    property bool dark: false
    property color ink: dark ? "#edf5ff" : "#122c50"
    property color muted: dark ? "#afc6df" : "#536b88"
    property color surface: dark ? "#192e49" : "#f1f7ff"
    property color elevated: dark ? "#244464" : "#ffffff"
    property color line: dark ? "#426586" : "#d7e6f8"
    property color ocean: dark ? "#071729" : "#164e86"
    property color cyan: dark ? "#4ce5ed" : "#007eac"
    property color accent: "#1884ff"
    property color danger: dark ? "#ff9caa" : "#b52e49"
    property color sky: dark ? "#102c4c" : "#9ed9fb"
    property color lavender: dark ? "#192748" : "#e2e2fc"
}
