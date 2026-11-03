import QtQuick
import QtQuick.Controls
TextField {
    id: control
    implicitHeight: 48
    leftPadding: 13; rightPadding: 13
    selectByMouse: true
    background: Rectangle {radius:12;color:control.palette.base;border.color:control.activeFocus?control.palette.highlight:control.palette.mid;border.width:control.activeFocus?2:1}
}
