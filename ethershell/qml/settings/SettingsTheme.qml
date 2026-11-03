import QtQuick
QtObject {
 property bool dark: Core.preferences.dark
 property real uiScale:1
 property color background: dark?"#0C192B":"#F3F8FF"
 property color surface: dark?"#162B43":"#FFFFFF"
 property color soft: dark?"#203C58":"#EAF3FF"
 property color ink: dark?"#EDF5FF":"#142F55"
 property color muted: dark?"#AAC0DA":"#617B9C"
 property color accent: Core.preferences.accent||"#087DFF"
 property color line: Core.preferences.highContrast?ink:dark?"#304F6E":"#D8E8FA"
 property color success: "#0BAE72"
 property color warning: "#E6A23C"
 property color danger: dark?"#FF8994":"#E54855"
 property color elevated: soft
 property real fontScale: Number(Core.preferences.fontScale)
 property int pageTitle: 25
 property int sectionTitle: 18
 property int body: 15
 property int caption: 12
 property int tiny: 11
 property int padding: 16
 property int inset: 14
 property int gap: 10
 property int sectionGap: 16
 property int radius: 20
 property int controlRadius: 14
 property int target: 48
 property int icon: 22
 property int motion: Core.preferences.animations&&!Core.preferences.lowPower?150:0
 property real disabledOpacity: .45
 property int shadow: Core.preferences.lowPower?0:2
}

