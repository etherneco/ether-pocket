import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
ColumnLayout {
 id:page;objectName:"etherPhoneSettings"
 property var control
 property var tokens
 readonly property var snapshot:control?control.state:({})
 readonly property var config:page.snapshot.config||({})
 readonly property color ink:tokens?tokens.ink:"#183454"
 component BodyText:Text {font.pixelSize:15*(page.tokens?page.tokens.fontScale:1)}
 spacing:12
 BodyText {text:"Calls";font.pixelSize:24;font.bold:true;color:page.ink;textFormat:Text.PlainText}
 BodyText {Layout.fillWidth:true;color:page.ink;wrapMode:Text.WordWrap;textFormat:Text.PlainText;text:"ModemManager · "+((page.snapshot.status||{}).voice?"Voice interface exposed":"Calling unavailable")+"\nIMS: "+(page.snapshot.ims||"Unverified")+" · VoLTE: "+(page.snapshot.volte||"Unverified")}
 BodyText {Layout.fillWidth:true;color:page.ink;wrapMode:Text.WordWrap;textFormat:Text.PlainText;text:"Audio: earpiece, speakerphone, microphone mute, Bluetooth and USB call routes require a verified Qualcomm voice path. SIM/backend switching, call waiting and conference are unavailable."}
 Switch {objectName:"callPrivacy";font.pixelSize:15;text:"Hide caller on lock screen";implicitHeight:48;checked:!!page.config.hideCallerOnLock;enabled:!!page.snapshot.ready&&!control.busy;onClicked:control.command("configure","",{hideCallerOnLock:checked})}
 Switch {font.pixelSize:15;text:"Missed call notifications";implicitHeight:48;checked:!!page.config.missedNotifications;enabled:!!page.snapshot.ready&&!control.busy;onClicked:control.command("configure","",{missedNotifications:checked})}
 BodyText {Layout.fillWidth:true;color:page.ink;wrapMode:Text.WordWrap;textFormat:Text.PlainText;text:"Ringtone, vibration, silent mode and DND integration are blocked pending a verified ringer/haptic backend. No automatic recording. Contact and call data stay in private local stores."}
 RowLayout {Layout.fillWidth:true
  BodyText {text:"History retention (days)";color:page.ink;Layout.fillWidth:true;wrapMode:Text.WordWrap}
  SpinBox {font.pixelSize:15;id:days;from:1;to:3650;value:page.config.retentionDays||90;editable:true;implicitHeight:48;enabled:!!page.snapshot.ready&&!control.busy;onValueModified:control.command("configure","",{retentionDays:value})}
 }
 BodyText {Layout.fillWidth:true;color:"#996122";wrapMode:Text.WordWrap;textFormat:Text.PlainText;text:page.snapshot.emergencyWarning||"Emergency calling is unverified. Keep a known-working phone available."}
 Button {font.pixelSize:15;text:"Export redacted diagnostics";implicitHeight:48;enabled:!!page.snapshot.ready;onClicked:control.exportFile("diagnostics")}
 BodyText {Layout.fillWidth:true;color:page.ink;wrapMode:Text.WordWrap;textFormat:Text.PlainText;text:control?control.message:"";visible:text.length>0}
}
