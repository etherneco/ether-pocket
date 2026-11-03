import QtQuick
import QtQuick.Controls
Button {
 id:control;required property var tokens
 property bool loading:false
 property string error:""
 property bool primary:false
 property bool destructive:false
 property real textSize:14
 implicitHeight:Math.max(tokens.target,label.implicitHeight+20);implicitWidth:Math.max(80,label.implicitWidth+24)
 padding:12;hoverEnabled:true;focusPolicy:Qt.StrongFocus;opacity:enabled?1:tokens.disabledOpacity
 Accessible.name:text;Accessible.description:error
 background:Rectangle {radius:control.tokens.controlRadius;color:control.down?Qt.darker(control.primary?control.tokens.accent:control.tokens.soft,1.1):control.primary?control.tokens.accent:control.hovered?control.tokens.surface:control.tokens.soft;border.color:control.activeFocus?control.tokens.accent:control.tokens.line;border.width:control.activeFocus?2:1}
 contentItem:Text {id:label;text:control.loading?"…":control.text;color:control.destructive?control.tokens.danger:control.primary?"white":control.tokens.ink;font.pixelSize:control.textSize*control.tokens.fontScale;wrapMode:Text.WordWrap;horizontalAlignment:Text.AlignHCenter;verticalAlignment:Text.AlignVCenter}
}

