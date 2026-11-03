import QtQuick
import QtQuick.Controls
ItemDelegate {
    id: control
    implicitHeight: 46
    background: Rectangle {radius:10;color:control.highlighted?control.palette.alternateBase:control.down?control.palette.highlight:control.hovered?control.palette.base:"transparent"}
    contentItem: Text {text:control.text;font:control.font;color:control.palette.text;verticalAlignment:Text.AlignVCenter;elide:Text.ElideRight;leftPadding:12}
}
