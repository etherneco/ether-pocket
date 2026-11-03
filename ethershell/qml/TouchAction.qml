import QtQuick
import QtQuick.Controls
Button {
    id: action
    required property var tokens
    property string glyph: ""
    property bool selected: false
    property bool destructive: false
    property bool compact: false
    property string hint: ""
    implicitHeight: Math.max(48,contentItem.implicitHeight+24)
    implicitWidth: compact ? 48 : Math.max(104,contentItem.implicitWidth+24)
    padding: 12
    hoverEnabled: true
    focusPolicy: Qt.StrongFocus
    background: Rectangle {
        radius: 16
        color: action.destructive ? Qt.rgba(tokens.danger.r,tokens.danger.g,tokens.danger.b,action.down?.22:action.hovered?.14:.07) : action.down||action.selected?tokens.accent:action.hovered?tokens.elevated:tokens.surface
        border.width: action.activeFocus?2:1
        border.color: action.activeFocus?tokens.accent:tokens.line
        Behavior on color {ColorAnimation {duration: action.tokens.motion}}
    }
    opacity: enabled ? 1 : .38
    contentItem: Item {
        implicitWidth: (action.glyph.length?22:0)+(action.glyph.length&&action.text.length?8:0)+(action.text.length?Math.ceil(label.implicitWidth)+2:0)
        implicitHeight: Math.max(action.glyph.length?22:0,action.text.length?label.implicitHeight:0)
        Row {
            id: contents
            anchors.centerIn: parent
            width: Math.min(parent.implicitWidth,parent.width)
            height: parent.implicitHeight
            spacing: 8
            Image {visible:action.glyph.length>0;width:22;height:22;anchors.verticalCenter:parent.verticalCenter;source:action.glyph.length?"qrc:/icons/"+action.glyph+((!action.destructive&&(action.selected||action.down))||tokens.dark?"-light":"")+".svg":"";fillMode:Image.PreserveAspectFit}
            Text {id:label;visible:action.text.length>0;width:Math.max(0,contents.width-(action.glyph.length?30:0));anchors.verticalCenter:parent.verticalCenter;text:action.text;color:action.destructive?tokens.danger:action.selected||action.down?"white":tokens.ink;font.pixelSize:14*tokens.fontScale;font.weight:Font.Medium;elide:Text.ElideRight}
        }
    }
    Accessible.name: hint.length?hint:text.length?text:glyph
    ToolTip.visible: hovered && compact
    ToolTip.text: hint.length?hint:text.length?text:glyph
}
