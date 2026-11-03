import QtQuick
import QtQuick.Controls
Button {
    id: control
    implicitHeight: Math.max(48, contentItem.implicitHeight+24)
    implicitWidth: Math.max(48, metrics.advanceWidth(text)+leftPadding+rightPadding)
    FontMetrics {id:metrics;font:control.font}
    padding: flat?6:12
    leftPadding: padding;rightPadding: padding
    font.pixelSize: flat?13:15
    focusPolicy: Qt.StrongFocus
    opacity: enabled?1:0.45
    background: Rectangle {
        radius: 12
        color: control.down||control.checked?control.palette.highlight:control.hovered?control.palette.alternateBase:control.palette.button
        border.color: control.flat?"transparent":control.palette.mid
    }
    contentItem: Text {text:control.text;font:control.font;color:control.down||control.checked?control.palette.highlightedText:control.palette.buttonText;horizontalAlignment:Text.AlignHCenter;verticalAlignment:Text.AlignVCenter;elide:Text.ElideRight}
}
