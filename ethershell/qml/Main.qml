import QtQuick
import "../ethernotifications" as NotificationUi
import QtQuick.Controls
import QtQuick.Layouts
import QtQuick.Window
import "../etherpower" as PowerUi

ApplicationWindow {
    id: root
    objectName: "pocket"
    visible: true
    title: "EtherShell • Pocket"
    PowerUi.PowerMenu {}
    flags: Qt.Window | Qt.FramelessWindowHint
    x: screen.virtualX; y: screen.virtualY
    width: screen.width; height: screen.height - dock.height
    property bool settingsActive:page==="settings"||page==="network"||page==="mobile"
    property real factor: (settingsActive?Math.max(1,Math.min(screen.width,screen.height)/400):Math.max(1,screen.width/420))*Number(Core.preferences.scale)
    property bool dark: Core.preferences.dark
    property color ink: dark ? "#f3f7ff" : "#122444"
    property color muted: dark ? "#9aafd0" : "#5d7291"
    property color card: dark ? "#202f49" : "#f9fcff"
    property color accent: Core.preferences.accent
    property string page: "home"
    property real unit:factor
    property real notificationSafeTop:0
    function home(destination){page=destination}
    NotificationUi.NotificationBanner {host:root}
    onPageChanged:if(page==="network"){settingsWorkspace.go("network");page="settings"}
    property string query: ""
    property string clock: Qt.formatDateTime(new Date(), "HH:mm")
    property string wifiSsid: ""
    property bool automaticKeyboardOpened: false
    property bool textEditing: false
    function requestAutomaticKeyboard(editable) {
        textEditing=editable
        const allowed=editable && Core.preferences.autoKeyboard && !Core.physicalKeyboardConnected && !Core.preferences.homeLocked
        if(allowed && !keyboardVisible){automaticKeyboardOpened=true;keyboardVisible=true}
        else if(!allowed && automaticKeyboardOpened){keyboardVisible=false;automaticKeyboardOpened=false}
    }
    onKeyboardVisibleChanged: if(!keyboardVisible)automaticKeyboardOpened=false
    property bool keyboardVisible: false
    Connections {
        target:Core
        function onTextInputFocus(editable){root.requestAutomaticKeyboard(editable)}
        function onPhysicalKeyboardChanged(){root.requestAutomaticKeyboard(root.textEditing)}
        function onPreferencesChanged(){root.requestAutomaticKeyboard(root.textEditing)}
    }
    property bool ctrl: false
    property bool alt: false
    property bool shift: false
    property bool windowMenu: false
    property bool terminalActive: Pocket.activeProfile.keyboard==="terminal"
    onTerminalActiveChanged: if(root.keyboardVisible)keyboard.terminal=root.terminalActive
    function appKey(symbol, ctrl, alt, shift) {Core.key(symbol,!!ctrl,!!alt,!!shift)}
    DesignTokens {id:mobileTheme}
    color: dark ? "#101c32" : "#e6f2ff"
    Timer {interval: 1000; running: true; repeat: true; onTriggered: root.clock=Qt.formatDateTime(new Date(),"HH:mm")}
    function home() {root.page="home";root.showNormal();root.raise();root.requestActivate();Core.refresh()}
    function launch(id) {Core.launch(id);root.showMinimized()}
    function favorite(id) {let f=Core.preferences.favorites.slice();let index=f.indexOf(id);if(index<0)f.push(id);else f.splice(index,1);Core.setting("favorites",f)}
    component Action: Button {
        id: button
        property bool active: false
        font.pixelSize: 13
        implicitHeight: 48
        background: Rectangle {radius: 16;color: button.down ? root.accent : button.active ? root.accent : root.card;border.color: root.dark?"#344563":"#dce7f5"}
        contentItem: Text {text: button.text;color: button.active||button.down?"white":root.ink;font: button.font;horizontalAlignment: Text.AlignHCenter;verticalAlignment: Text.AlignVCenter;elide: Text.ElideRight}
    }
    component Heading: Label {color: root.ink;font.pixelSize: 23;font.weight: Font.DemiBold;Layout.fillWidth: true}
    component Caption: Label {color: root.muted;font.pixelSize: 12;wrapMode: Text.WordWrap;Layout.fillWidth: true}
    component AppTile: Item {
        id: tile
        required property var app
        width: 86;height: 106
        Column {
            anchors.fill: parent;spacing: 8
            Rectangle {anchors.horizontalCenter: parent.horizontalCenter;width: 62;height: 62;radius: 20;color: root.card
                Image {anchors.centerIn: parent;width: 42;height: 42;source: "image://icons/"+tile.app.icon;sourceSize: Qt.size(96,96);fillMode: Image.PreserveAspectFit}
                Rectangle {visible: Core.preferences.favorites.indexOf(tile.app.id)>=0;width: 14;height: 14;radius: 7;color: root.accent;anchors.right: parent.right;anchors.top: parent.top}
            }
            Text {text: tile.app.name;width: parent.width;color: root.ink;font.pixelSize: 11;horizontalAlignment: Text.AlignHCenter;maximumLineCount: 2;wrapMode: Text.WordWrap;elide: Text.ElideRight}
        }
        MouseArea {anchors.fill: parent;onClicked: root.launch(tile.app.id);onPressAndHold: root.favorite(tile.app.id)}
    }
    Item {
        id: ui
        width: root.width/root.factor;height: root.height/root.factor;scale: root.factor;transformOrigin: Item.TopLeft
        Rectangle {x: -90;y: 80;width: 430;height: 430;radius: 215;color: root.dark?"#132c4c":"#d5eaff";rotation: 30}
        Rectangle {x: 180;y: 380;width: 400;height: 600;radius: 200;color: root.dark?"#15233b":"#ddecff";rotation: 35}
        ColumnLayout {
            anchors.fill: parent;anchors.margins:root.settingsActive?0:22;spacing:root.settingsActive?0:16
            RowLayout {Layout.fillWidth: true;visible:!root.settingsActive
                Label {text: root.clock;color: root.ink;font.pixelSize: 14;font.weight: Font.DemiBold;Layout.fillWidth: true}
                Label {text: Core.networks.some(n=>n.active)?"Wi-Fi":"USB";color: root.muted;font.pixelSize: 12}
                Label {text: (Core.telemetry.battery || "—")+"%"+(Core.telemetry.charging==="Charging"?" ⚡":"");color: root.ink;font.pixelSize: 12}
                Action {text: "⚙";implicitWidth: 42;implicitHeight: 36;onClicked: root.page=root.page==="settings"?"home":"settings"}
            }
            StackLayout {
                id: pages
                Layout.fillWidth: true;Layout.fillHeight: true
                currentIndex: ["home","apps","settings","tasks","notices","store","touchpad","gallery","network","mobile"].indexOf(root.page)
                ColumnLayout {
                    spacing: 15
                    Item {Layout.fillWidth: true;Layout.preferredHeight: 125
                        Column {anchors.centerIn: parent;spacing: 5
                            Image {anchors.horizontalCenter: parent.horizontalCenter;source: "qrc:/brand.png";width: 125;height: 66;fillMode: Image.PreserveAspectFit}
                            Label {text: "EtherShell";color: root.ink;font.pixelSize: 28;font.weight: Font.Bold}
                            Label {text: "Your Debian. Your Way.";color: root.muted;font.pixelSize: 12}
                        }
                    }
                    TextField {Layout.fillWidth: true;implicitHeight: 48;placeholderText: "Szukaj aplikacji…";font.pixelSize: 14;onTextEdited: {root.query=text;root.page="apps";Qt.callLater(function(){search.forceActiveFocus();search.cursorPosition=search.text.length})} background: Rectangle {radius: 24;color: root.card;border.color: "#dce7f5"}}
                    Caption {text: "ULUBIONE  ·  przytrzymaj ikonę, aby przypiąć"}
                    Flow {Layout.fillWidth: true;spacing: 9
                        Repeater {model: Core.apps.filter(a=>Core.preferences.favorites.indexOf(a.id)>=0).slice(0,8);delegate: AppTile {required property var modelData;app: modelData}}
                    }
                    RowLayout {Layout.fillWidth: true
                        Action {text: "⌘  Terminal";Layout.fillWidth: true;onClicked: {Core.control("terminal");root.showMinimized()}}
                        Action {text: "▣  Pliki";Layout.fillWidth: true;onClicked: {Core.control("files");root.showMinimized()}}
                    }
                    Action {text: "Wszystkie aplikacje  →";active: true;Layout.fillWidth: true;onClicked: {root.query="";root.page="apps"}}
                    Action {text: "▧  Obrazy i zrzuty";Layout.fillWidth: true;onClicked: {Media.scan();root.page="gallery"}}
                    RowLayout {Layout.fillWidth: true
                        Action {text: "Ustawienia";Layout.fillWidth: true;onClicked: root.page="settings"}
                        Action {text: "App Centre";Layout.fillWidth: true;onClicked: root.page="store"}
                    }
                    Item {Layout.fillHeight: true}
                    Caption {text: "Debian 13 · natywna sesja X11\n"+Core.telemetry.hostname+" · "+Core.telemetry.kernel}
                }
                ColumnLayout {
                    Heading {text: "Aplikacje"}
                    TextField {id: search;Layout.fillWidth: true;implicitHeight: 46;placeholderText: "Szukaj…";text: root.query;onTextEdited: root.query=text;font.pixelSize: 14}
                    Flickable {Layout.fillWidth: true;Layout.fillHeight: true;clip: true;contentHeight: appFlow.height;boundsBehavior: Flickable.StopAtBounds
                        Flow {id: appFlow;width: parent.width;spacing: 9
                            Repeater {model: Core.apps.filter(a=>a.name.toLowerCase().indexOf(root.query.toLowerCase())>=0);delegate: AppTile {required property var modelData;app: modelData}}
                        }
                    }
                }
                SettingsWorkspace {id:settingsWorkspace;onClosed:root.page="home";onOpenMobile:section=>{root.page="mobile";mobileSettings.navigate(section)};onOpenStore:root.page="store";onKeyboardRequested:root.requestAutomaticKeyboard(true)}
                ColumnLayout {
                    Heading {text: "Otwarte aplikacje"}
                    Action {text: "Odśwież";onClicked: Core.refresh()}
                    ListView {Layout.fillWidth: true;Layout.fillHeight: true;spacing: 10;clip: true;model: Pocket.windows
                        delegate: ColumnLayout {required property var modelData;width: ListView.view.width
                            Action {text: modelData.profile+" · "+modelData.title;Layout.fillWidth: true;onClicked: {Pocket.action("activate",modelData.id);root.showMinimized()}}
                            RowLayout {Action {text: "Minimalizuj";onClicked: Pocket.action("minimize",modelData.id)} Action {text: "Zamknij";onClicked: Pocket.action("close",modelData.id)}}
                        }
                    }
                }
                NotificationUi.NotificationCenter {}
                Flickable {
                    contentHeight: catalogColumn.height;clip: true;boundsBehavior: Flickable.StopAtBounds
                    ColumnLayout {id: catalogColumn;width: parent.width;spacing: 12
                        Heading {text: "Etherneco App Centre"}
                        Caption {text: "autoupddate.etherneco.com · Debian ARM64"}
                        Caption {text: Distributor.status;textFormat: Text.PlainText}
                        Action {text: Distributor.busy?"Pobieranie…":"Odśwież katalog";enabled: !Distributor.busy;Layout.fillWidth: true;onClicked: Distributor.refresh()}
                        Repeater {model: Distributor.catalog
                            delegate: Rectangle {id: familyCard;required property var modelData;property bool expanded: false;Layout.fillWidth: true;implicitHeight: familyContent.implicitHeight+26;radius: 16;color: root.card
                                ColumnLayout {id: familyContent;anchors.left: parent.left;anchors.right: parent.right;anchors.top: parent.top;anchors.margins: 13;spacing: 7
                                    Label {text: familyCard.modelData.name;color: root.ink;font.pixelSize: 17;font.bold: true;textFormat: Text.PlainText}
                                    Caption {text: familyCard.modelData.variants.length?String(familyCard.modelData.variants.length)+" wariantów · brak potwierdzonego pakietu Debian ARM64":"Brak projektu w odczytanym katalogu publicznym"}
                                    Action {text: familyCard.expanded?"Zwiń wydania ↑":"Pokaż wersje i platformy ↓";visible: familyCard.modelData.variants.length>0;Layout.fillWidth: true;onClicked: familyCard.expanded=!familyCard.expanded}
                                    Repeater {model: familyCard.expanded?familyCard.modelData.variants:[]
                                        delegate: ColumnLayout {required property var modelData;Layout.fillWidth: true;spacing: 4
                                            Label {text: modelData.name;color: root.ink;font.pixelSize: 13;font.bold: true;Layout.fillWidth: true;wrapMode: Text.WordWrap;textFormat: Text.PlainText}
                                            Caption {text: "Stable "+(modelData.version||"—")+" · "+modelData.platform+" · "+(modelData.format||"—");textFormat: Text.PlainText}
                                            Caption {text: modelData.reason;textFormat: Text.PlainText}
                                        }
                                    }
                                }
                            }
                        }
                        Caption {text: "Instalacja wymaga zgodnego pakietu i zweryfikowanego podpisu. Wydania dla Windows, Androida i macOS nie są instalowane na tym Debianie."}
                        Action {text: "Otwórz istniejący dystrybutor ↗";Layout.fillWidth: true;onClicked: {Core.control("distributor");root.showMinimized()}}
                    }
                }
                ColumnLayout {
                    Heading {text: "EtherAir · touchpad"}
                    Caption {text: "Przesuwaj palcem, aby sterować kursorem. Przyciski poniżej obsługują kliknięcie, przeciąganie i przewijanie."}
                    Rectangle {Layout.fillWidth: true;Layout.fillHeight: true;radius: 24;color: root.card;border.color: root.accent
                        Label {anchors.centerIn: parent;text: "Touchpad";color: root.muted;font.pixelSize: 24}
                        MouseArea {anchors.fill: parent;property real oldX;property real oldY;property bool moved: false
                            onPressed: mouse=>{oldX=mouse.x;oldY=mouse.y;moved=false}
                            onPositionChanged: mouse=>{if(pressed){let dx=mouse.x-oldX,dy=mouse.y-oldY;if(Math.abs(dx)+Math.abs(dy)>1)moved=true;Core.pointer(Math.round(dx*2),Math.round(dy*2));oldX=mouse.x;oldY=mouse.y}}
                            onReleased: {if(!moved){Core.mouse(1,true);Core.mouse(1,false)}}
                            onPressAndHold: {Core.mouse(3,true);Core.mouse(3,false);moved=true}
                        }
                    }
                    RowLayout {Layout.fillWidth: true
                        Action {text: "Lewy";Layout.fillWidth: true;onPressed: Core.mouse(1,true);onReleased: Core.mouse(1,false);onCanceled: Core.mouse(1,false)}
                        Action {text: "Prawy";Layout.fillWidth: true;onClicked: {Core.mouse(3,true);Core.mouse(3,false)}}
                        Action {text: "↑";onClicked: {Core.mouse(4,true);Core.mouse(4,false)}}
                        Action {text: "↓";onClicked: {Core.mouse(5,true);Core.mouse(5,false)}}
                    }
                }
                Gallery {ink: root.ink;muted: root.muted;card: root.card;accent: root.accent}
                Item {} // Legacy route is normalized to the shared Settings workspace.
                Item {MobileNetworkSettings {id:mobileSettings;anchors.fill:parent;anchors.margins:16;onBackRequested:root.page="network";onKeyboardRequested:root.requestAutomaticKeyboard(true)}}

            }
            Rectangle {visible: Core.message.length>0;Layout.fillWidth: true;implicitHeight: errorText.implicitHeight+20;radius: 14;color: root.dark?"#493a30":"#fff1dc"
                Text {id: errorText;anchors.fill: parent;anchors.margins: 10;text: Core.message;color: root.dark?"#ffdfb3":"#7f490d";font.pixelSize: 12;wrapMode: Text.WordWrap}
                MouseArea {anchors.fill: parent;onClicked: parent.visible=false}
            }
        }
        MouseArea {anchors.top: parent.top;width: parent.width-75;height: 40;property real sy;onPressed: mouse=>sy=mouse.y;onReleased: mouse=>{if(mouse.y-sy>45)root.page="settings"}}
    }
    Connections {
        target: Media
        function onCapturing() {feedback.hide()}
        function onSaved(path) { feedback.text="Zapisano zrzut · otwórz galerię";feedback.isScreenshot=true;feedback.show();feedbackDelay.restart() }
        function onVolumeShown() {feedback.text="Głośność: "+Media.volume+"%"+(Media.muted?" · wyciszono":"");feedback.isScreenshot=false;feedback.show();feedbackDelay.restart()}
        function onVolumeChanged() {if(feedback.visible&&!feedback.isScreenshot)feedback.text="Głośność: "+Media.volume+"%"+(Media.muted?" · wyciszono":"")}
        function onFailed(message) {feedback.text=message;feedback.isScreenshot=false;feedback.show();feedbackDelay.restart()}
    }
    Timer {id: feedbackDelay;interval: 2500;onTriggered: feedback.hide()}
    Window {
        id: feedback
        property string text: ""
        property bool isScreenshot: false
        transientParent: null;title: "EtherShell Feedback";visible: false
        flags: Qt.Tool | Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint | Qt.WindowDoesNotAcceptFocus | Qt.X11BypassWindowManagerHint
        x: root.screen.virtualX+(root.screen.width-width)/2;y: root.screen.virtualY+45*root.factor
        width: 355*root.factor;height: 66*root.factor;color: root.card
        Text {anchors.fill: parent;anchors.margins: 10*root.factor;text: feedback.text;color: root.ink;font.pixelSize: 14*root.factor;wrapMode: Text.WordWrap;horizontalAlignment: Text.AlignHCenter;verticalAlignment: Text.AlignVCenter}
        MouseArea {anchors.fill: parent;onClicked: {feedback.hide();if(feedback.isScreenshot){Media.scan();root.home();root.page="gallery"}}}
    }
    Instantiator {
        model: AvailableScreens
        delegate: Window {
            id: flash
            required property var modelData
            screen: modelData;transientParent: null;visible: false;title: "EtherShell Screenshot Flash"
            flags: Qt.Tool | Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint | Qt.WindowDoesNotAcceptFocus | Qt.WindowTransparentForInput | Qt.X11BypassWindowManagerHint
            x: screen.virtualX;y: screen.virtualY;width: screen.width;height: screen.height;color: "white"
            Connections {target: Media;function onCapturing() {flashAnimation.stop();flash.hide()} function onSaved(path) {flash.opacity=0.9;flash.show();flashAnimation.restart()}}
            SequentialAnimation {id: flashAnimation;PauseAnimation {duration: 70} NumberAnimation {target: flash;property: "opacity";to: 0;duration: 180} ScriptAction {script: flash.hide()}}
        }
    }
    Window {
        id: dock
        transientParent: null
        visible: true;title: "EtherShell Navigation";flags: Qt.Window | Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint | Qt.WindowDoesNotAcceptFocus
        x: root.screen.virtualX;y: root.screen.virtualY+root.screen.height-height;width: root.screen.width;height: (root.windowMenu?226:130)*root.factor;color: root.dark?"#14243d":"#f4f9ff"
        Component.onCompleted: Core.configureWindow(dock,"dock",height)
        onHeightChanged: Core.configureWindow(dock,"dock",height)
        onYChanged: Core.configureWindow(dock,"dock",height)
        Column {anchors.centerIn: parent;spacing: 5*root.factor
        Rectangle {width: dock.width;height: 16*root.factor;color: root.card
            Text {anchors.centerIn: parent;text: "‹  swipe / hold  ›";font.pixelSize: 10*root.factor;color: root.muted}
            MouseArea {anchors.fill: parent;property real startX;property real startY;property bool allowed: false;property bool held: false
                onPressed: mouse=>{held=false;startX=mouse.x;startY=mouse.y;allowed=mouse.x/width>=Pocket.gestureStart&&mouse.x/width<=Pocket.gestureEnd}
                onReleased: mouse=>{if(!allowed||held)return;let dx=mouse.x-startX,dy=mouse.y-startY;if(Math.abs(dx)>45*root.factor&&Math.abs(dx)>Math.abs(dy)){Pocket.action(dx<0?"next":"previous");root.showMinimized()}else if(dy< -25*root.factor){root.home();root.page="settings"}else if(Math.abs(dx)<8*root.factor)root.windowMenu=!root.windowMenu}
                onPressAndHold: if(allowed){held=true;root.windowMenu=true}
            }
        }
        Row {anchors.horizontalCenter: parent.horizontalCenter;spacing: 4*root.factor
            Repeater {model: ["‹", "Back", "−", "×", "Menu"]
                delegate: Rectangle {required property int index;required property string modelData;width: 76*root.factor;height: 48*root.factor;radius: 12*root.factor;color: root.card
                    Text {anchors.centerIn: parent;text: modelData;color: root.ink;font.pixelSize: 17*root.factor}
                    MouseArea {anchors.fill: parent;onClicked: {if(index===0)Pocket.action("previous");else if(index===1)root.appKey(root.terminalActive?"Escape":"Left",false,!root.terminalActive,false);else if(index===2)Pocket.action("minimize");else if(index===3)Pocket.action("close");else root.windowMenu=!root.windowMenu}onPressAndHold: root.windowMenu=true}
                }
            }
        }
        Row {anchors.horizontalCenter: parent.horizontalCenter;spacing: 5*root.factor
            Repeater {model: [{t:"⌂",p:"home"},{t:"▦",p:"apps"},{t:"▤",p:"tasks"},{t:"⌨",p:"keyboard"},{t:"◎",p:"touchpad"},{t:"☷",p:"notices"}]
                delegate: Rectangle {required property var modelData;width: 57*root.factor;height: 48*root.factor;radius: 15*root.factor;color: root.page===modelData.p?root.accent:root.card
                    Text {anchors.centerIn: parent;text: modelData.t;color: root.page===modelData.p?"white":root.ink;font.pixelSize: 24*root.factor}
                    MouseArea {anchors.fill: parent;onClicked: {if(modelData.p==="keyboard")root.keyboardVisible=!root.keyboardVisible;else{root.home();root.page=modelData.p}}}
                }
            }
        }
        Row {visible: root.windowMenu;anchors.horizontalCenter: parent.horizontalCenter;spacing: 4*root.factor
            Repeater {model: ["Full", "Fit", "Top", "Bottom"]
                delegate: Rectangle {required property int index;required property string modelData;width: 96*root.factor;height: 44*root.factor;radius: 10*root.factor;color: root.card
                    Text {anchors.centerIn: parent;text: modelData;color: root.ink;font.pixelSize: 13*root.factor}
                    MouseArea {anchors.fill: parent;onClicked: {Pocket.action(["fullscreen","maximize","split-top","split-bottom"][index]);root.windowMenu=false}}
                }
            }
        }
        Row {visible: root.windowMenu;anchors.horizontalCenter: parent.horizontalCenter;spacing: 4*root.factor
            Repeater {model: [root.terminalActive?"Copy":"Tab ‹",root.terminalActive?"Paste":"Tab ›","Scroll ↑","Scroll ↓"]
                delegate: Rectangle {required property int index;required property string modelData;width: 96*root.factor;height: 44*root.factor;radius: 10*root.factor;color: root.card
                    Text {anchors.centerIn: parent;text: modelData;color: root.ink;font.pixelSize: 13*root.factor}
                    MouseArea {anchors.fill: parent;onClicked: {if(index<2){if(root.terminalActive)root.appKey(index===0?"c":"v",true,false,true);else root.appKey(index===0?"Prior":"Next",true,false,false)}else if(root.terminalActive)root.appKey(index===2?"Prior":"Next",false,false,true);else {Core.mouse(index===2?4:5,true);Core.mouse(index===2?4:5,false)}}}
                }
            }
        }
        }
    }
    Keyboard {id: keyboard;visible: root.keyboardVisible;uiScale: root.factor*Number(Core.preferences.keyboardScale);dockHeight: dock.height;dark: root.dark;accent: root.accent;onDismiss: root.keyboardVisible=false;screen: root.screen;onVisibleChanged: {Core.configureWindow(keyboard,"keyboard",visible?height+dockHeight:0);if(visible)terminal=root.terminalActive}}
    Dialog {
        id: wifiDialog;title: root.wifiSsid;modal: true;anchors.centerIn: parent;width: Math.min(root.width-50,340*root.factor);scale: 1
        standardButtons: Dialog.Ok | Dialog.Cancel
        contentItem: TextField {id: password;echoMode: TextInput.Password;placeholderText: "Hasło Wi-Fi";font.pixelSize: 16*root.factor;implicitHeight: 52*root.factor}
        onAccepted: {Core.connectWifi(root.wifiSsid,password.text);password.clear()}
        onRejected: password.clear()
    }
    Instantiator {
        model: AvailableScreens
        delegate: Window {
            required property var modelData
            screen: modelData
            visible: screen.name!==root.screen.name
            title: "EtherShell • EtherAir Desktop"
            flags: Qt.Window | Qt.FramelessWindowHint
            transientParent: null
            x: screen.virtualX;y: screen.virtualY;width: screen.width;height: screen.height
            color: "#101d32"
            Component.onCompleted: if(visible)Core.configureWindow(this,"desktop")
            Column {anchors.centerIn: parent;spacing: 14
                Text {text: "EtherAir Desktop";color: "white";font.pixelSize: 48}
                Text {text: "Work. Create. Explore. Anywhere.";color: "#a4bbdc";font.pixelSize: 21}
            }
            Rectangle {anchors.bottom: parent.bottom;width: parent.width;height: 72;color: "#e9f3ff"
                Row {anchors.centerIn: parent;spacing: 12
                    Action {text: "Aplikacje";onClicked: {root.home();root.page="apps"}}
                    Action {text: "Terminal";onClicked: Core.control("terminal")}
                    Action {text: "Pliki";onClicked: Core.control("files")}
                    Repeater {model: 4;delegate: Action {required property int index;text: String(index+1);onClicked: Core.control("workspace",String(index))}}
                    Action {text: root.clock;onClicked: {root.home();root.page="settings"}}
                }
            }
        }
    }
}
