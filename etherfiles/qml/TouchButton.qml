import QtQuick
import QtQuick.Controls
ToolButton {
    id: control
    implicitHeight: 48
    implicitWidth: Math.max(48, contentItem.implicitWidth+20)
    opacity: enabled?1:0.4
    background: Rectangle {radius:12;color:control.checked||control.down?control.palette.highlight:control.hovered?control.palette.alternateBase:control.palette.button;border.color:control.palette.mid}
    contentItem: Text {text:control.text;font:control.font;color:control.checked||control.down?control.palette.highlightedText:control.palette.buttonText;horizontalAlignment:Text.AlignHCenter;verticalAlignment:Text.AlignVCenter}
}
