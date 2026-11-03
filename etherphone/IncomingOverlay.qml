import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
Popup {
 id:overlay
 property var control
 property bool locked:true
 property var calls:control?(control.state.calls||[]):[]
 property var caller:calls.length?calls[0]:({})
 property bool privateCaller:locked&&(!control||(control.state.config||{}).hideCallerOnLock!==false)
 parent:Overlay.overlay
 width:Math.min(parent.width-24,460);x:(parent.width-width)/2;y:Math.max(12,(parent.height-height)/2)
 modal:true;closePolicy:Popup.NoAutoClose
 visible:calls.length>0
 contentItem:ColumnLayout {spacing:16
  Text {text:overlay.caller.state==="Incoming"||overlay.caller.state==="Waiting"?"Incoming cellular call":overlay.caller.state+" call";font.bold:true;font.pixelSize:23;textFormat:Text.PlainText;Layout.fillWidth:true;wrapMode:Text.WordWrap}
  Text {text:overlay.privateCaller?"Caller information hidden":overlay.caller.name||overlay.caller.number||"Private caller";font.pixelSize:21;textFormat:Text.PlainText;wrapMode:Text.WordWrap;Layout.fillWidth:true}
  Text {font.pixelSize:14;text:"Voice audio and incoming wake are unverified.";textFormat:Text.PlainText;Layout.fillWidth:true;wrapMode:Text.WordWrap}
  RowLayout {Layout.fillWidth:true
   Button {font.pixelSize:15;objectName:"overlayAnswer";text:"Answer";implicitHeight:52;Layout.fillWidth:true;visible:overlay.caller.state==="Incoming";enabled:!control.busy;onClicked:control.command("answer",overlay.caller.key,{})}
   Button {font.pixelSize:15;objectName:"overlayEnd";text:overlay.caller.state==="Incoming"||overlay.caller.state==="Waiting"?"Decline":"End call";implicitHeight:52;Layout.fillWidth:true;enabled:!control.busy;onClicked:control.command(overlay.caller.state==="Incoming"||overlay.caller.state==="Waiting"?"decline":"end",overlay.caller.key,{})}
  }
 }
 // Answer never invokes Core.setPreference/home/unlock. The existing lock state
 // is retained. This is presentation, not an authenticated EtherLock service.
}
