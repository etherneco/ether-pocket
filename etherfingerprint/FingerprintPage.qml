import QtQuick
import QtQuick.Controls
import QtQuick.Layouts

ColumnLayout {
 id: page
 objectName: "fingerprintManager"
 required property var tokens
 readonly property var status: FingerprintControl.state
 readonly property bool serviceAvailable: status.ready === true
 readonly property bool reducedMotion: !tokens.motion
 readonly property string health: !serviceAvailable ? "Service unavailable" : !status.detected ? "Sensor unavailable" : !status.driver ? "Driver missing" : "Secure backend unavailable"
 property bool diagnosticsOpen: false
 spacing: 16
 Layout.fillWidth: true

 component Copy: Text {
  color: page.tokens.ink; font.pixelSize: 14 * page.tokens.fontScale
  wrapMode: Text.Wrap; Layout.fillWidth: true; Layout.minimumWidth: 0
  Accessible.role: Accessible.StaticText; Accessible.name: text
 }
 component Caption: Copy { color: page.tokens.muted; font.pixelSize: 12 * page.tokens.fontScale }
 component Heading: Copy { font.pixelSize: 18 * page.tokens.fontScale; font.bold: true }
 component Card: Rectangle {
  default property alias contents: body.data
  Layout.fillWidth: true; implicitHeight: body.implicitHeight + 40
  radius: page.tokens.radius; color: page.tokens.surface; border.color: page.tokens.line
  ColumnLayout { id: body; x: 20; y: 20; width: parent.width - 40; spacing: 12 }
 }
 component Action: Button {
  id: action
  property bool primary: false
  Layout.fillWidth: true; implicitHeight: Math.max(52, contentItem.implicitHeight + 24)
  padding: 12; focusPolicy: Qt.StrongFocus; Accessible.name: text
  contentItem: Text {
   text: action.text; font.pixelSize: 14 * page.tokens.fontScale; font.bold: true
   wrapMode: Text.Wrap; horizontalAlignment: Text.AlignHCenter; verticalAlignment: Text.AlignVCenter
   color: !action.enabled ? page.tokens.muted : action.primary ? "#FFFFFF" : page.tokens.accent
  }
  background: Rectangle {
   radius: 14
   color: !action.enabled ? page.tokens.soft : action.down ? page.tokens.soft : action.primary ? page.tokens.accent : page.tokens.surface
   border.color: action.activeFocus ? page.tokens.accent : page.tokens.line
   border.width: action.activeFocus ? 2 : 1
  }
 }

 Card {
  RowLayout {
   Layout.fillWidth: true; spacing: 12
   Rectangle {
    Layout.preferredWidth: 40; Layout.preferredHeight: 40; radius: 14; color: page.tokens.soft
    Text { anchors.centerIn: parent; text: "◇"; color: page.tokens.accent; font.pixelSize: 26; Accessible.ignored: true }
   }
   ColumnLayout {
    Layout.fillWidth: true; spacing: 3
    Caption { text: "ETHERFINGERPRINT"; font.letterSpacing: 1.5; font.pixelSize: 10 }
    Heading { text: "Your touch. Your device." }
   }
  }
  Item {
   Layout.fillWidth: true; implicitHeight: 156
   Rectangle { anchors.centerIn: parent; width: 146; height: 146; radius: 73; color: page.tokens.soft }
   Image {
    id: symbol; objectName: "fingerprintSymbol"
    anchors.centerIn: parent; width: 124; height: 136
    sourceSize: Qt.size(Math.ceil(width * page.tokens.uiScale), Math.ceil(height * page.tokens.uiScale))
    fillMode: Image.PreserveAspectFit
    Accessible.role: Accessible.Graphic
    Accessible.name: "Fingerprint symbol. Sensor is inactive. This is not a sensor position guide."
    source: "data:image/svg+xml;utf8," + encodeURIComponent('<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 124 136"><g fill="none" stroke="'+page.tokens.accent+'" stroke-width="3.8" stroke-linecap="round"><path d="M24 44 C40 12 84 12 100 44 M16 68 C12 8 110 3 109 66 M26 77 C25 27 98 25 98 69 C98 87 105 98 110 105 M38 86 C43 71 32 44 59 40 C86 36 88 53 87 76 C86 96 96 110 102 116 M24 98 C34 82 26 62 34 49 M43 110 C56 92 48 74 49 61 C50 45 76 48 76 65 C74 89 78 109 89 125 M62 62 C63 91 63 109 54 123 M15 84 C15 104 10 110 8 112"/></g></svg>')
    // A decorative entrance only; never implies sensing or enrollment progress.
    SequentialAnimation on opacity {
     running: !page.reducedMotion
     NumberAnimation { from: 0; to: 1; duration: 500; easing.type: Easing.OutCubic }
    }
   }
  }
  Heading { objectName: "fingerprintHealth"; text: page.health; horizontalAlignment: Text.AlignHCenter }
  Copy {
   horizontalAlignment: Text.AlignHCenter
   text: !page.serviceAvailable ? "Fingerprint status could not be read. Your PIN or password remains available." : !page.status.detected ? "The fingerprint sensor is unavailable. Continue using your PIN or password." : "Your sensor is detected, but secure fingerprint authentication is not available on this installation."
  }
  Rectangle {
   Layout.alignment: Qt.AlignHCenter; implicitWidth: badge.implicitWidth + 24; implicitHeight: 30
   radius: 15; color: page.tokens.soft
   Text { id: badge; anchors.centerIn: parent; text: "PIN / PASSWORD REQUIRED"; font.pixelSize: 10; font.bold: true; color: page.tokens.ink; Accessible.name: "PIN or password required" }
  }
 }

 Card {
  RowLayout {
   Layout.fillWidth: true
   Heading { text: "Saved fingerprints" }
   Caption { objectName: "fingerprintCount"; Layout.fillWidth: false; text: "Unknown" }
  }
  Copy { text: "Protected enrollment list unavailable"; font.bold: true }
  Caption { text: "We cannot read the trusted enrollment list. Existing fingerprints may be present; this does not mean that none are saved." }
  Action { objectName: "fingerprintEnroll"; text: "Add fingerprint"; primary: true; enabled: false; Accessible.description: "Enrollment requires a verified secure backend and existing credential authentication." }
  Caption { text: "Adding, renaming, deleting and replacing fingerprints will become available after secure backend integration. No stored fingerprint is changed here." }
 }

 Card {
  Heading { text: "Unlock & authorization" }
  RowLayout {
   Layout.fillWidth: true
   ColumnLayout {
    Layout.fillWidth: true; spacing: 3
    Copy { text: "Fingerprint unlock"; font.bold: true }
    Caption { text: "Unavailable · use your existing screen lock" }
   }
   Switch {
    objectName: "fingerprintToggle"; checked: false; enabled: false; focusPolicy: Qt.StrongFocus
    Accessible.name: "Fingerprint unlock unavailable"
    indicator: Rectangle {
     implicitWidth: 48; implicitHeight: 28; radius: 14; color: page.tokens.soft; border.color: page.tokens.line
     Rectangle { x: 4; y: 4; width: 20; height: 20; radius: 10; color: page.tokens.muted }
    }
    Layout.minimumHeight: 48
   }
  }
  Rectangle { Layout.fillWidth: true; height: 1; color: page.tokens.line }
  Copy { text: "PIN or password after restart"; font.bold: true }
  Caption { text: "Required. Biometrics cannot override primary authentication or EtherLock security policy." }
  Copy { text: "Authentication timeout"; font.bold: true }
  Caption { text: "Not configurable until secure fingerprint verification is supported." }
  Copy { text: "Privileged operations"; font.bold: true }
  Caption { text: "Fingerprint authorization is unavailable. Existing system authentication stays in control." }
  Action { objectName: "fingerprintTest"; text: "Test fingerprint"; enabled: false; Accessible.description: "Trusted verification and display illumination are not available." }
 }

 Card {
  Heading { text: "Private by design" }
  Copy { text: "Your password is always a way back in."; font.bold: true }
  Caption { text: "Enrollment and removal require your existing credential. Fingerprint images and protected templates are never shown, exported or synced by this manager." }
  Caption { text: "The symbol above is decorative. A sensing guide will appear only when the internal display position and safe illumination are verified. No sensor or brightness control is activated here." }
 }

 Card {
  Action {
   objectName: "fingerprintDiagnostics"
   text: page.diagnosticsOpen ? "Hide authentication diagnostics −" : "Authentication diagnostics +"
   Accessible.description: page.diagnosticsOpen ? "Expanded" : "Collapsed"
   onClicked: page.diagnosticsOpen = !page.diagnosticsOpen
  }
  ColumnLayout {
   visible: page.diagnosticsOpen; Layout.fillWidth: true; spacing: 12
   Repeater {
    model: [
     ["Service", page.serviceAvailable ? "Available · diagnostics only" : "Unavailable"],
     ["Sensor", page.serviceAvailable ? (page.status.detected ? page.status.vendor : "Not detected") : "Unknown"],
     ["Driver", page.status.driver || "Not verified"],
     ["Firmware", page.status.firmwareStatus || "Not verified"],
     ["Secure backend", "Unavailable"],
     ["Display illumination", "Not verified · inactive"],
     ["Enrollment / verification", "Unsupported by the installed backend"],
     ["Sensor location", "Not verified"],
     ["Last hardware observation", page.status.observedAt || "Unavailable"]
    ]
    delegate: ColumnLayout {
     required property var modelData
     Layout.fillWidth: true; spacing: 2
     Caption { text: modelData[0] }
     Copy { text: modelData[1] || "Unknown" }
    }
   }
   Caption { text: page.status.lastError || "Fingerprint service unavailable. Continue with your PIN or password." }
   Caption { text: "Refresh reads the service’s cached observation. It does not activate or test the sensor." }
  }
  Action { objectName: "fingerprintRefresh"; text: "Refresh status"; onClicked: FingerprintControl.refresh() }
 }
}

