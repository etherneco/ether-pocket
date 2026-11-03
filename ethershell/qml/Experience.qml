import QtQuick
import "../ethernotifications" as NotificationUi
import QtQuick.Controls
import QtQuick.Layouts
import QtQuick.Window
import "../etherpower" as PowerUi
import "../etherphone" as PhoneUi

ApplicationWindow {
    id: root
    objectName: "experience"
    title: "EtherShell 2 · Workspace"
    visible: true
    flags: Qt.Window | Qt.FramelessWindowHint
    property bool homeLocked: !!Core.preferences.homeLocked
    onClosing: close=>{if(homeLocked)close.accepted=false}
    onHomeLockedChanged: {if(homeLocked)home("home");else Core.configureWindow(root,"unlock-home")}
    property real unit: Math.max(1,Math.min(screen.width/460,screen.height/780))*Number(Core.preferences.scale)
    property bool homeShown: visibility!==Window.Minimized && visible
    property bool textEditing: false
    function requestAutomaticKeyboard(editable) {
        textEditing=editable
        const allowed=editable && Core.preferences.autoKeyboard && !Core.physicalKeyboardConnected && !Core.preferences.homeLocked
        if(allowed && !keyboardVisible){automaticKeyboardOpened=true;keyboardVisible=true}
        else if(!allowed && automaticKeyboardOpened){keyboardVisible=false;automaticKeyboardOpened=false}
    }
    onKeyboardVisibleChanged: if(!keyboardVisible)automaticKeyboardOpened=false
    property bool keyboardVisible: false
    property bool automaticKeyboardOpened: false
    property bool sidebarVisible: false
    property bool overviewVisible: false
    property bool quickVisible: false
    property bool menuVisible: false
    property bool dockExpanded: false
    property string page: "home"
    property string query: ""
    property string toast: ""
    property string closeCandidate: ""
    property var menuWindow: ({})
    property int previewRevision: 0
    property string clock: Qt.formatDateTime(new Date(),"ddd, d MMM  ·  HH:mm")
    property bool terminalActive: Pocket.activeProfile.keyboard==="terminal"
    property bool full: !!Pocket.activeWindow.fullscreen && !homeShown
    property var order: Core.preferences.dockOrder
    DesignTokens {id: theme}
    property real notificationSafeTop: chrome.visible?chrome.height:0
    NotificationUi.NotificationBanner {host:root}
    PhoneUi.IncomingOverlay {control:Phone;locked:root.homeLocked||!!LockControl.state.locked}
    Connections {target:Phone;function onIncoming(){root.showNormal();root.raise();root.requestActivate()}}
    property rect homeGeometry: homeLocked?Qt.rect(screen.virtualX,screen.virtualY,screen.width,screen.height):Qt.rect(screen.virtualX,screen.virtualY+chrome.height,screen.width,Math.max(100,screen.height-chrome.height-dock.height-(keyboardVisible?keyboard.height:0)))
    x: homeGeometry.x;y: homeGeometry.y
    width: homeGeometry.width;height: homeGeometry.height
    function fitHome(){x=homeGeometry.x;y=homeGeometry.y;width=homeGeometry.width;height=homeGeometry.height}
    onHomeGeometryChanged: Qt.callLater(fitHome)
    onXChanged: Qt.callLater(fitHome)
    onYChanged: Qt.callLater(fitHome)
    onWidthChanged: Qt.callLater(fitHome)
    onHeightChanged: Qt.callLater(fitHome)
    color: theme.surface
    Component.onCompleted: {Core.configureWindow(root,"home");updatePresentation()}
    function updatePresentation(){Pocket.presentation(Math.round(8*unit),Math.round(14*unit),Core.preferences.previews,Core.preferences.lowPower);if(NativeFrames)Core.nativeFrameTheme(Pocket.external)}
    Connections {target:Pocket;function onChanged(){if(NativeFrames)Core.nativeFrameTheme(Pocket.external)}}
    onUnitChanged: updatePresentation()
    onTerminalActiveChanged: if(keyboardVisible)keyboard.terminal=terminalActive
    Connections {target:Core;function onPreferencesChanged(){root.updatePresentation()}}
    Connections {
        target:Core
        function onTextInputFocus(editable){root.requestAutomaticKeyboard(editable)}
        function onPhysicalKeyboardChanged(){root.requestAutomaticKeyboard(root.textEditing)}
        function onPreferencesChanged(){root.requestAutomaticKeyboard(root.textEditing)}
    }
    Connections {target:LockControl;function onChanged(){if(LockControl.state.locked)Core.configureWindow(root,"unlock-home")}}
    Timer {interval:250;running:root.homeLocked&&!LockControl.state.locked;repeat:true;triggeredOnStart:true;onTriggered:{if(!root.homeShown||root.page!=="home")root.home("home");Core.configureWindow(root,"lock-home")}}
    Timer {interval:30000;running:true;repeat:true;onTriggered:root.clock=Qt.formatDateTime(new Date(),"ddd, d MMM  ·  HH:mm")}
    function home(destination){if(destination==="network"){settingsWorkspace.go("network");destination="settings"}page=homeLocked?"home":destination||"home";showNormal();raise();requestActivate();overviewVisible=false;quickVisible=false;sidebarVisible=false}
    function launch(id){if(homeLocked)return;Core.launch(id);root.hide();sidebarVisible=false}
    function showMenu(id){menuWindow=id?Pocket.windows.find(w=>w.id===id)||({}):Object.assign({},Pocket.activeWindow);menuVisible=true}
    function key(symbol,ctrl,alt,shift){Core.key(symbol,!!ctrl,!!alt,!!shift)}
    function back(){if(homeShown&&page!=="home")home("home");else key(terminalActive?"Escape":"Left",false,!terminalActive,false)}
    function navigate(direction){
        if(direction==="back")back()
        else if(direction==="next"||direction==="previous"){Pocket.action(direction);root.hide()}
        else if(direction==="overview"){overviewVisible=true;previewRevision++}
        else if(direction==="quick")quickVisible=true
        else if(direction==="menu")showMenu("")
        else {dockExpanded=true;dockDelay.restart()}
    }
    function dockAction(action){
        if(action==="keyboard")keyboardVisible=!keyboardVisible
        else if(action==="tasks"){overviewVisible=!overviewVisible;previewRevision++}
        else if(action==="settings")quickVisible=!quickVisible
        else home(action)
    }
    function favorite(id){let f=Core.preferences.favorites.slice(),i=f.indexOf(id);if(i<0)f.push(id);else f.splice(i,1);Core.setting("favorites",f)}
    component Heading: Text {color:theme.ink;font.pixelSize:25*theme.fontScale;font.weight:Font.DemiBold;Layout.fillWidth:true}
    component Caption: Text {color:theme.muted;font.pixelSize:12*theme.fontScale;wrapMode:Text.WordWrap;Layout.fillWidth:true;textFormat:Text.PlainText}
    component Tile: Item {
        id: tile;required property var app
        width:92;height:108
        Column {anchors.fill:parent;spacing:9
            GlassPanel {tokens:theme;anchors.horizontalCenter:parent.horizontalCenter;width:62;height:62;radius:20
                Image {anchors.centerIn:parent;width:38;height:38;source:"image://icons/"+tile.app.icon;sourceSize:Qt.size(96,96)}
                Rectangle {visible:Core.preferences.favorites.indexOf(tile.app.id)>=0;anchors.right:parent.right;anchors.top:parent.top;width:9;height:9;radius:5;color:theme.accent}
            }
            Text {text:tile.app.name;width:parent.width;height:32;horizontalAlignment:Text.AlignHCenter;wrapMode:Text.WordWrap;maximumLineCount:2;elide:Text.ElideRight;color:theme.ink;font.pixelSize:11*theme.fontScale}
        }
        MouseArea {anchors.fill:parent;onClicked:root.launch(tile.app.id);onPressAndHold:root.favorite(tile.app.id)}
        Accessible.name:app.name
    }

    Rectangle {visible:root.homeLocked&&Notifications.state.locked&&((Notifications.state.unread||0)>0||(Notifications.state.cards||[]).length>0);anchors.horizontalCenter:parent.horizontalCenter;anchors.top:parent.top;anchors.topMargin:80*root.unit;width:Math.min(parent.width-32*root.unit,480*root.unit);height:Math.min(parent.height-100*root.unit,560*root.unit);radius:16;color:"#f5f8fc";z:50
        NotificationUi.NotificationCenter {anchors.fill:parent}
    }
    // Real client windows sit above these backgrounds, independently of Qt.
    PowerUi.PowerMenu {id:powerMenu;uiScale:root.unit}
    Instantiator {
        model: AvailableScreens
        delegate: Window {
            id: background;required property var modelData
            screen:modelData;visible:true;title:"EtherShell 2 · Background"
            transientParent:null;flags:Qt.Window|Qt.FramelessWindowHint
            x:screen.virtualX;y:screen.virtualY;width:screen.width;height:screen.height
            Component.onCompleted: Core.configureWindow(background,"desktop")
            Rectangle {anchors.fill:parent;gradient:Gradient {GradientStop {position:0;color:theme.ocean} GradientStop {position:.48;color:theme.sky} GradientStop {position:1;color:theme.lavender}}}
            Image {anchors.fill:parent;source:Core.preferences.wallpaper?"file://"+Core.preferences.wallpaper:"";fillMode:Image.PreserveAspectCrop;visible:status===Image.Ready}
            Rectangle {x:parent.width*.5;y:parent.height*.14;width:parent.width*.8;height:width;radius:width/2;color:theme.cyan;opacity:.09}
            Rectangle {x:-parent.width*.35;y:parent.height*.65;width:parent.width;height:width;radius:width/2;color:theme.elevated;opacity:.14}
            Column {visible:screen.name!==root.screen.name;anchors.centerIn:parent;spacing:18
                Text {text:"EtherAir";color:theme.ink;font.pixelSize:64;font.weight:Font.Light}
                Text {text:"A wider space for your work";color:theme.muted;font.pixelSize:20}
            }
            Row {visible:!root.homeLocked&&screen.name!==root.screen.name;anchors.bottom:parent.bottom;anchors.bottomMargin:12;anchors.horizontalCenter:parent.horizontalCenter;spacing:8
                TouchAction {tokens:theme;glyph:"apps";text:"Applications";onClicked:root.home("apps")}
                TouchAction {tokens:theme;glyph:"recent";text:"Overview";onClicked:root.overviewVisible=true}
                Repeater {model:4;delegate:TouchAction {required property int index;tokens:theme;text:String(index+1);compact:true;onClicked:Core.control("workspace",String(index))}}
            }
        }
    }

    Rectangle {anchors.fill:parent;color:theme.surface}
    Item {
        enabled: !root.homeLocked
        property bool settingsActive:root.page==="settings"||root.page==="network"||root.page==="mobile"
        property real contentScale:settingsActive?Math.max(1,(root.screen.name.indexOf("DSI")===0||(!DevelopmentDesktop&&!Pocket.external)?Math.min(root.screen.width,root.screen.height)/400:root.unit))*Number(Core.preferences.scale):root.unit
        width:root.width/contentScale;height:root.height/contentScale;scale:contentScale;transformOrigin:Item.TopLeft
        ColumnLayout {anchors.top:parent.top;anchors.bottom:parent.bottom;anchors.horizontalCenter:parent.horizontalCenter;width:parent.settingsActive?parent.width:Math.min(parent.width-44,920);spacing:parent.settingsActive?0:18
            RowLayout {Layout.fillWidth:true;visible:root.page!=="settings"&&root.page!=="network"&&root.page!=="mobile"
                Heading {text:root.page==="home"?"Your space.":root.page==="apps"?"Applications":root.page==="mobile"?"Settings":root.page==="network"?"Network & Internet":root.page==="settings"?"Settings":root.page==="store"?"App Centre":root.page==="gallery"?"Images":root.page==="notices"?"Notifications":"EtherAir Touchpad"}
                TouchAction {tokens:theme;glyph:"menu";compact:true;onClicked:root.sidebarVisible=!root.sidebarVisible}
            }
            StackLayout {Layout.fillWidth:true;Layout.fillHeight:true;currentIndex:["home","apps","settings","store","touchpad","gallery","notices","network","mobile"].indexOf(root.page)
                ScrollView {id:homeScroll;objectName:"homeScroll";Layout.maximumWidth:640;Layout.alignment:Qt.AlignHCenter;clip:true;contentWidth:availableWidth;ScrollBar.horizontal.policy:ScrollBar.AlwaysOff;ColumnLayout {objectName:"homeContent";width:homeScroll.availableWidth;spacing:18
                    Caption {text:"Real Linux applications. A lighter way to move between them."}
                    GlassPanel {tokens:theme;Layout.fillWidth:true;Layout.preferredHeight:116
                        RowLayout {anchors.fill:parent;anchors.margins:18;spacing:16
                            Image {source:"qrc:/brand.png";Layout.preferredWidth:100;Layout.preferredHeight:60;fillMode:Image.PreserveAspectFit}
                            ColumnLayout {Layout.fillWidth:true
                                Text {text:"EtherPocket";color:theme.ink;font.pixelSize:23;font.weight:Font.DemiBold}
                                Caption {text:DevelopmentSession?"Isolated development session":"EtherShell 2 experimental session"}
                                Caption {text:Pocket.enabled?"EtherSurface is active":"Safe mode · automatic fitting is off"}
                            }
                        }
                    }
                    TextField {Layout.fillWidth:true;implicitHeight:48;font.pixelSize:14;placeholderText:"Find an application";onTextEdited:{root.query=text;root.page="apps"}
                        background:Rectangle {radius:24;color:theme.elevated;border.color:theme.line}
                    }
                    Caption {text:"FAVOURITES  ·  hold to customise"}
                    Flow {Layout.fillWidth:true;spacing:12
                        Repeater {model:Core.apps.filter(a=>Core.preferences.favorites.indexOf(a.id)>=0).slice(0,8);delegate:Tile {required property var modelData;app:modelData}}
                    }
                    RowLayout {Layout.fillWidth:true
                        TouchAction {tokens:theme;glyph:"terminal";text:"Terminal";Layout.fillWidth:true;Layout.preferredWidth:0;onClicked:{Core.control("terminal");root.hide()}}
                        TouchAction {tokens:theme;glyph:"files";text:"Files";Layout.fillWidth:true;Layout.preferredWidth:0;onClicked:{Core.control("files");root.hide()}}
                    }
                    TouchAction {tokens:theme;objectName:"browseApplications";glyph:"apps";text:"Browse applications";selected:true;Layout.alignment:Qt.AlignHCenter;Layout.fillWidth:true;Layout.maximumWidth:360;onClicked:root.page="apps"}
                    RowLayout {Layout.fillWidth:true
                        TouchAction {tokens:theme;glyph:"store";text:"App Centre";Layout.fillWidth:true;Layout.preferredWidth:0;onClicked:root.page="store"}
                        TouchAction {tokens:theme;glyph:"gallery";text:"Screenshots";Layout.fillWidth:true;Layout.preferredWidth:0;onClicked:{Media.scan();root.page="gallery"}}
                    }
                    Item {Layout.fillHeight:true}
                    Caption {text:"Debian · native X11 · "+Core.telemetry.hostname}
                }}
                ColumnLayout {
                    TextField {Layout.fillWidth:true;implicitHeight:48;placeholderText:"Search installed applications";text:root.query;onTextEdited:root.query=text;font.pixelSize:14}
                    Flickable {Layout.fillWidth:true;Layout.fillHeight:true;contentHeight:appFlow.height;clip:true;boundsBehavior:Flickable.StopAtBounds
                        Flow {id:appFlow;width:parent.width;spacing:12;Repeater {model:Core.apps.filter(a=>a.name.toLowerCase().indexOf(root.query.toLowerCase())>=0);delegate:Tile {required property var modelData;app:modelData}}}
                    }
                }
                SettingsWorkspace {id:settingsWorkspace;onClosed:root.home("home");onOpenMobile:section=>{root.home("mobile");mobileSettings.navigate(section)};onOpenStore:root.home("store");onKeyboardRequested:root.requestAutomaticKeyboard(true)}
                ScrollView {id:storeScroll;clip:true;contentWidth:availableWidth;ScrollBar.horizontal.policy:ScrollBar.AlwaysOff
                    ColumnLayout {width:storeScroll.availableWidth;spacing:14
                        Caption {text:Distributor.status}
                        TouchAction {tokens:theme;text:Distributor.busy?"Refreshing…":"Refresh existing catalogue";enabled:!Distributor.busy;onClicked:Distributor.refresh()}
                        Repeater {model:Distributor.catalog;delegate:GlassPanel {required property var modelData;tokens:theme;Layout.fillWidth:true;implicitHeight:content.implicitHeight+28
                            ColumnLayout {id:content;anchors.fill:parent;anchors.margins:14
                                Text {text:modelData.name;color:theme.ink;font.pixelSize:18;font.bold:true}
                                Caption {text:modelData.variants.length?modelData.variants.length+" published variants":"No project in the public catalogue"}
                                Repeater {model:modelData.variants;delegate:Caption {required property var modelData;text:modelData.name+" · "+modelData.version+" · "+modelData.platform+"\n"+modelData.reason}}
                            }
                        }}
                        Caption {text:"Installation requires a verified compatible Debian ARM64 artifact. The existing distribution service is unchanged."}
                        TouchAction {tokens:theme;text:"Open distributor";onClicked:Core.control("distributor")}
                    }
                }
                ColumnLayout {
                    Caption {text:"Your phone remains the pointer and keyboard for EtherAir."}
                    GlassPanel {tokens:theme;Layout.fillWidth:true;Layout.fillHeight:true
                        Text {anchors.centerIn:parent;text:"Touchpad";color:theme.muted;font.pixelSize:25}
                        MouseArea {anchors.fill:parent;property real px;property real py;property bool moved
                            onPressed: e=>{px=e.x;py=e.y;moved=false}
                            onPositionChanged:e=>{if(pressed){let dx=e.x-px,dy=e.y-py;if(Math.abs(dx)+Math.abs(dy)>1)moved=true;Core.pointer(Math.round(dx*2),Math.round(dy*2));px=e.x;py=e.y}}
                            onReleased:if(!moved){Core.mouse(1,true);Core.mouse(1,false)}
                            onPressAndHold:{Core.mouse(3,true);Core.mouse(3,false);moved=true}
                        }
                    }
                    RowLayout {Layout.fillWidth:true
                        TouchAction {tokens:theme;text:"Hold / drag";Layout.fillWidth:true;onPressed:Core.mouse(1,true);onReleased:Core.mouse(1,false);onCanceled:Core.mouse(1,false)}
                        TouchAction {tokens:theme;text:"Right click";Layout.fillWidth:true;onClicked:{Core.mouse(3,true);Core.mouse(3,false)}}
                    }
                }
                Gallery {ink:theme.ink;muted:theme.muted;card:theme.surface;accent:theme.accent}
                NotificationUi.NotificationCenter {}
                Item {} // Legacy route is normalized to the shared Settings workspace.
                Item {MobileNetworkSettings {id:mobileSettings;anchors.fill:parent;anchors.margins:16;onBackRequested:root.home("network");onKeyboardRequested:root.requestAutomaticKeyboard(true)}}

            }
        }
    }

    Window {
        id: chrome;title:"EtherSurface · Header";transientParent:null
        visible:!root.homeLocked&&!root.full;flags:Qt.Window|Qt.FramelessWindowHint|Qt.WindowStaysOnTopHint|Qt.WindowDoesNotAcceptFocus
        x:root.screen.virtualX;y:root.screen.virtualY;width:root.screen.width;height:(DevelopmentDesktop||FloatingWindows||root.page==="settings"||root.page==="mobile"||root.page==="network"?40:100)*root.unit;color:"transparent"
        function reserve(){Core.configureWindow(chrome,"top",visible?height:0)}
        Component.onCompleted:reserve();onVisibleChanged:reserve();onHeightChanged:reserve();onYChanged:reserve()
        MouseArea {anchors.fill:parent;property real down;onPressed:e=>down=e.y;onReleased:e=>{if(e.y-down>20)root.home("notices")}}
        Item {width:parent.width/root.unit;height:100;scale:root.unit;transformOrigin:Item.TopLeft
            RowLayout {anchors.left:parent.left;anchors.right:parent.right;anchors.top:parent.top;anchors.margins:9;height:26
                Text {text:"EtherPocket";color:"#f5faff";font.pixelSize:15;font.weight:Font.DemiBold;Layout.fillWidth:true}
                ToolButton {text:"☷ "+(Notifications.state.unread||0);font.pixelSize:12;implicitHeight:26;implicitWidth:60;onClicked:root.home("notices")}
                Text {text:root.clock;color:"#f5faff";font.pixelSize:10}
                Text {text:(LocationControl.state.active?"● LOC · ":"")+(CameraControl.state.active?"● CAM · ":"")+(AudioControl.state.recording?"● MIC · ":"")+((Share.state.active||[]).length?"Sharing · ":"")+(Core.networks.some(n=>n.active)?"Wi-Fi · ":"")+(Mobile.status.canDisconnect?(Mobile.status.technology+" · "):"")+(Core.telemetry.battery||"—")+"%";color:"#f5faff";font.pixelSize:10}
            }
            SurfaceHeader {visible:!DevelopmentDesktop&&!FloatingWindows&&root.page!=="settings"&&root.page!=="mobile"&&root.page!=="network";anchors.left:parent.left;anchors.right:parent.right;anchors.bottom:parent.bottom;anchors.margins:9;height:54;tokens:theme
                application:root.homeShown?({name:"EtherPocket",profile:"Workspace",icon:"preferences-desktop"}):Pocket.activeWindow
                onMenuRequested:root.showMenu("");onKeyboardRequested:root.keyboardVisible=!root.keyboardVisible
            }
        }
    }

    Window {
        id:dock;title:"EtherDock 2";transientParent:null;visible:!root.homeLocked
        flags:Qt.Window|Qt.FramelessWindowHint|Qt.WindowStaysOnTopHint|Qt.WindowDoesNotAcceptFocus
        property bool compact:Core.preferences.dockAutoHide&&root.full&&!root.keyboardVisible&&!root.dockExpanded
        x:root.screen.virtualX;y:root.screen.virtualY+root.screen.height-height;width:root.screen.width;height:(compact?24:88)*root.unit;color:theme.dark?theme.surface:theme.lavender
        function reserve(){Core.configureWindow(dock,"dock",visible?height:0)}
        Component.onCompleted:reserve();onVisibleChanged:reserve();onHeightChanged:reserve();onYChanged:reserve()
        GestureStrip {tokens:theme;unit:root.unit;width:parent.width;height:24*root.unit;onNavigate:direction=>root.navigate(direction)}
        Item {visible:!dock.compact;x:8*root.unit;y:28*root.unit;width:parent.width/root.unit-16;height:52;scale:root.unit;transformOrigin:Item.TopLeft
            RowLayout {anchors.fill:parent;spacing:6
                TouchAction {tokens:theme;glyph:"back";compact:true;Layout.preferredWidth:48;Layout.fillHeight:true;onClicked:root.back()}
                GlassPanel {tokens:theme;Layout.fillWidth:true;Layout.fillHeight:true;radius:26
                    Row {id:dockActions;anchors.centerIn:parent;spacing:3
                        Repeater {model:root.order;delegate:TouchAction {required property string modelData;tokens:theme;glyph:({home:"home",apps:"apps",tasks:"recent",keyboard:"keyboard",touchpad:"touchpad",settings:"settings"})[modelData];hint:({home:"Home",apps:"Applications",tasks:"Recent applications",keyboard:"Keyboard",touchpad:"Touchpad",settings:"Settings"})[modelData]+(modelData==="apps"&&Core.smsUnread>0?" · "+Core.smsUnread+" unread SMS":"");compact:true;selected:(modelData===root.page&&root.homeShown&&!root.overviewVisible&&!root.quickVisible)||(modelData==="tasks"&&root.overviewVisible)||(modelData==="settings"&&root.quickVisible)||(modelData==="keyboard"&&root.keyboardVisible);width:Math.min(44,(dockActions.parent.width-12-(root.order.length-1)*dockActions.spacing)/Math.max(1,root.order.length));height:48
                            Rectangle {visible:modelData==="apps"&&Core.smsUnread>0;anchors.right:parent.right;anchors.top:parent.top;width:20;height:20;radius:10;color:theme.accent
                                Text {anchors.centerIn:parent;text:Core.smsUnread>99?"99+":String(Core.smsUnread);color:"white";font.pixelSize:10;textFormat:Text.PlainText}
                            }
                            onClicked:root.dockAction(modelData)
                        }}
                    }
                }
                TouchAction {tokens:theme;glyph:"more";compact:true;Layout.preferredWidth:48;Layout.fillHeight:true;onClicked:root.showMenu("")}
                TouchAction {tokens:theme;objectName:"mobileDockStatus";text:"SIM";hint:(Mobile.status.operator || "Mobile Network")+" · "+(Mobile.status.signal || "Unavailable");selected:!!Mobile.status.dataActive;compact:true;Layout.preferredWidth:44;Layout.fillHeight:true;onClicked:root.home("mobile")}
            }
        }
    }
    Timer {id:dockDelay;interval:5000;onTriggered:root.dockExpanded=false}
    Keyboard {id:keyboard;settingsCompact:root.page==="settings"||root.page==="mobile"||root.page==="network";visible:root.keyboardVisible;screen:root.screen;uiScale:root.unit*Number(Core.preferences.keyboardScale);dockHeight:dock.height;dark:theme.dark;accent:theme.accent;onDismiss:root.keyboardVisible=false;onVisibleChanged:{Core.configureWindow(keyboard,"keyboard",visible?height+dockHeight:0);if(visible)terminal=root.terminalActive}}

    Window {
        id:sidebar;title:"EtherSidebar";transientParent:null;visible:!root.homeLocked&&(root.sidebarVisible||(Core.preferences.sidebarPinned&&root.screen.width>root.screen.height))
        flags:Qt.Window|Qt.FramelessWindowHint|Qt.WindowStaysOnTopHint|Qt.WindowDoesNotAcceptFocus
        x:root.screen.virtualX+8*root.unit;y:root.screen.virtualY+chrome.height+10*root.unit;width:92*root.unit;height:430*root.unit;color:"transparent"
        Component.onCompleted:Core.configureWindow(sidebar,"dock",0)
        GlassPanel {tokens:theme;anchors.fill:parent;radius:22*root.unit}
        Column {anchors.centerIn:parent;spacing:7*root.unit
            Repeater {model:[{i:"home",t:"Start",p:"home"},{i:"apps",t:"Apps",p:"apps"},{i:"files",t:"Files",p:"files"},{i:"terminal",t:"Terminal",p:"terminal"},{i:"recent",t:"Recent",p:"tasks"},{i:"settings",t:"Settings",p:"settings"}]
                delegate:Item {required property var modelData;width:76*root.unit;height:60*root.unit
                    Column {anchors.centerIn:parent;spacing:5*root.unit;Image {anchors.horizontalCenter:parent.horizontalCenter;width:25*root.unit;height:25*root.unit;source:"qrc:/icons/"+modelData.i+(theme.dark?"-light":"")+".svg"} Text {text:modelData.t;anchors.horizontalCenter:parent.horizontalCenter;color:theme.ink;font.pixelSize:10*root.unit}}
                    MouseArea {anchors.fill:parent;onClicked:{if(modelData.p==="terminal"||modelData.p==="files"){Core.control(modelData.p);root.hide()}else if(modelData.p==="tasks")root.overviewVisible=true;else root.home(modelData.p);root.sidebarVisible=false}}
                }
            }
        }
    }

    Window {
        id:overview;title:"EtherSurface · Overview";transientParent:null;visible:root.overviewVisible
        flags:Qt.Window|Qt.FramelessWindowHint|Qt.WindowStaysOnTopHint|Qt.WindowDoesNotAcceptFocus
        x:root.screen.virtualX+12*root.unit;y:root.screen.virtualY+chrome.height+8*root.unit;width:root.screen.width-24*root.unit;height:root.screen.height-chrome.height-dock.height-20*root.unit;color:"transparent"
        Component.onCompleted:Core.configureWindow(overview,"dock",0)
        Rectangle {color:theme.surface;border.color:theme.line;anchors.fill:parent;radius:24*root.unit}
        Item {width:parent.width/root.unit;height:parent.height/root.unit;scale:root.unit;transformOrigin:Item.TopLeft
            ColumnLayout {anchors.fill:parent;anchors.margins:16;spacing:14
                RowLayout {Layout.fillWidth:true;spacing:12;Heading {text:"Your applications";font.pixelSize:22*theme.fontScale;elide:Text.ElideRight} TouchAction {tokens:theme;glyph:"close";hint:"Close overview";compact:true;onClicked:root.overviewVisible=false}}
                Caption {text:Pocket.windows.length?"Choose a surface to continue":"Open an application to begin."}
                GridView {id:cards;Layout.fillWidth:true;Layout.fillHeight:true;clip:true;cellWidth:width/Math.max(1,Math.floor(width/180));cellHeight:244+48*theme.fontScale+(Pocket.external?56:0);model:Pocket.windows;boundsBehavior:Flickable.StopAtBounds
                    ScrollBar.vertical: ScrollBar {policy:ScrollBar.AsNeeded}
                    delegate:Item {required property var modelData;required property int index;width:cards.cellWidth;height:cards.cellHeight
                        Rectangle {color:theme.elevated;border.color:theme.line;anchors.fill:parent;anchors.margins:6;radius:18
                            ColumnLayout {anchors.fill:parent;anchors.margins:12;spacing:8
                                Rectangle {Layout.fillWidth:true;Layout.preferredHeight:112;radius:10;color:theme.ocean;clip:true
                                    Image {id:preview;anchors.fill:parent;source:root.overviewVisible&&Core.preferences.previews&&!Core.preferences.lowPower&&index<12?"image://windows/"+modelData.id+"?"+root.previewRevision:"";cache:false;sourceSize.width:360;fillMode:Image.PreserveAspectCrop}
                                    Image {visible:preview.status!==Image.Ready;anchors.centerIn:parent;width:42;height:42;source:"image://icons/"+modelData.icon}
                                    Text {visible:preview.status!==Image.Ready;anchors.bottom:parent.bottom;anchors.horizontalCenter:parent.horizontalCenter;anchors.bottomMargin:6;text:"Application preview unavailable";color:"white";font.pixelSize:8}
                                    MouseArea {anchors.fill:parent;onClicked:{Pocket.action("activate",modelData.id);root.overviewVisible=false;root.hide()}onPressAndHold:root.showMenu(modelData.id)}
                                }
                                Text {text:modelData.name;Layout.fillWidth:true;Layout.preferredHeight:20*theme.fontScale;color:theme.ink;font.pixelSize:14*theme.fontScale;font.bold:true;elide:Text.ElideRight;textFormat:Text.PlainText}
                                Text {text:modelData.title;Layout.fillWidth:true;Layout.preferredHeight:28*theme.fontScale;color:theme.muted;font.pixelSize:11*theme.fontScale;maximumLineCount:2;wrapMode:Text.Wrap;elide:Text.ElideRight;textFormat:Text.PlainText}
                                Item {Layout.fillHeight:true}
                                RowLayout {Layout.fillWidth:true;spacing:8
                                    TouchAction {tokens:theme;text:"Open";hint:"Open "+modelData.name;selected:true;implicitWidth:64;Layout.fillWidth:true;onClicked:{Pocket.action("activate",modelData.id);root.overviewVisible=false;root.hide()}}
                                    TouchAction {tokens:theme;glyph:"close";hint:"Close "+modelData.name;compact:true;destructive:true;onClicked:root.closeCandidate=modelData.id}
                                }
                                TouchAction {tokens:theme;visible:Pocket.external;text:"Move to EtherAir";hint:"Move "+modelData.name+" to EtherAir";Layout.fillWidth:true;onClicked:Pocket.action("external",modelData.id)}
                            }
                        }
                    }
                }
            }
        }
        Timer {interval:1500;running:overview.visible&&Core.preferences.previews&&!Core.preferences.lowPower;repeat:true;onTriggered:root.previewRevision++}
    }

    Window {
        id:windowMenu;title:"EtherSurface · Actions";transientParent:null;visible:root.menuVisible
        flags:Qt.Window|Qt.FramelessWindowHint|Qt.WindowStaysOnTopHint|Qt.WindowDoesNotAcceptFocus
        x:root.screen.virtualX+20*root.unit;y:root.screen.virtualY+chrome.height+12*root.unit;width:root.screen.width-40*root.unit;height:Math.min(560*root.unit,root.screen.height-chrome.height-dock.height-24*root.unit);color:"transparent"
        Component.onCompleted:Core.configureWindow(windowMenu,"dock",0)
        GlassPanel {tokens:theme;anchors.fill:parent;radius:24*root.unit}
        Item {width:parent.width/root.unit;height:parent.height/root.unit;scale:root.unit;transformOrigin:Item.TopLeft
            ScrollView {anchors.fill:parent;anchors.margins:18;clip:true;ColumnLayout {width:parent.width;spacing:12
                RowLayout {Heading {text:root.menuWindow.name||"Workspace"} TouchAction {tokens:theme;glyph:"close";compact:true;onClicked:root.menuVisible=false}}
                Caption {text:root.menuWindow.title||"Touch controls are always available here.";maximumLineCount:5;elide:Text.ElideRight}
                GridLayout {columns:3;Layout.fillWidth:true
                    Repeater {model:[{t:"Minimise",a:"minimize",i:"minus"},{t:"Fit",a:"maximize",i:"expand"},{t:"Restore",a:"restore",i:"recent"},{t:"Fullscreen",a:"fullscreen",i:"expand"},{t:"Top split",a:"split-top",i:"up"},{t:"Bottom split",a:"split-bottom",i:"chevron"},{t:"Move",a:"move",i:"more"},{t:"Resize",a:"resize",i:"resize"},{t:"EtherAir",a:"external",i:"external"}]
                        delegate:TouchAction {required property var modelData;tokens:theme;text:modelData.t;Layout.fillWidth:true;implicitWidth:80;enabled:!!root.menuWindow.id&&(modelData.a!=="external"||Pocket.external);onClicked:{Pocket.action(modelData.a,root.menuWindow.id);root.menuVisible=false}}
                    }
                }
                RowLayout {visible:root.menuWindow.profile==="Firefox";Layout.fillWidth:true
                    TouchAction {tokens:theme;glyph:"back";compact:true;onClicked:root.key("Left",false,true,false)}
                    TouchAction {tokens:theme;glyph:"forward";compact:true;onClicked:root.key("Right",false,true,false)}
                    TouchAction {tokens:theme;text:"−";compact:true;onClicked:root.key("minus",true,false,false)}
                    TouchAction {tokens:theme;text:"+";compact:true;onClicked:root.key("equal",true,false,false)}
                    TouchAction {tokens:theme;text:"100%";onClicked:root.key("0",true,false,false)}
                }
                RowLayout {visible:root.menuWindow.profile==="Firefox";Layout.fillWidth:true
                    TouchAction {tokens:theme;text:"Tab ‹";Layout.fillWidth:true;onClicked:root.key("Prior",true,false,false)}
                    TouchAction {tokens:theme;text:"Tab ›";Layout.fillWidth:true;onClicked:root.key("Next",true,false,false)}
                    TouchAction {tokens:theme;text:"New tab";Layout.fillWidth:true;onClicked:root.key("t",true,false,false)}
                }
                RowLayout {visible:root.menuWindow.profile==="Terminal";Layout.fillWidth:true
                    TouchAction {tokens:theme;text:"Copy";Layout.fillWidth:true;onClicked:root.key("c",true,false,true)}
                    TouchAction {tokens:theme;text:"Paste";Layout.fillWidth:true;onClicked:root.key("v",true,false,true)}
                    TouchAction {tokens:theme;text:"Scroll ↑";Layout.fillWidth:true;onClicked:root.key("Prior",false,false,true)}
                }
                RowLayout {Layout.fillWidth:true
                    TouchAction {tokens:theme;text:"Sidebar";Layout.fillWidth:true;onClicked:{root.sidebarVisible=!root.sidebarVisible;root.menuVisible=false}}
                    TouchAction {tokens:theme;text:"Notifications";Layout.fillWidth:true;onClicked:{root.home("notices");root.menuVisible=false}}
                }
                Item {Layout.fillHeight:true}
                TouchAction {tokens:theme;glyph:"close";text:"Close application…";destructive:true;enabled:!!root.menuWindow.id;Layout.fillWidth:true;onClicked:root.closeCandidate=root.menuWindow.id}
            }}
        }
    }

    Window {
        id:confirmation;title:"EtherSurface · Confirm close";transientParent:null;visible:root.closeCandidate.length>0
        flags:Qt.Window|Qt.FramelessWindowHint|Qt.WindowStaysOnTopHint|Qt.WindowDoesNotAcceptFocus
        x:root.screen.virtualX+24*root.unit;y:root.screen.virtualY+root.screen.height*.35;width:root.screen.width-48*root.unit;height:170*root.unit;color:"transparent"
        Component.onCompleted:Core.configureWindow(confirmation,"dock",0)
        GlassPanel {tokens:theme;anchors.fill:parent;radius:24*root.unit}
        Item {width:parent.width/root.unit;height:170;scale:root.unit;transformOrigin:Item.TopLeft;ColumnLayout {anchors.fill:parent;anchors.margins:20;spacing:12
            Heading {text:"Close this application?";font.pixelSize:20}
            Caption {text:"The application can still ask you to save your work."}
            RowLayout {Layout.fillWidth:true
                TouchAction {tokens:theme;text:"Keep open";Layout.fillWidth:true;onClicked:root.closeCandidate=""}
                TouchAction {tokens:theme;text:"Close";destructive:true;Layout.fillWidth:true;onClicked:{Pocket.action("close",root.closeCandidate);root.closeCandidate="";root.menuVisible=false}}
            }
        }}
    }

    Window {
        id:quick;title:"EtherControl 2";transientParent:null;visible:root.quickVisible
        flags:Qt.Window|Qt.FramelessWindowHint|Qt.WindowStaysOnTopHint|Qt.WindowDoesNotAcceptFocus
        x:root.screen.virtualX+16*root.unit;y:root.screen.virtualY+42*root.unit;width:root.screen.width-32*root.unit;height:Math.min(590*root.unit,root.screen.height-dock.height-60*root.unit);color:"transparent"
        Component.onCompleted:Core.configureWindow(quick,"dock",0)
        GlassPanel {tokens:theme;anchors.fill:parent;radius:26*root.unit}
        Item {width:parent.width/root.unit;height:parent.height/root.unit;scale:root.unit;transformOrigin:Item.TopLeft
            ScrollView {id:quickScroll;anchors.fill:parent;anchors.margins:20;clip:true;contentWidth:availableWidth
            ColumnLayout {width:quickScroll.availableWidth;spacing:14
                RowLayout {Heading {text:"EtherControl"} TouchAction {tokens:theme;glyph:"close";compact:true;onClicked:root.quickVisible=false}}
                RowLayout {Layout.fillWidth:true
                    TouchAction {tokens:theme;text:"Notifications · "+(Notifications.state.unread||0);Layout.fillWidth:true;onClicked:root.home("notices")}
                    TouchAction {tokens:theme;text:Notifications.state.dnd==="off"?"DND off":"DND on";Layout.fillWidth:true;onClicked:Notifications.configure({dnd:Notifications.state.dnd==="off"?"priority":"off",manualDnd:true})}
                }
                RowLayout {Layout.fillWidth:true
                    TouchAction {tokens:theme;text:(Notifications.state.config||{}).silent?"Silent ON":"Silent";Layout.fillWidth:true;onClicked:Notifications.configure({silent:!(Notifications.state.config||{}).silent})}
                    TouchAction {tokens:theme;text:"Clear notifications";Layout.fillWidth:true;onClicked:Notifications.command("clear")}
                }
                Caption {text:(Core.telemetry.battery||"—")+"% battery  ·  "+(Core.telemetry.charging||"Status unavailable")}
                RowLayout {Layout.fillWidth:true
                    TouchAction {tokens:theme;glyph:"wifi";text:"Wi-Fi";selected:Core.networks.some(n=>n.active);Layout.fillWidth:true;onClicked:{Core.control("network-settings");root.quickVisible=false}}
                    TouchAction {tokens:theme;glyph:"bluetooth";text:"Bluetooth";enabled:Core.telemetry.bluetooth;Layout.fillWidth:true;onClicked:{Core.control("bluetooth-settings");root.quickVisible=false}}
                }
                Caption {visible:!Core.telemetry.bluetooth;text:"Bluetooth controller is unavailable on this system."}
                RowLayout {Layout.fillWidth:true
                    TouchAction {tokens:theme;objectName:"mobileQuickToggle";text:Mobile.status.dataActive?"Mobile data ON":Mobile.status.dataPending?"Mobile data connecting":"Mobile data OFF";selected:!!Mobile.status.dataActive;Layout.fillWidth:true;enabled:!Mobile.busy&&(Mobile.status.canConnect||Mobile.status.canDisconnect);onClicked:{root.home("mobile");mobileSettings.toggleData()}}
                    TouchAction {tokens:theme;text:"Mobile Network";Layout.fillWidth:true;onClicked:root.home("mobile")}
                }
                Caption {text:(Mobile.status.operator || "Mobile unavailable")+" · "+(Mobile.status.technology || "Unavailable")+" · "+(Mobile.status.signal || "Unavailable")+(Mobile.status.roaming?" · ROAMING":"")}

                RowLayout {Layout.fillWidth:true
                    TouchAction {tokens:theme;objectName:"usbSharingQuick";text:(Share.state.active||[]).some(x=>x.method==="usb")?"USB sharing ON":"USB sharing OFF";Layout.fillWidth:true;selected:(Share.state.active||[]).some(x=>x.method==="usb");enabled:!!Share.state.usbReady&&!Share.busy&&!DevelopmentSession;onClicked:{let active=(Share.state.active||[]).some(x=>x.method==="usb");let usb=(Share.state.interfaces||[]).find(x=>x.kind==="usb");if(active)Share.stop("usb");else if(usb)Share.start("usb",usb.interface,false)}}
                    TouchAction {tokens:theme;text:(Share.state.active||[]).some(x=>x.method==="hotspot")?"Hotspot ON":"Hotspot";Layout.fillWidth:true;selected:(Share.state.active||[]).some(x=>x.method==="hotspot");onClicked:{root.home("settings");settingsWorkspace.go("sharing")}}
                }
                TouchAction {tokens:theme;text:"Internet Sharing";Layout.fillWidth:true;onClicked:{root.home("settings");settingsWorkspace.go("sharing")}}
                RowLayout {Layout.fillWidth:true
                    TouchAction {tokens:theme;text:(Power.state.profileState||{}).effective==="power-saver"?"Saver ON":"Battery Saver";selected:(Power.state.profileState||{}).effective==="power-saver";enabled:!!Power.state.ready&&!Power.busy&&!DevelopmentSession;Layout.fillWidth:true;onClicked:Power.profile((Power.state.profileState||{}).effective==="power-saver"?"balanced":"power-saver")}
                    TouchAction {tokens:theme;text:"Battery & Power";Layout.fillWidth:true;onClicked:{root.home("settings");settingsWorkspace.go("power")}}
                }
                Caption {text:"Profile: "+((Power.state.profileState||{}).effective||"Unavailable")}
                Caption {text:"Brightness"}
                Slider {Layout.fillWidth:true;from:0;to:100;value:Core.telemetry.brightness||50;enabled:!!Core.telemetry.brightnessWritable&&!DevelopmentSession;onMoved:Power.setBrightness(Math.round(value))}
                Caption {visible:!Core.telemetry.brightnessWritable||DevelopmentSession;text:DevelopmentSession?"Host brightness is protected in the development session.":"Brightness requires writable backlight access."}
                Caption {text:"Volume · "+Media.volume+"%"+(Media.muted?" · muted":"")}
                Slider {Layout.fillWidth:true;from:0;to:100;value:Media.volume;enabled:!DevelopmentSession;onMoved:Media.setVolume(Math.round(value))}
                RowLayout {Layout.fillWidth:true
                    TouchAction {tokens:theme;text:Media.muted?"Unmute":"Mute";Layout.fillWidth:true;enabled:!DevelopmentSession;onClicked:Media.toggleMute()}
                    TouchAction {tokens:theme;text:AudioControl.state.recording?"● Microphone in use":"Sound";Layout.fillWidth:true;onClicked:{root.home("settings");settingsWorkspace.go("sound")}}
                }
                TouchAction {tokens:theme;objectName:"locationQuickToggle";text:(LocationControl.state.config||{}).enabled?"Location ON · "+(LocationControl.state.fixStatus||"No fix"):"Location OFF";selected:!!(LocationControl.state.config||{}).enabled;enabled:!!LocationControl.state.ready;Layout.fillWidth:true;onClicked:LocationControl.configure({enabled:!(LocationControl.state.config||{}).enabled})}
                TouchAction {tokens:theme;text:"Location settings";Layout.fillWidth:true;onClicked:{root.home("settings");settingsWorkspace.go("location")}}
                TouchAction {tokens:theme;objectName:"sensorsQuickStatus";text:SensorControl.state.ready?"Rotation locked · Motion unavailable":"Sensors unavailable";Layout.fillWidth:true;onClicked:{root.home("settings");settingsWorkspace.go("sensors")}}
                TouchAction {tokens:theme;text:CameraControl.state.active?"● Camera in use":"Camera diagnostics";Layout.fillWidth:true;onClicked:{root.home("settings");settingsWorkspace.go("camera")}}
                ComboBox {Layout.fillWidth:true;model:AudioControl.state.sinks||[];textRole:"description";currentIndex:model.findIndex(d=>d.name===AudioControl.state["default-sink"]);enabled:!!AudioControl.state.ready&&!DevelopmentSession;onActivated:index=>AudioControl.command("select","sink",{name:model[index].name})}
                RowLayout {Layout.fillWidth:true
                    TouchAction {tokens:theme;text:"Displays";Layout.fillWidth:true;onClicked:Core.control("display-settings")}
                    TouchAction {tokens:theme;text:"Rotate";Layout.fillWidth:true;enabled:!DevelopmentSession;onClicked:Core.control("rotate","right")}
                    TouchAction {tokens:theme;text:"Power";Layout.fillWidth:true;onClicked:powerMenu.open()}
                }
                Caption {text:Pocket.external?"EtherAir connected · desktop window policy":"EtherAir is not connected"}
                RowLayout {Layout.fillWidth:true;Repeater {model:["light","dark","auto"];delegate:TouchAction {required property string modelData;tokens:theme;text:modelData;selected:Core.preferences.themeMode===modelData;Layout.fillWidth:true;onClicked:Core.setting("themeMode",modelData)}}}
                TouchAction {tokens:theme;glyph:"settings";text:"Personalise and accessibility";Layout.fillWidth:true;onClicked:root.home("settings")}
                Caption {text:DevelopmentSession?"Isolated session · host controls are protected":"Uses the existing Linux device services."}
            }
            }
        }
    }


    Instantiator {
        model: NativeFrames?[]:Pocket.windowIds
        delegate:Window {
            id:airHeader;required property string modelData
            property var application:Pocket.windows.find(w=>w.id===modelData)||({})
            property real headerUnit:application.phone?root.unit:1
            title:"EtherSurface · "+(application.name||"");visible:Pocket.enabled&&!!application.id&&(!application.phone||application.floating)&&!application.hidden&&!application.fullscreen;transientParent:null
            flags:Qt.Window|Qt.FramelessWindowHint|Qt.WindowDoesNotAcceptFocus
            x:application.x||0;y:Math.max(0,(application.y||0)-60*headerUnit);width:application.width||1;height:56*headerUnit;color:"transparent"
            Component.onCompleted:Pocket.bindHeader(airHeader,modelData)
            Item {width:parent.width/airHeader.headerUnit;height:56;scale:airHeader.headerUnit;transformOrigin:Item.TopLeft
                SurfaceHeader {anchors.fill:parent;anchors.margins:2;tokens:theme;application:airHeader.application;desktopMode:true;onMenuRequested:root.showMenu(airHeader.modelData);onKeyboardRequested:root.keyboardVisible=!root.keyboardVisible}
            }
            Window {id:grip;title:"EtherSurface · Resize";visible:airHeader.visible;transientParent:null;flags:Qt.Window|Qt.FramelessWindowHint|Qt.WindowDoesNotAcceptFocus
                x:(airHeader.application.x||0)+(airHeader.application.width||0)-52*airHeader.headerUnit;y:(airHeader.application.y||0)+(airHeader.application.height||0);width:52*airHeader.headerUnit;height:44*airHeader.headerUnit;color:"transparent"
                Component.onCompleted:Pocket.bindHeader(grip,airHeader.modelData)
                GlassPanel {tokens:theme;anchors.fill:parent;radius:14;Image {anchors.centerIn:parent;width:20;height:20;source:"qrc:/icons/resize"+(theme.dark?"-light":"")+".svg"}}
                MouseArea {anchors.fill:parent;property point origin;property size initial;onPressed:e=>{origin=mapToGlobal(e.x,e.y);initial=Qt.size(airHeader.application.width,airHeader.application.height);Pocket.action("activate",airHeader.modelData)};onPositionChanged:e=>{if(pressed){let current=mapToGlobal(e.x,e.y);Pocket.resizeTo(airHeader.modelData,Math.round(initial.width+current.x-origin.x),Math.round(initial.height+current.y-origin.y))}}}
            }
        }
    }
    Connections {target:Media
        function onSaved(path){root.toast="Screenshot saved · open Images to view";toastDelay.restart()}
        function onVolumeShown(){root.toast="Volume "+Media.volume+"%";toastDelay.restart()}
        function onFailed(message){root.toast=message;toastDelay.restart()}
    }
    Timer {id:toastDelay;interval:3000;onTriggered:root.toast=""}
    Window {id:feedback;title:"EtherShell 2 · Feedback";visible:root.toast.length>0;transientParent:null;flags:Qt.Window|Qt.FramelessWindowHint|Qt.WindowStaysOnTopHint|Qt.WindowDoesNotAcceptFocus
        x:root.screen.virtualX+20*root.unit;y:root.screen.virtualY+chrome.height+8*root.unit;width:root.screen.width-40*root.unit;height:64*root.unit;color:"transparent"
        Component.onCompleted:Core.configureWindow(feedback,"dock",0)
        GlassPanel {tokens:theme;anchors.fill:parent;radius:18*root.unit;Text {anchors.fill:parent;anchors.margins:12*root.unit;text:root.toast;color:theme.ink;font.pixelSize:12*root.unit;wrapMode:Text.WordWrap}}
    }
}
