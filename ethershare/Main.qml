import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import QtQuick.Window
import "../qml/settings" as S
ApplicationWindow {
 id:window;visible:true;title:"EtherShare";width:420;height:820
 S.SettingsTheme {id:theme}
 readonly property real phoneScale:PocketDisplay?Math.max(1,width/420):1
 color:theme.background
 Item {width:window.width/window.phoneScale;height:window.height/window.phoneScale;scale:window.phoneScale;transformOrigin:Item.TopLeft
 ColumnLayout {anchors.fill:parent;anchors.margins:theme.padding;spacing:theme.gap
  S.SettingsHeader {tokens:theme;title:"EtherShare";subtitle:"Internet Sharing";onBack:window.close()}
  ScrollView {id:scroll;Layout.fillWidth:true;Layout.fillHeight:true;clip:true;contentWidth:availableWidth
   SharePage {width:scroll.availableWidth;tokens:theme;onKeyboardRequested:Qt.inputMethod.show()}
  }
 }
 }
}
