import QtQuick
import QtQuick.Layouts
Rectangle {
 id:card;required property var tokens
 default property alias contents:body.data
 property alias spacing:body.spacing
 Layout.fillWidth:true;implicitHeight:body.implicitHeight+2*tokens.inset
 color:tokens.surface;radius:tokens.radius;border.color:activeFocus?tokens.accent:tokens.line;border.width:activeFocus?2:1
 ColumnLayout {id:body;anchors.fill:parent;anchors.margins:card.tokens.inset;spacing:card.tokens.gap}
}

