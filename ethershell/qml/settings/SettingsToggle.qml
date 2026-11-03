import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
SettingsRow {
 id:row;signal requested(bool wanted)
 arrow:false
 onClicked:requested(!checked)
 rightPadding:60
 Switch {
  id:toggle;anchors.right:parent.right;anchors.verticalCenter:parent.verticalCenter;width:56;height:46
  checked:row.checked;focusPolicy:Qt.StrongFocus;Accessible.name:row.title
  onClicked:{checked=Qt.binding(function(){return row.checked});row.requested(!row.checked)}
  indicator:Rectangle {x:2;y:11;width:50;height:27;radius:14;color:row.checked?row.tokens.accent:row.tokens.line
   Rectangle {x:row.checked?25:3;y:3;width:21;height:21;radius:11;color:"white";Behavior on x {NumberAnimation {duration:row.tokens.motion}}}
   border.width:toggle.activeFocus?2:0;border.color:row.tokens.ink
  }
 }
}

