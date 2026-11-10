import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import "StructuredData.js" as Data

ColumnLayout {
    id: view
    required property var value
    required property var tokens
    spacing: 6
    Repeater {
        model: Data.fields(view.value)
        delegate: Rectangle {
            id: field
            required property var modelData
            Layout.fillWidth: true
            implicitHeight: content.implicitHeight + 20
            radius: 10
            color: view.tokens.soft
            border.color: view.tokens.line
            ColumnLayout {
                id: content
                anchors { left: parent.left; right: parent.right; top: parent.top; margins: 10 }
                spacing: 4
                Label {
                    Layout.fillWidth: true
                    text: field.modelData.title
                    textFormat: Text.PlainText
                    color: view.tokens.muted
                    font.pixelSize: view.tokens.caption
                    wrapMode: Text.Wrap
                }
                Label {
                    Layout.fillWidth: true
                    text: field.modelData.value
                    textFormat: Text.PlainText
                    color: view.tokens.ink
                    wrapMode: Text.WrapAnywhere
                }
            }
        }
    }
}
