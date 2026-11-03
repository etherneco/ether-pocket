import QtQuick
import QtQuick.Controls
import QtQuick.Layouts

ColumnLayout {
    id: gallery
    objectName: "gallery"
    property color ink: "#122444"
    property color muted: "#5d7291"
    property color card: "#f9fcff"
    property color accent: "#087cff"
    component GalleryAction: Button {
        id: action
        implicitHeight: 44;font.pixelSize: 13;opacity: enabled?1:0.45
        background: Rectangle {radius: 14;color: action.down||action.checked?gallery.accent:gallery.card;border.color: gallery.muted;border.width: 0.3}
        contentItem: Text {text: action.text;font: action.font;color: action.down||action.checked?"white":gallery.ink;horizontalAlignment: Text.AlignHCenter;verticalAlignment: Text.AlignVCenter;elide: Text.ElideRight}
    }
    property bool screenshotsOnly: false
    property int selected: -1
    property real zoom: 1
    property var entries: screenshotsOnly ? Media.images.filter(a => a.screenshot) : Media.images
    onSelectedChanged: {zoom=1;viewer.contentX=0;viewer.contentY=0}
    onScreenshotsOnlyChanged: selected=-1
    spacing: 10
    Label {text: "Obrazy i zrzuty";color: gallery.ink;font.pixelSize: 23;font.bold: true}
    RowLayout {
        Layout.fillWidth: true
        GalleryAction {Layout.fillWidth: true;text: "Wszystkie";checkable: true;checked: !gallery.screenshotsOnly;onClicked: gallery.screenshotsOnly=false}
        GalleryAction {Layout.fillWidth: true;text: "Zrzuty";checkable: true;checked: gallery.screenshotsOnly;onClicked: gallery.screenshotsOnly=true}
        GalleryAction {Layout.fillWidth: true;text: "Odśwież";onClicked: {gallery.selected=-1;Media.scan()}}
    }
    Label {visible: gallery.selected<0;text: "Folder Obrazy · "+gallery.entries.length+" plików";color: gallery.muted;font.pixelSize: 12}
    GridView {
        id: grid
        Layout.fillWidth: true;Layout.fillHeight: true;visible: gallery.selected<0;clip: true
        cellWidth: width/3;cellHeight: cellWidth+35;model: gallery.entries
        ScrollBar.vertical: ScrollBar {}
        delegate: Rectangle {
            required property var modelData
            required property int index
            width: grid.cellWidth-6;height: grid.cellHeight-6;radius: 10;color: gallery.card
            Image {anchors.top: parent.top;anchors.left: parent.left;anchors.right: parent.right;height: parent.width;source: modelData.url;sourceSize: Qt.size(220,220);fillMode: Image.PreserveAspectCrop;asynchronous: true;autoTransform: true;clip: true}
            Label {anchors.bottom: parent.bottom;width: parent.width;padding: 4;text: modelData.name;textFormat: Text.PlainText;elide: Text.ElideMiddle;color: gallery.ink;font.pixelSize: 10}
            MouseArea {anchors.fill: parent;onClicked: gallery.selected=index}
        }
        Label {anchors.centerIn: parent;visible: gallery.entries.length===0;width: parent.width;text: "Brak obrazów.\nPower + ciszej zapisuje zrzut w Obrazy/Screenshots.";wrapMode: Text.WordWrap;horizontalAlignment: Text.AlignHCenter;color: gallery.muted}
    }
    ColumnLayout {
        Layout.fillWidth: true;Layout.fillHeight: true;visible: gallery.selected>=0
        RowLayout {
            GalleryAction {text: "← Galeria";onClicked: gallery.selected=-1}
            Label {Layout.fillWidth: true;text: (gallery.selected+1)+" / "+gallery.entries.length;color: gallery.muted;horizontalAlignment: Text.AlignHCenter}
            GalleryAction {text: gallery.zoom===1?"Powiększ":"Dopasuj";onClicked: gallery.zoom=gallery.zoom===1?2:1}
        }
        Flickable {
            id: viewer
            Layout.fillWidth: true;Layout.fillHeight: true;clip: true
            contentWidth: width*gallery.zoom;contentHeight: height*gallery.zoom
            boundsBehavior: Flickable.StopAtBounds
            Image {
                id: fullImage
                objectName: "galleryImage"
                width: viewer.contentWidth;height: viewer.contentHeight
                source: gallery.selected>=0 && gallery.selected<gallery.entries.length ? gallery.entries[gallery.selected].url : ""
                sourceSize: Qt.size(4096,4096);fillMode: Image.PreserveAspectFit;asynchronous: true;autoTransform: true
                PinchHandler {minimumScale: 1;maximumScale: 4;target: null;property real startZoom: 1;onActiveChanged: if(active)startZoom=gallery.zoom;onActiveScaleChanged: gallery.zoom=Math.max(1,Math.min(4,startZoom*activeScale))}
            }
            Label {anchors.centerIn: parent;visible: fullImage.status===Image.Error;text: "Nie można odczytać obrazu.";color: gallery.muted}
        }
        Label {Layout.fillWidth: true;text: gallery.selected>=0 && gallery.selected<gallery.entries.length ? gallery.entries[gallery.selected].name+"\n"+gallery.entries[gallery.selected].date : "";color: gallery.muted;font.pixelSize: 12;wrapMode: Text.WrapAnywhere;textFormat: Text.PlainText}
        RowLayout {
            GalleryAction {Layout.fillWidth: true;text: "← Poprzedni";enabled: gallery.selected>0;onClicked: --gallery.selected}
            GalleryAction {Layout.fillWidth: true;text: "Następny →";enabled: gallery.selected<gallery.entries.length-1;onClicked: ++gallery.selected}
        }
    }
}
