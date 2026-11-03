import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import QtCore
import EtherFiles 1.0

ApplicationWindow {
    id: app
    width: 1180; height: 790; minimumWidth: 360; minimumHeight: 480
    visible: true; title: "EtherFiles"
    color: theme.surface
    property string presentation: "auto"
    readonly property bool pocket: presentation==="pocket" || (presentation==="auto" && width<900)
    property bool dark: false
    property bool split: false
    property bool previewVisible: true
    property bool developer: false
    property var tabs: []
    property var closedTabs: []
    property int tabIndex: 0
    property var activePane: leftPane
    readonly property bool editingText: activeFocusItem && (activeFocusItem instanceof TextInput || activeFocusItem instanceof TextEdit)
    property string promptAction: "mkdir"
    property string confirmAction: "trash"
    property var openWithApps: []
    property int layoutView: pocket ? preferences.pocketView : preferences.desktopView
    Tokens {id:theme;dark:app.dark}
    palette.window: theme.surface; palette.windowText: theme.ink; palette.text: theme.ink
    palette.base: theme.elevated; palette.button: theme.surface; palette.buttonText: theme.ink
    palette.mid: theme.line; palette.alternateBase: theme.dark?"#194f83":"#dfedff"
    palette.highlight: theme.accent; palette.highlightedText: "white"
    font.family: "DejaVu Sans";font.pixelSize:13
    Settings {
        id: preferences
        category: "Layout"
        property alias dark: app.dark
        property alias presentation: app.presentation
        property alias split: app.split
        property alias preview: app.previewVisible
        property alias developer: app.developer
        property alias windowWidth: app.width
        property alias windowHeight: app.height
        property int pocketView: 0
        property int desktopView: 0
        property string savedTabs: "[]"
        property string rightLocation: ""
    }
    function stashTab() {
        if(!tabs.length)return
        var copy=tabs.slice();copy[tabIndex]={uri:leftPane.location,history:leftPane.history,index:leftPane.historyIndex,view:leftPane.viewMode,sort:leftPane.sorting,descending:leftPane.descending,hidden:leftPane.hidden};tabs=copy
    }
    function activateTab(index) {
        if(index<0||index>=tabs.length)return
        stashTab();tabIndex=index;var t=tabs[index];leftPane.location=t.uri
        leftPane.history=t.history||[t.uri];leftPane.historyIndex=t.index===undefined?leftPane.history.length-1:t.index
        leftPane.viewMode=t.view||0;leftPane.sorting=t.sort||0;leftPane.descending=t.descending||false;leftPane.hidden=t.hidden||false;leftPane.selection=[];activePane=leftPane
    }
    function newTab(uri) {stashTab();tabs=tabs.concat([{uri:uri||Services.home}]);activateTab(tabs.length-1)}
    function closeTab(index) {
        if(tabs.length<=1)return
        stashTab();closedTabs=closedTabs.concat([tabs[index]]);var c=tabs.slice();c.splice(index,1);tabs=c
        tabIndex=Math.min(tabIndex,tabs.length-1);var t=tabs[tabIndex];leftPane.location=t.uri;leftPane.history=t.history||[t.uri];leftPane.historyIndex=t.index||0;leftPane.selection=[]
    }
    function restoreTab() {if(!closedTabs.length)return;var c=closedTabs.slice();var t=c.pop();closedTabs=c;tabs=tabs.concat([t]);activateTab(tabs.length-1)}
    function prompt(action) {promptAction=action;nameField.text=action==="rename"&&activePane.selection.length===1?activePane.selection[0].name:action==="permissions"?"644":action==="archive"?"Archive.zip":"";nameDialog.open()}
    function doPaste() {var clip=Services.paste();if(clip.uris.length)Operations.submit(clip.cut?"move":"copy",clip.uris,activePane.location)}
    function askDelete(action) {if(!activePane.selection.length)return;confirmAction=action;deleteDialog.open()}
    function inspect(entry) {Services.inspect(entry.uri)}
    Component.onCompleted: {
        var saved=[];try{saved=JSON.parse(preferences.savedTabs)}catch(e){}
        tabs=saved.length?saved.slice(0,20).filter(t=>t.uri&&typeof t.uri==="string"):[{uri:InitialLocation||Services.home}]
        if(!tabs.length)tabs=[{uri:Services.home}]
        if(InitialLocation)tabs[0]={uri:InitialLocation}
        leftPane.location=tabs[0].uri;leftPane.history=tabs[0].history||[tabs[0].uri];leftPane.historyIndex=tabs[0].index||0
        leftPane.viewMode=layoutView;rightPane.navigate(preferences.rightLocation||Services.home)
    }
    onClosing: {stashTab();preferences.savedTabs=JSON.stringify(tabs);preferences.rightLocation=rightPane.location;if(pocket)preferences.pocketView=leftPane.viewMode;else preferences.desktopView=leftPane.viewMode}
    onPocketChanged: {if(pocket)activePane=leftPane;leftPane.viewMode=layoutView}
    Connections {target:Services;function onNetworkReady(uri){app.activePane.navigate(uri);networkDialog.close()}}
    Connections {target:Operations;function onCompleted(){leftPane.refresh();rightPane.refresh()}function onConflictChanged(){if(Operations.conflict.source)conflictDialog.open();else conflictDialog.close()}}
    Shortcut {sequence:"Alt+Left";onActivated:app.activePane.back()}
    Shortcut {sequence:"Alt+Right";onActivated:app.activePane.forward()}
    Shortcut {sequence:"Alt+Up";onActivated:app.activePane.up()}
    Shortcut {sequence:"Ctrl+T";onActivated:app.newTab(app.activePane.location)}
    Shortcut {sequence:"Ctrl+W";onActivated:app.closeTab(app.tabIndex)}
    Shortcut {sequence:"Ctrl+Shift+T";onActivated:app.restoreTab()}
    Shortcut {sequence:"Ctrl+Tab";onActivated:app.activateTab((app.tabIndex+1)%app.tabs.length)}
    Shortcut {sequence:"Ctrl+L";onActivated:app.activePane.focusPath()}
    Shortcut {sequence:"Ctrl+Shift+N";onActivated:app.prompt("mkdir")}
    Shortcut {sequence:"Ctrl+A";enabled:!app.editingText;onActivated:app.activePane.selectAll()}
    Shortcut {sequence:"Ctrl+C";enabled:app.activePane.selection.length>0&&!app.editingText;onActivated:Services.clipboard(app.activePane.selectedUris,false)}
    Shortcut {sequence:"Ctrl+X";enabled:app.activePane.selection.length>0&&!app.editingText;onActivated:Services.clipboard(app.activePane.selectedUris,true)}
    Shortcut {sequence:"Ctrl+V";enabled:!app.editingText;onActivated:app.doPaste()}
    Shortcut {sequence:"Ctrl+H";onActivated:app.activePane.hidden=!app.activePane.hidden}
    Shortcut {sequence:"F2";enabled:app.activePane.selection.length===1;onActivated:app.prompt("rename")}
    Shortcut {sequence:"F5";onActivated:app.activePane.refresh()}
    Shortcut {sequence:"Delete";enabled:app.activePane.selection.length>0&&!app.editingText;onActivated:app.askDelete("trash")}
    Shortcut {sequence:"Escape";enabled:!app.editingText;onActivated:{app.activePane.selection=[];app.activePane.selecting=false}}
    header: Rectangle {
        height:app.pocket?78:66;color:theme.surface
        RowLayout {
            anchors.fill:parent;anchors.margins:12;spacing:12
            TouchButton {text:"☰";visible:app.pocket;implicitWidth:48;implicitHeight:48;onClicked:placesDrawer.open();Accessible.name:"Places"}
            Image {source:"qrc:/icons/etherfiles.svg";Layout.minimumWidth:40;Layout.maximumWidth:40;Layout.preferredHeight:40;sourceSize:Qt.size(80,80)}
            ColumnLayout {spacing:2;Layout.fillWidth:true
                Label {text:"EtherFiles";font.pixelSize:app.pocket?23:19;font.bold:true;color:theme.ink}
                Label {text:app.pocket?"Your files, within reach":"EtherAir · "+app.tabs.length+" tab"+(app.tabs.length===1?"":"s");font.pixelSize:11;color:theme.muted}
            }
            TouchButton {text:"Split";visible:!app.pocket;checkable:true;checked:app.split;onClicked:app.split=checked;Layout.preferredWidth:64;implicitHeight:48;ToolTip.text:"Split view";ToolTip.visible:hovered}
            TouchButton {text:"Preview";visible:!app.pocket;checkable:true;checked:app.previewVisible;onClicked:app.previewVisible=checked;Layout.preferredWidth:82;implicitHeight:48;ToolTip.text:"Preview panel";ToolTip.visible:hovered}
            TouchButton {text:"Jobs";implicitWidth:48;implicitHeight:48;onClicked:jobsDrawer.open();Accessible.name:"File operations"}
            TouchButton {id:topMore;text:"⋮";implicitWidth:48;implicitHeight:48;onClicked:moreMenu.popup();Accessible.name:"More options"}
        }
    }
    ColumnLayout {
        anchors.fill:parent;anchors.margins:app.pocket?8:14;spacing:10
        Flickable {visible:app.pocket;Layout.fillWidth:true;Layout.preferredHeight:52;contentWidth:categories.width;clip:true;boundsBehavior:Flickable.StopAtBounds
            Row {id:categories;spacing:8
                Repeater {model:[{name:"All files",mime:""},{name:"Images",mime:"image/"},{name:"Videos",mime:"video/"},{name:"Documents",mime:"application/pdf"},{name:"Music",mime:"audio/"}]
                    ActionButton {required property var modelData;text:modelData.name;onClicked:{app.activePane.navigate(Services.home);app.activePane.recursive=modelData.mime!=="";app.activePane.query=modelData.mime}}
                }
            }
        }
        RowLayout {Layout.fillWidth:true;visible:!app.pocket
            Repeater {model:app.tabs
                Rectangle {required property var modelData;required property int index;Layout.preferredWidth:Math.max(110,Math.min(190,(app.width-300)/app.tabs.length));Layout.preferredHeight:42;radius:12;color:index===app.tabIndex?theme.elevated:theme.surface;border.color:theme.line
                    RowLayout {anchors.fill:parent;anchors.leftMargin:12
                        Label {Layout.fillWidth:true;text:decodeURIComponent(modelData.uri.split('/').filter(Boolean).pop()||"/");elide:Text.ElideRight;color:theme.ink}
                        TouchButton {text:"×";visible:app.tabs.length>1;implicitWidth:38;onClicked:app.closeTab(index)}
                    }
                    TapHandler {onTapped:app.activateTab(index)}
                }
            }
            TouchButton {text:"+";onClicked:app.newTab(Services.home);implicitHeight:42;implicitWidth:44;ToolTip.text:"New tab";ToolTip.visible:hovered}
            Item {Layout.fillWidth:true}
            TouchButton {text:"Sort";onClicked:sortMenu.popup();implicitHeight:42}
            TouchButton {text:app.activePane.viewMode===0?"▦ Grid":app.activePane.viewMode===1?"☷ List":"☰ Compact";onClicked:viewMenu.popup();implicitHeight:42}
        }
        RowLayout {
            Layout.fillWidth:true;Layout.fillHeight:true;spacing:12
            Rectangle {visible:!app.pocket;Layout.preferredWidth:185;Layout.fillHeight:true;radius:theme.radius;color:theme.surface
                ScrollView {anchors.fill:parent;clip:true;contentWidth:availableWidth
                    ColumnLayout {width:parent.width;spacing:4
                        Label {text:"PLACES";color:theme.muted;font.pixelSize:10;Layout.leftMargin:12;Layout.topMargin:12}
                        Repeater {model:Services.places
                            PlaceDelegate {required property var modelData;Layout.fillWidth:true;text:modelData.icon+"   "+modelData.name;implicitHeight:43;highlighted:app.activePane.location===modelData.uri;onClicked:app.activePane.navigate(modelData.uri)}
                        }
                        Label {text:"NETWORK";color:theme.muted;font.pixelSize:10;Layout.leftMargin:12;Layout.topMargin:20}
                        PlaceDelegate {Layout.fillWidth:true;text:"◎   Connect to server";implicitHeight:46;onClicked:networkDialog.open()}
                        Label {text:"DEVICES";color:theme.muted;font.pixelSize:10;Layout.leftMargin:12;Layout.topMargin:20}
                        Repeater {model:Services.devices
                            PlaceDelegate {required property var modelData;Layout.fillWidth:true;implicitHeight:65
                                contentItem:Column {spacing:3
                                    Label {text:modelData.name;width:160;elide:Text.ElideRight;color:theme.ink}
                                    Label {text:modelData.label;width:160;elide:Text.ElideRight;color:theme.muted;font.pixelSize:10}
                                    ProgressBar {width:155;value:modelData.capacity>0?(modelData.capacity-modelData.free)/modelData.capacity:0}
                                }
                                onClicked:app.activePane.navigate(modelData.uri)
                            }
                        }
                        PlaceDelegate {Layout.fillWidth:true;text:"Storage controls…";onClicked:storageDialog.open()}
                        Label {text:"FAVOURITES";color:theme.muted;font.pixelSize:10;Layout.leftMargin:12;Layout.topMargin:20}
                        Repeater {model:Services.bookmarks
                            PlaceDelegate {required property var modelData;Layout.fillWidth:true;text:"☆   "+modelData.name;onClicked:app.activePane.navigate(modelData.uri)}
                        }
                    }
                }
            }
            FilePane {id:leftPane;tokens:theme;pocket:app.pocket;active:app.activePane===leftPane;Layout.fillWidth:true;Layout.fillHeight:true;Layout.minimumWidth:260
                onActivated:app.activePane=leftPane
                onContextRequested:contextMenu.popup()
                onInspected:entry=>app.inspect(entry)
                onSearchRequested:searchDialog.open()
                onNavigated:uri=>{if(app.tabs.length){var c=app.tabs.slice();c[app.tabIndex].uri=uri;app.tabs=c}}
            }
            FilePane {id:rightPane;tokens:theme;pocket:false;active:app.activePane===rightPane;visible:!app.pocket&&app.split;Layout.fillWidth:true;Layout.fillHeight:true;Layout.minimumWidth:260
                onActivated:app.activePane=rightPane
                onContextRequested:contextMenu.popup()
                onInspected:entry=>app.inspect(entry)
                onSearchRequested:searchDialog.open()
            }
            Rectangle {visible:!app.pocket&&app.previewVisible&&!app.split&&app.width>=1120;Layout.preferredWidth:260;Layout.fillHeight:true;radius:18;color:theme.elevated;border.color:theme.line
                ScrollView {anchors.fill:parent;anchors.margins:16;clip:true;contentWidth:availableWidth
                    ColumnLayout {width:244;spacing:14
                        Label {text:"FILE PREVIEW";font.pixelSize:10;color:theme.muted}
                        Image {Layout.fillWidth:true;Layout.preferredHeight:165;source:Services.preview.image?"image://thumb/"+encodeURIComponent(Services.preview.thumbnailPath):"qrc:/icons/"+(Services.preview.directory?"folder":"file")+".svg";sourceSize:Qt.size(480,320);asynchronous:true;fillMode:Image.PreserveAspectFit;visible:!!Services.preview.uri}
                        Label {text:Services.preview.name||"Select a file";font.bold:true;color:theme.ink;wrapMode:Text.Wrap;Layout.fillWidth:true}
                        Label {text:Services.preview.loading?"Reading metadata…":Services.preview.mime||"Details and quick actions appear here.";wrapMode:Text.Wrap;color:theme.muted;Layout.fillWidth:true}
                        Repeater {model:["sizeLabel","dimensions","modified","owner","group","permissions","target","filesystem"]
                            Label {required property string modelData;visible:!!Services.preview[modelData];text:modelData+"   "+(Services.preview[modelData]||"");color:theme.muted;font.pixelSize:11;wrapMode:Text.Wrap;Layout.fillWidth:true}
                        }
                        TextArea {visible:!!Services.preview.text;text:Services.preview.text||"";readOnly:true;textFormat:TextEdit.PlainText;wrapMode:TextEdit.Wrap;Layout.fillWidth:true;Layout.maximumHeight:260;font.family:"monospace";font.pixelSize:11;selectByMouse:true}
                        ActionButton {text:"Open";Layout.fillWidth:true;enabled:!!Services.preview.uri;onClicked:Services.open(Services.preview.uri)}
                        ActionButton {text:"Properties & preview";Layout.fillWidth:true;enabled:!!Services.preview.uri;onClicked:propertiesDialog.open()}
                        ActionButton {text:"Open terminal here";Layout.fillWidth:true;onClicked:Services.terminal(app.activePane.location)}
                    }
                }
            }
        }
        Rectangle {Layout.fillWidth:true;Layout.preferredHeight:app.pocket?80:58;radius:22;color:theme.elevated;border.color:theme.line
            RowLayout {anchors.fill:parent;anchors.margins:6;spacing:2
                ActionButton {Layout.fillWidth:true;Layout.fillHeight:true;flat:true;text:app.activePane.selection.length?"Copy":"＋ New";onClicked:app.activePane.selection.length?Services.clipboard(app.activePane.selectedUris,false):newMenu.popup()}
                ActionButton {Layout.fillWidth:true;Layout.fillHeight:true;flat:true;text:app.activePane.selection.length?"Move":"Select";onClicked:{if(app.activePane.selection.length)Services.clipboard(app.activePane.selectedUris,true);else app.activePane.selecting=!app.activePane.selecting}}
                ActionButton {Layout.fillWidth:true;Layout.fillHeight:true;flat:true;text:app.activePane.selection.length?"Trash":"Sort";onClicked:app.activePane.selection.length?app.askDelete("trash"):sortMenu.popup()}
                ActionButton {Layout.fillWidth:true;Layout.fillHeight:true;flat:true;text:app.activePane.selection.length?"Details":"View";onClicked:{if(app.activePane.selection.length){Services.inspect(app.activePane.selection[0].uri);propertiesDialog.open()}else viewMenu.popup()}}
                ActionButton {Layout.fillWidth:true;Layout.fillHeight:true;flat:true;text:app.activePane.selection.length?"Actions":"More";onClicked:app.activePane.selection.length?contextMenu.popup():moreMenu.popup()}
            }
        }
        Label {Layout.fillWidth:true;visible:Services.message.length>0;text:Services.message;color:theme.muted;elide:Text.ElideRight;maximumLineCount:2;wrapMode:Text.Wrap
            TapHandler {onTapped:messageDialog.open()}
        }
    }
    Menu {id:newMenu;MenuItem {text:"New folder";onTriggered:app.prompt("mkdir")}MenuItem {text:"New empty file";onTriggered:app.prompt("touch")}MenuItem {text:"New symbolic link";onTriggered:app.prompt("symlink")}MenuItem {text:"Paste here";onTriggered:app.doPaste()}}
    Menu {id:sortMenu
        Repeater {model:["Name","Size","Type","Date modified"];MenuItem {required property string modelData;required property int index;text:modelData;checkable:true;checked:app.activePane.sorting===index;onTriggered:app.activePane.sorting=index}}
        MenuSeparator {}
        MenuItem {text:"Descending";checkable:true;checked:app.activePane.descending;onTriggered:app.activePane.descending=checked}
        MenuItem {text:"Folders always appear first";enabled:false}
    }
    Menu {id:viewMenu
        Repeater {model:["Grid","Detailed list","Compact list"];MenuItem {required property string modelData;required property int index;text:modelData;checkable:true;checked:app.activePane.viewMode===index;onTriggered:app.activePane.viewMode=index}}
        MenuSeparator {}
        MenuItem {text:"Hidden files";checkable:true;checked:app.activePane.hidden;onTriggered:app.activePane.hidden=checked}
        MenuItem {text:"Search subfolders";checkable:true;checked:app.activePane.recursive;onTriggered:app.activePane.recursive=checked}
    }
    Menu {id:moreMenu
        MenuItem {text:"Paste";onTriggered:app.doPaste()}
        MenuItem {text:"Select all";onTriggered:app.activePane.selectAll()}
        MenuItem {text:"Clear selection";onTriggered:{app.activePane.selection=[];app.activePane.selecting=false}}
        MenuItem {text:"New tab";onTriggered:app.newTab(app.activePane.location)}
        MenuItem {text:"Duplicate tab";onTriggered:app.newTab(app.activePane.location)}
        MenuItem {text:"Restore closed tab";enabled:app.closedTabs.length>0;onTriggered:app.restoreTab()}
        MenuItem {text:"Bookmark this folder";onTriggered:Services.bookmark(app.activePane.location)}
        MenuItem {text:"Connect to server…";onTriggered:networkDialog.open()}
        MenuItem {text:"Storage controls…";onTriggered:storageDialog.open()}
        MenuSeparator {}
        MenuItem {text:"Dark theme";checkable:true;checked:app.dark;onTriggered:app.dark=checked}
        MenuItem {text:"Developer mode";checkable:true;checked:app.developer;onTriggered:app.developer=checked}
        MenuItem {text:"Automatic layout";onTriggered:app.presentation="auto"}
        MenuItem {text:"Pocket layout";onTriggered:app.presentation="pocket"}
        MenuItem {text:"EtherAir desktop layout";onTriggered:app.presentation="desktop"}
        MenuItem {text:"Cancel background task";onTriggered:Services.cancelTask()}
    }
    Menu {id:contextMenu
        MenuItem {text:"Open";enabled:app.activePane.selection.length===1;onTriggered:app.activePane.openEntry(app.activePane.selection[0])}
        MenuItem {text:"Open with…";enabled:app.activePane.selection.length===1;onTriggered:{app.openWithApps=Services.applications(app.activePane.selectedUris[0]);openWithDialog.open()}}
        MenuItem {text:"Copy";onTriggered:Services.clipboard(app.activePane.selectedUris,false)}
        MenuItem {text:"Cut / move";onTriggered:Services.clipboard(app.activePane.selectedUris,true)}
        MenuItem {text:"Paste here";onTriggered:app.doPaste()}
        MenuItem {text:"Rename…";enabled:app.activePane.selection.length===1;onTriggered:app.prompt("rename")}
        MenuItem {text:"Move to Trash…";onTriggered:app.askDelete("trash")}
        MenuItem {text:"Restore from Trash";visible:app.activePane.location.startsWith("trash:");onTriggered:Operations.submit("restore",app.activePane.selectedUris)}
        MenuItem {text:"Permanently delete…";onTriggered:app.askDelete("delete")}
        MenuItem {text:"Properties & preview";onTriggered:{Services.inspect(app.activePane.selection[0].uri);propertiesDialog.open()}}
        MenuSeparator {}
        MenuItem {text:"Copy to other pane";visible:app.split&&!app.pocket;onTriggered:Operations.submit("copy",app.activePane.selectedUris,app.activePane===leftPane?rightPane.location:leftPane.location)}
        MenuItem {text:"Move to other pane";visible:app.split&&!app.pocket;onTriggered:Operations.submit("move",app.activePane.selectedUris,app.activePane===leftPane?rightPane.location:leftPane.location)}
        MenuItem {text:"Extract archive here";enabled:app.activePane.selection.length===1;onTriggered:Services.extract(app.activePane.selectedUris[0],app.activePane.location)}
        MenuItem {text:"Create ZIP archive…";onTriggered:app.prompt("archive")}
        MenuItem {text:"Copy full paths";onTriggered:Services.copyText(app.activePane.selection.map(e=>e.path||e.uri).join("\n"))}
        MenuItem {text:"Copy filenames";onTriggered:Services.copyText(app.activePane.selection.map(e=>e.name).join("\n"))}
        MenuItem {text:"Copy directory path";onTriggered:Services.copyText(decodeURIComponent(app.activePane.location.replace("file://","")))}
        MenuItem {text:"Open terminal here";onTriggered:Services.terminal(app.activePane.location)}
        MenuItem {text:"SHA-256";visible:app.developer;enabled:app.activePane.selection.length===1;onTriggered:Services.hash(app.activePane.selectedUris[0],false)}
        MenuItem {text:"SHA-512";visible:app.developer;enabled:app.activePane.selection.length===1;onTriggered:Services.hash(app.activePane.selectedUris[0],true)}
        MenuItem {text:"Change permissions…";visible:app.developer;onTriggered:app.prompt("permissions")}
    }
    Dialog {id:nameDialog;anchors.centerIn:parent;width:Math.min(app.width-32,440);modal:true;title:app.promptAction==="permissions"?"Set permissions (non-recursive)":app.promptAction==="archive"?"Create ZIP archive":app.promptAction==="rename"?"Rename":app.promptAction==="symlink"?"New symbolic link":app.promptAction==="mkdir"?"New folder":"New empty file";standardButtons:Dialog.Ok|Dialog.Cancel
        ColumnLayout {width:parent.width
            EntryField {id:nameField;Layout.fillWidth:true;selectByMouse:true;onAccepted:app.promptAction==="symlink"?linkTarget.forceActiveFocus():nameDialog.accept();placeholderText:app.promptAction==="permissions"?"Octal mode, e.g. 644":"Name"}
            EntryField {id:linkTarget;Layout.fillWidth:true;visible:app.promptAction==="symlink";placeholderText:"Link target: absolute or relative path"}
        }
        onOpened:{nameField.forceActiveFocus();nameField.selectAll()}
        onAccepted:{if(app.promptAction==="archive")Services.createArchive(app.activePane.selectedUris,app.activePane.location,nameField.text);else Operations.submit(app.promptAction,app.promptAction==="symlink"?[linkTarget.text]:app.promptAction==="rename"||app.promptAction==="permissions"?app.activePane.selectedUris:[],app.activePane.location,nameField.text)}
    }
    Dialog {id:searchDialog;anchors.centerIn:parent;width:Math.min(app.width-32,460);modal:true;title:"Search filters";standardButtons:Dialog.Ok|Dialog.Cancel|Dialog.Reset
        ColumnLayout {width:parent.width;spacing:8
            ComboBox {id:searchScope;Layout.fillWidth:true;model:["Current folder","Current folder and subfolders","Home and subfolders"];currentIndex:app.activePane.recursive?1:0}
            EntryField {id:extensionFilter;Layout.fillWidth:true;placeholderText:"Extension, e.g. pdf";text:app.activePane.filters.extension||""}
            EntryField {id:mimeFilter;Layout.fillWidth:true;placeholderText:"MIME type or prefix, e.g. image/";text:app.activePane.filters.mime||""}
            EntryField {id:minFilter;Layout.fillWidth:true;placeholderText:"Minimum bytes";inputMethodHints:Qt.ImhDigitsOnly;validator:RegularExpressionValidator {regularExpression:/[0-9]*/}}
            EntryField {id:maxFilter;Layout.fillWidth:true;placeholderText:"Maximum bytes";inputMethodHints:Qt.ImhDigitsOnly;validator:RegularExpressionValidator {regularExpression:/[0-9]*/}}
            EntryField {id:afterFilter;Layout.fillWidth:true;placeholderText:"Modified on/after YYYY-MM-DD";validator:RegularExpressionValidator {regularExpression:/[0-9]{4}-[0-9]{2}-[0-9]{2}/}}
            EntryField {id:beforeFilter;Layout.fillWidth:true;placeholderText:"Modified on/before YYYY-MM-DD";validator:RegularExpressionValidator {regularExpression:/[0-9]{4}-[0-9]{2}-[0-9]{2}/}}
            CheckBox {id:searchHidden;text:"Include hidden files";checked:app.activePane.hidden}
        }
        onReset:{app.activePane.filters={};extensionFilter.clear();mimeFilter.clear();minFilter.clear();maxFilter.clear();afterFilter.clear();beforeFilter.clear();close()}
        onAccepted:{
            var filter={extension:extensionFilter.text,mime:mimeFilter.text,after:afterFilter.text,before:beforeFilter.text}
            if(minFilter.text)filter.minimum=Number(minFilter.text)
            if(maxFilter.text)filter.maximum=Number(maxFilter.text)
            if(searchScope.currentIndex===2)app.activePane.navigate(Services.home)
            app.activePane.recursive=searchScope.currentIndex>0;app.activePane.hidden=searchHidden.checked;app.activePane.filters=filter
        }
    }
    Dialog {id:deleteDialog;anchors.centerIn:parent;width:Math.min(app.width-32,460);modal:true;title:app.confirmAction==="trash"?"Move to Trash?":"Permanently delete?";standardButtons:Dialog.Ok|Dialog.Cancel
        Label {width:parent.width;wrapMode:Text.Wrap;text:app.activePane.selection.length+" selected item(s).\n"+(app.confirmAction==="trash"?"Items can be restored from Trash when supported by this filesystem.":"This removes files and folder contents permanently. It cannot be undone.")}
        onAccepted:Operations.submit(app.confirmAction,app.activePane.selectedUris)
    }
    Dialog {id:conflictDialog;anchors.centerIn:parent;width:Math.min(app.width-32,500);modal:true;closePolicy:Popup.NoAutoClose;title:"A destination already exists"
        ColumnLayout {width:parent.width;spacing:12
            Label {Layout.fillWidth:true;text:"Incoming: "+(Operations.conflict.source||"")+"\n\nExisting: "+(Operations.conflict.destination||"");wrapMode:Text.Wrap}
            CheckBox {id:applyRemaining;text:"Apply to remaining conflicts"}
            RowLayout {Layout.fillWidth:true
                EntryField {id:incomingName;Layout.fillWidth:true;placeholderText:"A different incoming filename"}
                ActionButton {text:"Rename incoming";enabled:incomingName.text.length>0&&!incomingName.text.includes('/');onClicked:Operations.resolve("rename:"+incomingName.text,false)}
            }
            Flow {Layout.fillWidth:true;spacing:8
                ActionButton {text:"Replace file";onClicked:Operations.resolve("replace",applyRemaining.checked)}
                ActionButton {text:"Skip";onClicked:Operations.resolve("skip",applyRemaining.checked)}
                ActionButton {text:"Keep both";onClicked:Operations.resolve("keep",applyRemaining.checked)}
                ActionButton {text:"Cancel operation";onClicked:Operations.resolve("cancel",false)}
            }
            Label {text:"Directories are never replaced as a whole.";color:theme.muted}
        }
        onOpened:{applyRemaining.checked=false;incomingName.clear()}
    }
    Dialog {id:openWithDialog;anchors.centerIn:parent;width:Math.min(app.width-32,460);modal:true;title:"Open with";standardButtons:Dialog.Close
        ColumnLayout {width:parent.width;spacing:8
            Repeater {model:app.openWithApps;ActionButton {required property var modelData;Layout.fillWidth:true;text:modelData.name;onClicked:{Services.openWith(app.activePane.selectedUris[0],modelData.id);openWithDialog.close()}}}
            Label {visible:app.openWithApps.length===0;text:"No applications registered for this file type.";wrapMode:Text.Wrap;Layout.fillWidth:true}
        }
    }
    Dialog {id:networkDialog;anchors.centerIn:parent;width:Math.min(app.width-32,480);modal:true;title:"Connect to server";standardButtons:Dialog.Ok|Dialog.Cancel
        ColumnLayout {width:parent.width;spacing:12
            Label {text:"SFTP · SMB · WebDAV";color:theme.muted}
            EntryField {id:networkUri;Layout.fillWidth:true;placeholderText:"sftp://host:22/path or smb://host/share";selectByMouse:true}
            EntryField {id:networkUser;Layout.fillWidth:true;placeholderText:"Username"}
            EntryField {id:networkPassword;Layout.fillWidth:true;placeholderText:"Password (optional for existing SSH key)";echoMode:TextInput.Password}
            Label {Layout.fillWidth:true;wrapMode:Text.Wrap;text:"GVfs uses system SSH keys and certificate checks. Unknown or changed identities require verification in a system client. Passwords are never saved by EtherFiles.";font.pixelSize:11;color:theme.muted}
        }
        onAccepted:{Services.connectNetwork(networkUri.text,networkUser.text,networkPassword.text);networkPassword.clear()}
        onRejected:networkPassword.clear()
    }
    Dialog {id:storageDialog;anchors.centerIn:parent;width:Math.min(app.width-32,500);modal:true;title:"Storage services";standardButtons:Dialog.Close
        ColumnLayout {width:parent.width;spacing:12
            Label {Layout.fillWidth:true;wrapMode:Text.Wrap;text:"Discovered removable filesystems. Requests use your system authorization agent. Unmount before ejecting."}
            Repeater {model:Services.removable
                ColumnLayout {required property var modelData;Layout.fillWidth:true
                    Label {text:modelData.name+" · "+modelData.type;color:theme.ink}
                    RowLayout {ActionButton {text:"Mount";onClicked:Services.storageAction(modelData.block,"Mount")}ActionButton {text:"Unmount";onClicked:Services.storageAction(modelData.block,"Unmount")}ActionButton {text:"Eject";onClicked:Services.storageAction(modelData.block,"Eject")}}
                }
            }
            Label {visible:Services.removable.length===0;text:"No removable filesystems detected.";color:theme.muted}
            ActionButton {text:"Refresh";onClicked:Services.refreshDevices()}
        }
    }
    Dialog {id:propertiesDialog;anchors.centerIn:parent;width:Math.min(app.width-24,660);height:Math.min(app.height-40,700);modal:true;title:"Properties & preview";standardButtons:Dialog.Close
        ScrollView {anchors.fill:parent;contentWidth:availableWidth;clip:true
            ColumnLayout {width:propertiesDialog.availableWidth;spacing:12
                Image {visible:!!Services.preview.image;source:Services.preview.thumbnailPath?"image://thumb/"+encodeURIComponent(Services.preview.thumbnailPath):"";Layout.fillWidth:true;Layout.preferredHeight:220;fillMode:Image.PreserveAspectFit;asynchronous:true;sourceSize:Qt.size(800,600)}
                TextArea {Layout.fillWidth:true;readOnly:true;selectByMouse:true;textFormat:TextEdit.PlainText;wrapMode:TextEdit.Wrap;text:Object.keys(Services.preview).filter(k=>k!=="text"&&k!=="image").map(k=>k+": "+Services.preview[k]).join("\n");font.pixelSize:12}
                TextArea {Layout.fillWidth:true;visible:!!Services.preview.text;text:Services.preview.text||"";textFormat:TextEdit.PlainText;readOnly:true;selectByMouse:true;wrapMode:TextEdit.Wrap;font.family:"monospace";font.pixelSize:12}
                ActionButton {text:"Open with default application";onClicked:Services.open(Services.preview.uri)}
            }
        }
    }
    Dialog {id:messageDialog;anchors.centerIn:parent;width:Math.min(app.width-32,650);modal:true;title:"Background task result";standardButtons:Dialog.Close
        TextArea {width:parent.width;text:Services.message;readOnly:true;selectByMouse:true;wrapMode:TextEdit.Wrap;textFormat:TextEdit.PlainText}
    }
    Drawer {id:placesDrawer;width:Math.min(app.width-40,310);height:app.height
        ScrollView {anchors.fill:parent;contentWidth:availableWidth
            ColumnLayout {width:placesDrawer.width-20;spacing:6
                Label {text:"Places";font.pixelSize:24;Layout.margins:16;color:theme.ink}
                Repeater {model:Services.places;PlaceDelegate {required property var modelData;Layout.fillWidth:true;text:modelData.icon+"  "+modelData.name;implicitHeight:50;onClicked:{app.activePane.navigate(modelData.uri);placesDrawer.close()}}}
                Label {text:"Favourites";Layout.margins:12;color:theme.muted}
                Repeater {model:Services.bookmarks;PlaceDelegate {required property var modelData;Layout.fillWidth:true;text:modelData.name;implicitHeight:50;onClicked:{app.activePane.navigate(modelData.uri);placesDrawer.close()}}}
                Label {text:"Devices";Layout.margins:12;color:theme.muted}
                Repeater {model:Services.devices;PlaceDelegate {required property var modelData;Layout.fillWidth:true;text:modelData.name;implicitHeight:50;onClicked:{app.activePane.navigate(modelData.uri);placesDrawer.close()}}}
                ActionButton {text:"Connect to server";onClicked:{placesDrawer.close();networkDialog.open()}}
            }
        }
    }
    Drawer {id:jobsDrawer;edge:Qt.RightEdge;width:Math.min(app.width-24,480);height:app.height
        ColumnLayout {anchors.fill:parent;anchors.margins:16;spacing:12
            Label {text:"File operations";font.pixelSize:22;color:theme.ink}
            ListView {Layout.fillWidth:true;Layout.fillHeight:true;clip:true;spacing:12;model:Operations.jobs
                delegate:Frame {required property var modelData;width:ListView.view.width
                    ColumnLayout {width:parent.width
                        Label {text:modelData.action+" · "+modelData.state;font.bold:true;color:theme.ink}
                        Label {text:modelData.current||modelData.destination||"";Layout.fillWidth:true;wrapMode:Text.Wrap;color:theme.muted;font.pixelSize:11}
                        ProgressBar {Layout.fillWidth:true;value:modelData.bytesTotal>0?modelData.bytes/modelData.bytesTotal:0;indeterminate:modelData.state==="Queued"}
                        Label {text:modelData.done+" / "+modelData.total+" items";color:theme.muted}
                        Label {visible:!!modelData.speed;text:(modelData.speed||0)+" B/s · about "+(modelData.eta||0)+" s for this file";color:theme.muted;font.pixelSize:11}
                        Label {visible:modelData.errors&&modelData.errors.length>0;text:modelData.errors?modelData.errors.join("\n"):"";Layout.fillWidth:true;wrapMode:Text.Wrap;color:theme.danger}
                        ActionButton {visible:modelData.state==="Running"||modelData.state==="Queued";text:"Cancel";onClicked:Operations.cancel(modelData.id)}
                    }
                }
                Label {visible:Operations.jobs.length===0;anchors.centerIn:parent;text:"No file operations yet";color:theme.muted}
            }
        }
    }
}
