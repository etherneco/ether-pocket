import QtQuick
import QtQuick.Layouts
RowLayout {
 required property var tokens;property string title:"Settings";property string subtitle:"EtherPocket";property bool backVisible:true
 signal back();signal more()
 Layout.fillWidth:true;spacing:12
 SettingsAction {tokens:parent.tokens;text:"‹";visible:parent.backVisible;implicitWidth:48;onClicked:parent.back();Accessible.name:"Back"}
 ColumnLayout {Layout.fillWidth:true;spacing:2
  Text {text:parent.parent.subtitle;color:parent.parent.tokens.muted;font.pixelSize:parent.parent.tokens.caption}
  Text {text:parent.parent.title;color:parent.parent.tokens.ink;font.pixelSize:parent.parent.tokens.pageTitle*parent.parent.tokens.fontScale;font.bold:true;wrapMode:Text.WordWrap;Layout.fillWidth:true}
 }
 SettingsAction {tokens:parent.tokens;text:"⋮";implicitWidth:48;onClicked:parent.more();Accessible.name:"More actions"}
}

