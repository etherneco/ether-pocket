import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import EtherFiles 1.0

Rectangle {
    id: pane
    required property var tokens
    property bool pocket: false
    property bool active: true
    property alias location: directory.location
    property alias query: directory.query
    property alias hidden: directory.hidden
    property alias recursive: directory.recursive
    property alias sorting: directory.sort
    property alias descending: directory.descending
    property alias filters: directory.filters
    property int viewMode: 0
    property var selection: []
    property var history: []
    property int historyIndex: -1
    property bool selecting: false
    readonly property var selectedUris: selection.map(e => e.uri)
    readonly property int count: directory.count
    signal activated()
    signal contextRequested()
    signal inspected(var entry)
    signal navigated(string uri)
    signal searchRequested()
    radius: 16; color: tokens.elevated
    border.color: active ? tokens.line : tokens.surface
    border.width: active ? 2 : 1
    DirectoryModel {id: directory}
    function navigate(uri) {
        if (!uri || uri === location) return
        history = history.slice(0, historyIndex + 1).concat([uri]); historyIndex = history.length - 1
        location = uri; selection = []; selecting = false; navigated(uri)
    }
    function back() { if(historyIndex > 0) { historyIndex--; location = history[historyIndex]; selection=[]; navigated(location) } }
    function forward() { if(historyIndex + 1 < history.length) { historyIndex++; location = history[historyIndex]; selection=[]; navigated(location) } }
    function up() { navigate(directory.parentLocation()) }
    function refresh() { directory.refresh() }
    function focusPath() { pathInput.forceActiveFocus(); pathInput.selectAll() }
    function toggle(entry) {
        var copy=selection.slice(); var i=copy.findIndex(e => e.uri===entry.uri)
        if(i>=0)copy.splice(i,1);else copy.push(entry);selection=copy; inspected(entry)
    }
    function selectAll() { var items=[]; for(var i=0;i<directory.count;i++)items.push(directory.get(i));selection=items;selecting=true }
    function openEntry(entry) { if(entry.directory)navigate(entry.uri);else Services.open(entry.uri) }
    ColumnLayout {
        anchors.fill: parent; anchors.margins: 10; spacing: 10
        RowLayout {
            Layout.fillWidth: true
            TouchButton { text: "‹"; font.pixelSize: 28; implicitWidth:48; implicitHeight:48; enabled: pane.historyIndex>0; onClicked: {pane.activated();pane.back()} ToolTip.text: "Back"; ToolTip.visible: hovered }
            TouchButton { text: "›"; font.pixelSize: 28; implicitWidth:48; implicitHeight:48; enabled: pane.historyIndex+1<pane.history.length; onClicked: pane.forward(); visible: !pane.pocket }
            TouchButton { text: "↑"; implicitWidth:48; implicitHeight:48; onClicked: pane.up(); ToolTip.text: "Parent folder"; ToolTip.visible: hovered }
            EntryField { id: pathInput; Layout.fillWidth: true; text: decodeURIComponent(pane.location.replace("file://", "")); color: pane.tokens.ink; selectByMouse: true; font.pixelSize: 13; implicitHeight:48; onAccepted: {pane.navigate(text);focus=false} ToolTip.text: "Enter a path or mounted network URI"; ToolTip.visible: hovered }
            TouchButton {text:"↻";implicitWidth:48;implicitHeight:48;onClicked:pane.refresh();ToolTip.text:"Refresh";ToolTip.visible:hovered}
        }
        RowLayout {
            Layout.fillWidth: true
            EntryField { Layout.fillWidth: true; placeholderText: "Search names or MIME types…"; text: pane.query; onTextEdited:pane.query=text; implicitHeight:48; color:pane.tokens.ink }
            TouchButton {text:pane.recursive?"Subfolders ✓":"Subfolders";checkable:true;checked:pane.recursive;onClicked:pane.recursive=checked;implicitHeight:48;visible:!pane.pocket}
            TouchButton {text:"Filter";implicitHeight:48;onClicked:{pane.activated();pane.searchRequested()}}
        }
        RowLayout {Layout.fillWidth:true;visible:directory.busy||directory.error.length>0
            BusyIndicator {running:directory.busy;visible:running;implicitWidth:28;implicitHeight:28}
            Label {Layout.fillWidth:true;text:directory.error||"Reading files…";wrapMode:Text.Wrap;color:directory.error?pane.tokens.danger:pane.tokens.muted}
            TouchButton {visible:directory.busy;text:"Cancel";onClicked:directory.cancel()}
        }
        GridView {
            id: grid
            Layout.fillWidth: true; Layout.fillHeight: true; clip: true
            model: directory
            cellWidth: pane.viewMode===0 ? width/Math.max(1,Math.floor(width/(pane.pocket?135:146))) : width
            cellHeight: pane.viewMode===0 ? (pane.pocket?168:164) : pane.viewMode===1?66:48
            reuseItems: true; cacheBuffer: cellHeight*2
            boundsBehavior: Flickable.DragOverBounds
            onDragEnded: if(verticalOvershoot < -70) pane.refresh()
            ScrollBar.vertical: ScrollBar {}
            Label {anchors.centerIn:parent;visible:directory.count===0&&!directory.busy;text:directory.error?"This location is unavailable":"No files here";color:pane.tokens.muted}
            delegate: Item {
                id: tile
                required property var entry
                width: grid.cellWidth; height: grid.cellHeight
                readonly property bool selected: pane.selection.some(e => e.uri===entry.uri)
                Rectangle {anchors.fill:parent;anchors.margins:4;radius:14;color:tile.selected?(pane.tokens.dark?"#194f83":"#e3f0ff"):pane.tokens.elevated;border.color:tile.selected?pane.tokens.accent:pane.tokens.line;border.width:tile.selected?2:1
                    Image {
                        id: fileIcon
                        width:pane.viewMode===0?78:38;height:pane.viewMode===0?72:38
                        x:pane.viewMode===0?(parent.width-width)/2:12;y:pane.viewMode===0?15:(parent.height-height)/2
                        source:tile.entry.directory?"qrc:/icons/folder.svg":(tile.entry.icon==="image"&&tile.entry.path&&tile.entry.size<33554432&&!tile.entry.symlink?"image://thumb/"+encodeURIComponent(tile.entry.path):"qrc:/icons/file.svg")
                        sourceSize:Qt.size(180,130);fillMode:Image.PreserveAspectFit;asynchronous:true
                    }
                    Label {visible:!tile.entry.directory&&tile.entry.icon!=="image";anchors.centerIn:fileIcon;text:tile.entry.icon==="PDF"?"PDF":tile.entry.icon==="code"?"‹/›":tile.entry.icon==="video"?"▶":tile.entry.icon==="audio"?"♪":tile.entry.icon==="archive"?"ZIP":"";font.pixelSize:16;font.bold:true;color:pane.tokens.accent}
                    Column {
                        x:pane.viewMode===0?10:62;y:pane.viewMode===0?96:(parent.height-height)/2
                        width:pane.viewMode===0?parent.width-20:parent.width-104;spacing:4
                        Label {text:tile.entry.name; width:parent.width;height:pane.viewMode===0?36:implicitHeight;wrapMode:pane.viewMode===0?Text.Wrap:Text.NoWrap;maximumLineCount:2;elide:Text.ElideRight;color:pane.tokens.ink;font.pixelSize:13;horizontalAlignment:pane.viewMode===0?Text.AlignHCenter:Text.AlignLeft}
                        Label {text:tile.entry.symlink?"Link · "+tile.entry.sizeLabel:tile.entry.sizeLabel;width:parent.width;elide:Text.ElideRight;color:pane.tokens.muted;font.pixelSize:11;horizontalAlignment:pane.viewMode===0?Text.AlignHCenter:Text.AlignLeft;visible:pane.viewMode!==2}
                    }
                    Label {visible:tile.selected;text:"✓";color:pane.tokens.accent;anchors.right:parent.right;anchors.top:parent.top;anchors.margins:8;font.bold:true}
                    MouseArea {
                        anchors.fill:parent;acceptedButtons:Qt.LeftButton|Qt.RightButton
                        onClicked: mouse=>{pane.activated();if(mouse.button===Qt.RightButton){if(!tile.selected)pane.selection=[tile.entry];pane.inspected(tile.entry);pane.contextRequested();return}if(pane.pocket&&!pane.selecting&&pane.selection.length===0)pane.openEntry(tile.entry);else if(pane.selecting||(mouse.modifiers&Qt.ControlModifier))pane.toggle(tile.entry);else{pane.selection=[tile.entry];pane.inspected(tile.entry)}}
                        onDoubleClicked:if(!pane.pocket)pane.openEntry(tile.entry)
                        onPressAndHold:{pane.activated();pane.selecting=true;pane.toggle(tile.entry)}
                    }
                    TouchButton {anchors.right:parent.right;anchors.bottom:parent.bottom;implicitWidth:48;implicitHeight:48;text:"⋮";onClicked:{pane.activated();if(!tile.selected)pane.selection=[tile.entry];pane.inspected(tile.entry);pane.contextRequested()} Accessible.name:"Actions for "+tile.entry.name}
                }
            }
        }
        Label { Layout.fillWidth:true; text:pane.selection.length?pane.selection.length+" selected · "+pane.selection.map(e=>e.name).join(", "):directory.count+" items"; elide:Text.ElideRight; color:pane.tokens.muted; font.pixelSize:12; ToolTip.text:pane.selection.map(e=>e.name).join("\n");ToolTip.visible:hover.hovered
            HoverHandler {id:hover}
        }
        Label {Layout.fillWidth:true;visible:pane.pocket&&pane.selection.length===1;text:pane.selection.length===1?pane.selection[0].name:"";wrapMode:Text.Wrap;color:pane.tokens.ink;font.pixelSize:13}
    }
}
