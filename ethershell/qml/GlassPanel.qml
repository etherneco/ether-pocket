import QtQuick
Rectangle {
    id: panel
    required property var tokens
    radius: tokens.radius
    color: Qt.rgba(tokens.surface.r,tokens.surface.g,tokens.surface.b,tokens.glass)
    border.width: tokens.contrast ? 2 : 1
    border.color: tokens.line
    Rectangle {z:-1;x:2;y:5;width:parent.width;height:parent.height;radius:parent.radius;color:"#102c50";opacity:panel.tokens.reduced?0:.14}
}
