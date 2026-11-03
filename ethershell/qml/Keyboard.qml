import QtQuick
import QtQuick.Controls
import QtQuick.Window

Window {
    id: kb
    title: "EtherKeyboard"
    transientParent: null
    property real uiScale: 1
    property real dockHeight: 70
    property bool dark: false
    property color accent: "#087cff"
    property bool shift: false
    property bool ctrl: false
    property bool alt: false
    property bool superKey: false
    property bool altgr: false
    property bool caps: false
    property bool symbols: false
    property bool terminal: false
    property bool settingsCompact:false
    property bool polish: Core.preferences.layout==="PL"
    signal dismiss()
    flags: Qt.Window | Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint | Qt.WindowDoesNotAcceptFocus
    x: screen.virtualX;y: screen.virtualY+screen.height-height-dockHeight
    width: screen.width;height:(terminal?366:settingsCompact?272:320)*uiScale
    color: dark?"#1c2c45":"#dceafb"
    onVisibleChanged: Core.configureWindow(kb,"keyboard",visible?height+dockHeight:0)
    onHeightChanged: if(visible)Core.configureWindow(kb,"keyboard",height+dockHeight)
    onYChanged: if(visible)Core.configureWindow(kb,"keyboard",height+dockHeight)
    function send(k) {
        let special={"⌫":"BackSpace","↵":"Return","Tab":"Tab","Esc":"Escape","←":"Left","→":"Right","↑":"Up","↓":"Down","Home":"Home","End":"End","PgUp":"Prior","PgDn":"Next","Del":"Delete","Ins":"Insert","Space":"space"}
        if(k==="Shift"){shift=!shift;return}if(k==="Ctrl"){ctrl=!ctrl;return}if(k==="Alt"){alt=!alt;return}if(k==="Caps"){caps=!caps;return}
        if(k==="Super"){superKey=!superKey;return}if(k==="AltGr"){altgr=!altgr;return}
        if(k==="?123"){symbols=!symbols;return}if(k==="EN/PL"){Core.setting("layout",polish?"EN":"PL");return}
        let diacritics={a:"ą",c:"ć",e:"ę",l:"ł",n:"ń",o:"ó",s:"ś",z:"ż",x:"ź"}
        if(altgr&&kb.polish&&diacritics[k])Core.text(shift!==caps?diacritics[k].toUpperCase():diacritics[k])
        else if(special[k] || /^F\d+$/.test(k))Core.key(special[k]||k,ctrl,alt,shift,superKey,altgr)
        else if(ctrl||alt||superKey||altgr)Core.key(k.toLowerCase(),ctrl,alt,shift||caps,superKey,altgr)
        else Core.text(shift!==caps?k.toUpperCase():k)
        ctrl=false;alt=false;shift=false;superKey=false;altgr=false
    }
    Item {
        width: kb.width/kb.uiScale;height: kb.height/kb.uiScale;scale: kb.uiScale;transformOrigin: Item.TopLeft
        Column {
            anchors.fill: parent;anchors.margins: 7;spacing: 5
            Row {spacing: 5
                Repeater {model: [kb.polish?"PL":"EN",kb.terminal?"Standard":"Terminal","Caps","Ukryj"]
                    delegate: Rectangle {required property string modelData;width: (kb.width/kb.uiScale-29)/4;height: 30;radius: 9;color: dark?"#2e4364":"#f2f8ff"
                        Text {anchors.centerIn: parent;text: modelData;color: dark?"white":"#243b60";font.pixelSize: 11}
                        MouseArea {anchors.fill: parent;onClicked: {if(index===0)kb.send("EN/PL");if(index===1)kb.terminal=!kb.terminal;if(index===2)kb.caps=!kb.caps;if(index===3)kb.dismiss()}}
                    }
                }
            }
            Row {visible: kb.terminal;spacing: 3
                Repeater {model: 12;delegate: Rectangle {required property int index;width: (kb.width/kb.uiScale-47)/12;height: 38;radius: 7;color: dark?"#2e4364":"#f7fbff"
                    Text {anchors.centerIn: parent;text: "F"+(index+1);font.pixelSize: 10;color: dark?"white":"#163354"}
                    MouseArea {anchors.fill: parent;onClicked: kb.send("F"+(index+1))}
                }}
            }
            Repeater {
                model: [kb.symbols?["1","2","3","4","5","6","7","8","9","0"]:["q","w","e","r","t","y","u","i","o","p"],kb.symbols?["@","#","$","%","&","*","-","+","(",")"]:["a","s","d","f","g","h","j","k","l"],kb.symbols?["/","\\","|","~","`","[","]","{","}"]:["Shift","z","x","c","v","b","n","m","⌫"]]
                delegate: Row {
                    required property var modelData
                    spacing: 4
                    property int count: modelData.length
                    Repeater {model: modelData
                        delegate: Rectangle {
                            required property string modelData
                            width: (kb.width/kb.uiScale-14-(parent.count-1)*4)/parent.count;height: 45;radius: 9
                            color: keyMouse.pressed?kb.accent:dark?"#304666":"#f7fbff"
                            Text {anchors.centerIn: parent;text: kb.shift!==kb.caps?modelData.toUpperCase():modelData;color: dark?"white":"#193154";font.pixelSize: modelData==="Shift"?11:18}
                            MouseArea {id: keyMouse;anchors.fill: parent;property bool repeated: false;onClicked: if(!repeated)kb.send(modelData)
                                onPressed: {repeated=false;if(modelData==="⌫")repeatDelay.start()}
                                onReleased: {repeatDelay.stop();repeatKey.stop()}
                                onCanceled: {repeatDelay.stop();repeatKey.stop()}
                                Timer {id: repeatDelay;interval: 400;onTriggered: {keyMouse.repeated=true;kb.send(modelData);repeatKey.start()}}
                                Timer {id: repeatKey;interval: 80;repeat: true;onTriggered: kb.send(modelData)}
                                onPressAndHold: {let variants={a:"ą",c:"ć",e:"ę",l:"ł",n:"ń",o:"ó",s:"ś",z:"ż",x:"ź"};if(kb.polish&&variants[modelData]){Core.text(kb.shift?variants[modelData].toUpperCase():variants[modelData]);kb.shift=false}}
                            }
                        }
                    }
                }
            }
            Row {spacing: 4
                Repeater {model: ["?123","Ctrl","Alt","Space",".","↵"]
                    delegate: Rectangle {required property string modelData;width: modelData==="Space"?105:(kb.width/kb.uiScale-139)/5;height: 43;radius: 9;color: (modelData==="Ctrl"&&kb.ctrl)||(modelData==="Alt"&&kb.alt)?kb.accent:dark?"#304666":"#f7fbff"
                        Text {anchors.centerIn: parent;text: modelData==="Space"?(kb.polish?"Polski":"English"):modelData;color: dark?"white":"#193154";font.pixelSize: 12}
                        MouseArea {anchors.fill: parent;onClicked: kb.send(modelData)}
                    }
                }
            }
            Row {visible:!kb.settingsCompact||kb.terminal;spacing: 3
                Repeater {model: ["Esc","Tab","Home","End","←","↓","↑","→"]
                    delegate: Rectangle {required property string modelData;width: (kb.width/kb.uiScale-35)/8;height: 37;radius: 9;color: dark?"#304666":"#eef6ff"
                        Text {anchors.centerIn: parent;text: modelData;color: dark?"white":"#193154";font.pixelSize: 12}
                        MouseArea {anchors.fill: parent;onClicked: kb.send(modelData)}
                    }
                }
            }
            Row {spacing: 4
                Repeater {model: kb.terminal?["PgUp","PgDn","Ins","Del","Super","AltGr"]:["Super","AltGr"]
                    delegate: Rectangle {required property string modelData;width: (kb.width/kb.uiScale-14-(kb.terminal?5:1)*4)/(kb.terminal?6:2);height: 30;radius: 8;color: (modelData==="Super"&&kb.superKey)||(modelData==="AltGr"&&kb.altgr)?kb.accent:dark?"#304666":"#eef6ff"
                        Text {anchors.centerIn: parent;text: modelData;color: dark?"white":"#193154";font.pixelSize: 11}
                        MouseArea {anchors.fill: parent;onClicked: kb.send(modelData)}
                    }
                }
            }
        }
    }
}
