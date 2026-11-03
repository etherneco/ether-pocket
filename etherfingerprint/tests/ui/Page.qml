import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import "../.." as FP
ApplicationWindow {
 width: testWidth
 height: testHeight
 visible: true
 property bool dark: testDark
 color: dark ? "#0C192B" : "#F3F8FF"
 ScrollView {
  anchors.fill: parent
  contentWidth: availableWidth
  ColumnLayout {
   width: parent.width
   FP.FingerprintPage {
    tokens: QtObject {
     property color ink: dark ? "#EDF5FF" : "#142F55"
     property color muted: dark ? "#AAC0DA" : "#617B9C"
     property color surface: dark ? "#162B43" : "#FFFFFF"
     property color soft: dark ? "#203C58" : "#EAF3FF"
     property color line: dark ? "#304F6E" : "#D8E8FA"
     property color accent: dark ? "#60A5FF" : "#087DFF"
     property int radius: 20
     property real uiScale: testUiScale
     property real fontScale: testFontScale
     property int motion: testMotion
    }
    Layout.margins: 16
    Layout.fillWidth: true
   }
  }
 }
}
