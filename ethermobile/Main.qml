import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import "diagnostics.js" as Diagnostics

ApplicationWindow {
    id: win
    visible: true
    width: 1100; height: 820
    minimumWidth: 360; minimumHeight: 580
    title: "EtherMobile"
    property bool dark: false
    property string page: "Overview"
    readonly property bool compact: width < 760
    readonly property color ink: dark ? "#e7efff" : "#122948"
    readonly property color muted: dark ? "#a2b7d0" : "#5e728b"
    readonly property color surface: dark ? "#182941" : "#ffffff"
    readonly property color line: dark ? "#30445e" : "#dbe6f1"
    readonly property color accent: dark ? "#8ebaff" : "#1558bb"
    readonly property color ice: dark ? "#101d30" : "#edf5fd"
    property string pendingAction: ""
    property string pendingPath: ""
    property bool pendingRadio: false
    property var selectedProfile: ({})
    color: ice
    font.family: "DejaVu Sans"
    font.pixelSize: 15
    palette.window: ice; palette.base: surface; palette.text: ink
    palette.windowText: ink; palette.buttonText: ink; palette.button: surface
    palette.highlight: accent

    component Body: Label { color: win.ink; wrapMode: Text.WordWrap; textFormat: Text.PlainText; Layout.fillWidth: true }
    component Caption: Body { color: win.muted; font.pixelSize: 13 }
    component TouchButton: Button {
        id: btn
        implicitHeight: 50
        padding: 15
        contentItem: Text { text: btn.text; color: btn.enabled ? win.accent : win.muted; font: btn.font; horizontalAlignment: Text.AlignHCenter; verticalAlignment: Text.AlignVCenter; elide: Text.ElideRight }
        background: Rectangle { color: btn.down ? win.ice : win.surface; radius: 13; border.width: 1; border.color: win.line; opacity: btn.enabled ? 1 : 0.6 }
    }
    component Card: Rectangle {
        default property alias content: cardLayout.data
        Layout.fillWidth: true
        implicitHeight: cardLayout.implicitHeight + 40
        color: win.surface; radius: 20; border.color: win.line
        ColumnLayout { id: cardLayout; anchors.fill: parent; anchors.margins: 20; spacing: 13 }
    }
    component Fact: ColumnLayout {
        property string heading
        property string value
        Layout.fillWidth: true
        spacing: 6
        Caption { text: heading }
        Body { text: value || "Unavailable"; font.pixelSize: 20; font.weight: Font.DemiBold }
    }
    component Field: TextField {
        Layout.fillWidth: true; implicitHeight: 50; color: win.ink
        selectByMouse: true; leftPadding: 14; rightPadding: 14
        background: Rectangle { radius: 12; color: win.ice; border.color: parent.activeFocus ? win.accent : win.line }
    }

    function confirm(action, path, description) {
        pendingAction = action; pendingPath = path || ""
        confirmText.text = description; confirmation.open()
    }

    header: Rectangle {
        height: compact ? 78 : 94; color: surface
        border.color: line
        RowLayout {
            anchors.fill: parent; anchors.leftMargin: 24; anchors.rightMargin: 24; spacing: 14
            Rectangle {
                width: 44; height: 44; radius: 14; color: win.accent
                Image { anchors.centerIn: parent; width: 28; height: 28; source: "qrc:/ethermobile.svg" }
            }
            ColumnLayout {
                spacing: 3; Layout.fillWidth: true
                Body { text: "EtherMobile"; font.pixelSize: 24; font.weight: Font.Bold }
                Caption { text: "Your mobile network, clearly."; visible: !win.compact }
            }
            BusyIndicator { running: Mobile.busy; visible: running; implicitWidth: 32; implicitHeight: 32 }
            TouchButton { text: win.dark ? "Light" : "Dark"; onClicked: win.dark = !win.dark }
        }
    }

    RowLayout {
        anchors.fill: parent; spacing: 0
        Rectangle {
            visible: !win.compact; Layout.preferredWidth: 210; Layout.fillHeight: true; color: win.surface
            ColumnLayout {
                anchors.fill: parent; anchors.margins: 16; spacing: 6
                Caption { text: "CONNECTIVITY"; leftPadding: 12; topPadding: 10; bottomPadding: 10; font.letterSpacing: 1.5 }
                Repeater {
                    model: ["Overview", "Mobile Data", "SIM", "Networks", "SMS", "Calls", "Hotspot", "Diagnostics", "Settings"]
                    delegate: Button {
                        required property string modelData
                        Layout.fillWidth: true; implicitHeight: 48
                        text: modelData
                        contentItem: Text { text: parent.text; color: win.page === parent.text ? win.accent : win.muted; font.pixelSize: 15; font.weight: win.page === parent.text ? Font.DemiBold : Font.Normal; verticalAlignment: Text.AlignVCenter }
                        background: Rectangle { radius: 12; color: win.page === parent.text ? win.ice : "transparent" }
                        onClicked: win.page = modelData
                    }
                }
                Item { Layout.fillHeight: true }
                Caption { text: "EtherPocket\nNative Linux · X11"; leftPadding: 10; lineHeight: 1.5 }
            }
        }
        ColumnLayout {
            Layout.fillWidth: true; Layout.fillHeight: true; spacing: 0
            ComboBox {
                visible: win.compact; Layout.fillWidth: true; Layout.margins: 16; implicitHeight: 50
                model: ["Overview", "Mobile Data", "SIM", "Networks", "SMS", "Calls", "Hotspot", "Diagnostics", "Settings"]
                currentIndex: model.indexOf(win.page)
                onActivated: win.page = currentText
            }
            ScrollView {
                id: scroll
                Layout.fillWidth: true; Layout.fillHeight: true; clip: true
                contentWidth: availableWidth
                ColumnLayout {
                    width: scroll.availableWidth
                    spacing: 18
                    Item { implicitHeight: win.compact ? 0 : 10 }
                    ColumnLayout {
                        Layout.fillWidth: true; Layout.leftMargin: win.compact ? 16 : 30; Layout.rightMargin: win.compact ? 16 : 30
                        spacing: 18
                        Body { text: win.page; font.pixelSize: 30; font.weight: Font.Bold }
                        Caption { text: win.page === "Overview" ? "Live status from your system. Unavailable values stay unavailable." : win.page === "Diagnostics" ? "Find the stage that needs attention, with real system evidence." : "Manage the capabilities available on your current modem." }
                        ComboBox {
                            visible: Mobile.modems.length > 1; Layout.fillWidth: true; implicitHeight: 50
                            model: Mobile.modems; textRole: "label"; valueRole: "path"
                            onActivated: Mobile.selectModem(currentValue)
                        }
                        Card {
                            visible: win.page === "Overview"
                            RowLayout {
                                Layout.fillWidth: true
                                Rectangle { width: 12; height: 12; radius: 6; color: Mobile.status.hasIp ? "#29966f" : "#d79330" }
                                Body { text: Mobile.status.state || "Discovering…"; font.pixelSize: 24; font.weight: Font.DemiBold }
                            }
                            Body { text: Mobile.status.explanation || "Reading modem status…"; color: win.muted }
                            GridLayout {
                                columns: win.compact ? 1 : 2; rowSpacing: 22; columnSpacing: 24; Layout.fillWidth: true
                                Fact { heading: "OPERATOR"; value: Mobile.status.operator || "Unavailable" }
                                Fact { heading: "NETWORK"; value: Mobile.status.technology || "Unavailable" }
                                Fact { heading: "SIGNAL"; value: Mobile.status.signal || "Unavailable" }
                                Fact { heading: "SIM"; value: Mobile.status.sim || "Unavailable" }
                            }
                            Rectangle { Layout.fillWidth: true; implicitHeight: 1; color: win.line }
                            Body { text: "Internet access: " + (Mobile.status.internet || "Not verified"); font.weight: Font.DemiBold }
                            RowLayout {
                                Layout.fillWidth: true
                                TouchButton { text: "Mobile data"; Layout.fillWidth: true; onClicked: win.page = "Mobile Data" }
                                TouchButton { text: "Diagnose"; Layout.fillWidth: true; enabled: !Mobile.busy; onClicked: { win.page = "Diagnostics"; Mobile.diagnose() } }
                            }
                        }
                        Card {
                            visible: win.page === "Overview"
                            Body { text: "A clear path to mobile internet"; font.pixelSize: 18; font.weight: Font.DemiBold }
                            Caption { text: "Modem → SIM → registration → data session → IP → DNS → internet. Diagnostics keeps these stages separate." }
                            Caption { text: "Data usage: unavailable until a cellular interface can be measured. Interface counters are not carrier billing totals." }
                        }
                        Card {
                            visible: win.page === "Mobile Data"
                            Body { text: "Access point profiles"; font.pixelSize: 20; font.weight: Font.DemiBold }
                            Caption { text: "Use the APN supplied by your carrier. New profiles start with roaming and automatic connection off. A default internet route requires your explicit choice." }
                            TouchButton { text: "Add APN"; enabled: !Mobile.busy; onClicked: { win.selectedProfile = ({}); profileName.text = ""; profileApn.text = ""; profileRoam.checked = false; profileRoute.checked = false; ipType.currentIndex = 0; apnDialog.open() } }
                            Caption { visible: Mobile.profiles.length === 0; text: "No accessible cellular profiles. Add an APN when you have your carrier details." }
                            Repeater {
                                model: Mobile.profiles
                                delegate: ColumnLayout {
                                    required property var modelData
                                    Layout.fillWidth: true; spacing: 10
                                    Body { text: modelData.name; font.weight: Font.DemiBold }
                                    Caption { text: "APN: " + modelData.apn + " · Roaming " + (modelData.roaming ? "allowed" : "blocked") }
                                    Flow {
                                        Layout.fillWidth: true; spacing: 8
                                        TouchButton { text: "Connect"; enabled: Mobile.status.canConnect && !Mobile.busy; onClicked: win.confirm("connect", modelData.path, "Connect using this APN? Mobile data charges may apply." + (modelData.roaming ? " This profile allows roaming charges." : " Roaming is blocked.")) }
                                        TouchButton { text: "Edit"; enabled: !Mobile.busy && modelData.name.indexOf("EtherMobile · ") === 0; onClicked: { win.selectedProfile = modelData; profileName.text = modelData.name.replace("EtherMobile · ", ""); profileApn.text = modelData.apn; profileRoam.checked = modelData.roaming; profileRoute.checked = modelData.internetRoute; ipType.currentIndex = modelData.ipType === "IPv4" ? 0 : 1; apnDialog.open() } }
                                        TouchButton { text: "Delete"; enabled: !Mobile.busy && modelData.name.indexOf("EtherMobile · ") === 0; onClicked: win.confirm("delete", modelData.path, "Delete this APN profile? If it is active, data may disconnect.") }
                                    }
                                    Rectangle { Layout.fillWidth: true; implicitHeight: 1; color: win.line }
                                }
                            }
                            TouchButton { text: "Disconnect mobile data"; enabled: Mobile.status.canDisconnect && !Mobile.busy; onClicked: win.confirm("disconnect", "", "Disconnect this modem's cellular data session? Wi-Fi settings will remain unchanged.") }
                            Caption { text: "Carrier defaults, authenticated APNs and automatic reconnection require further integration. Existing profiles can also be managed in NetworkManager's connection editor." }
                        }
                        Card {
                            visible: win.page === "SIM"
                            Fact { heading: "SIM STATUS"; value: Mobile.status.sim || "Unavailable" }
                            Caption { text: "Identifiers are masked and are never written to ordinary logs. An unavailable SIM may be absent, inaccessible or blocked by modem initialization." }
                            Body { text: Mobile.status.pinRequired ? "SIM PIN required" : "No PIN request reported"; font.weight: Font.DemiBold }
                            TouchButton { text: "Enter SIM PIN"; enabled: Mobile.status.pinRequired && !Mobile.busy; onClicked: { pinField.text = ""; pinDialog.open() } }
                            Caption { text: "Incorrect PINs can lock your SIM. Never guess a PIN or PUK. Retry counts are shown only when reliable. PIN lock changes, PUK recovery, slot switching and eSIM are not enabled in this release." }
                        }
                        Card {
                            visible: win.page === "Networks"
                            Fact { heading: "CURRENT TECHNOLOGY"; value: Mobile.status.technology || "Unavailable" }
                            Fact { heading: "REGISTRATION / DATA STATE"; value: Mobile.status.state || "Unavailable" }
                            Caption { text: "LTE does not imply LTE Advanced. A firmware capability advertisement does not establish working 5G. Network scans and radio mode changes are not enabled until this device's control and data paths are verified." }
                            TouchButton { text: Mobile.status.radio ? "Disable cellular radio" : "Enable cellular radio"; enabled: Mobile.status.available && !Mobile.busy; onClicked: { win.pendingRadio = !Mobile.status.radio; win.confirm("radio", "", win.pendingRadio ? "Enable this modem's cellular radio? This may start network registration." : "Disable this modem's cellular radio? Cellular sessions may disconnect.") } }
                        }
                        Card {
                            visible: win.page === "SMS" || win.page === "Calls" || win.page === "Hotspot"
                            Body { text: win.page + " is not enabled"; font.pixelSize: 22; font.weight: Font.DemiBold }
                            Caption { text: win.page === "Calls" ? "Voice and VoLTE need verified call control, audio routing, IMS and carrier provisioning. A voice service alone does not establish working calls." : win.page === "SMS" ? "SMS send and receive have not been verified on this stack. No messages are sent automatically." : "Internet sharing needs a working cellular data path, verified Wi-Fi AP support and explicit network configuration. Sharing is off." }
                            TouchButton { text: "View Diagnostics"; onClicked: win.page = "Diagnostics" }
                        }
                        Card {
                            visible: win.page === "Diagnostics"
                            Body { text: "EtherModem Doctor"; font.pixelSize: 22; font.weight: Font.DemiBold }
                            Caption { text: "Read-only discovery. It does not reset shared Qualcomm services, power the radio, scan networks or connect data. Some evidence may require a local administrator." }
                            TouchButton { text: "Run diagnostics"; enabled: !Mobile.busy; onClicked: Mobile.diagnose() }
                            Caption { visible: Mobile.stages.length === 0; text: "Run the Doctor to collect evidence from this system." }
                            Repeater {
                                model: Mobile.stages
                                delegate: ColumnLayout {
                                    id: stageRow
                                    required property var modelData
                                    property bool expanded: false
                                    Layout.fillWidth: true; spacing: 8
                                    RowLayout {
                                        Layout.fillWidth: true
                                        Rectangle { width: 9; height: 9; radius: 5; color: stageRow.modelData.status === "Working" ? "#279d78" : stageRow.modelData.status === "Blocked" ? "#d88d32" : "#8094b0" }
                                        Body { text: stageRow.modelData.stage; font.weight: Font.DemiBold }
                                    }
                                    RowLayout {
                                        Caption { text: Diagnostics.status(stageRow.modelData.status) }
                                        TouchButton { text: stageRow.expanded ? "Hide details" : "Show details"; onClicked: stageRow.expanded = !stageRow.expanded }
                                    }
                                    Caption {text:Diagnostics.summary(stageRow.modelData)}
                                    Repeater {model:stageRow.expanded?Diagnostics.rows(stageRow.modelData.evidence):[];delegate:ColumnLayout {required property var modelData;Layout.fillWidth:true;Body {text:modelData.label;font.weight:Font.DemiBold}Caption {text:modelData.value;textFormat:Text.PlainText}}}
                                    Rectangle { Layout.fillWidth: true; implicitHeight: 1; color: win.line }
                                }
                            }
                        }
                        Card {
                            visible: win.page === "Settings"
                            Body { text: "Safe by default"; font.pixelSize: 22; font.weight: Font.DemiBold }
                            Caption { text: "EtherMobile działa jako użytkownik pulpitu. Działania sieciowe wymagają uprawnień D-Bus i PolicyKit. Adapter IPA steruje wyłącznie usługą ethermobile-data." }
                            Caption { text: "Wewnętrzny modem Qualcomm używa działającego adaptera IPA, ponieważ standardowy ModemManager odrzuca jego sterownik QMI. Postęp i błędy pochodzą z rzeczywistej usługi danych." }
                            Caption { text: "Airplane mode, restart recovery, detailed usage history, automated retry and suspend/resume acceptance remain pending. Use Diagnostics to retry discovery safely." }
                            TouchButton { text: "Refresh discovery"; enabled: !Mobile.busy; onClicked: Mobile.refresh() }
                        }
                        Card {
                            visible:Mobile.status.dataProvider === "downstream-ipa"
                            Body {text:Mobile.status.dataError||Mobile.operation.state==="Błąd połączenia"||Mobile.operation.state==="Nieobsługiwany profil"?"Błąd połączenia":Mobile.status.dataPending?"Próbuję połączyć…":Mobile.status.dataActive?"Dane komórkowe połączone":"Transmisja danych rozłączona";font.bold:true}
                            BusyIndicator {running:!!Mobile.status.dataPending;visible:running;Layout.preferredWidth:32;Layout.preferredHeight:32}
                            Body {text:Mobile.status.dataMessage || "Sprawdzam usługę transmisji danych…"}
                            Caption {visible:!!Mobile.status.dataErrorDetail;text:(Mobile.status.dataErrorCode?"Kod: "+Mobile.status.dataErrorCode+" · ":"")+(Mobile.status.dataErrorDetail||"")}
                            Caption {text:"Połączeniem steruje adapter IPA. Standardowy ModemManager nie obsługuje tego sterownika QMI."}
                        }
                        Card {
                            visible: Mobile.message.length > 0
                            Body { text: Mobile.message; color: win.muted }
                        }
                    }
                    Item { implicitHeight: 24 }
                }
            }
        }
    }
    Dialog {
        id: confirmation; modal: true; anchors.centerIn: parent
        width: Math.min(win.width - 32, 480); title: "Confirm action"
        standardButtons: Dialog.Ok | Dialog.Cancel
        contentItem: Body { id: confirmText; width: confirmation.availableWidth }
        onAccepted: {
            if(win.pendingAction === "connect") Mobile.connectProfile(win.pendingPath)
            else if(win.pendingAction === "delete") Mobile.deleteProfile(win.pendingPath)
            else if(win.pendingAction === "disconnect") Mobile.disconnectData()
            else if(win.pendingAction === "radio") Mobile.setRadio(win.pendingRadio)
        }
    }
    Dialog {
        id: apnDialog; modal: true; anchors.centerIn: parent
        width: Math.min(win.width - 32, 500); title: win.selectedProfile.path ? "Edit APN" : "Add APN"
        standardButtons: Dialog.Save | Dialog.Cancel
        contentItem: ColumnLayout {
            spacing: 12
            Caption { text: "Enter the values provided by your carrier." }
            Field { id: profileName; placeholderText: "Profile name"; maximumLength: 80 }
            Field { id: profileApn; placeholderText: "Carrier APN"; maximumLength: 100; inputMethodHints: Qt.ImhNoPredictiveText }
            ComboBox { id: ipType; Layout.fillWidth: true; implicitHeight: 50; model: ["IPv4", "IPv4 + IPv6"] }
            CheckBox { id: profileRoam; text: "Allow data roaming (charges may apply)"; Layout.fillWidth: true; implicitHeight: 48 }
            CheckBox { id: profileRoute; text: "Allow a default internet route"; Layout.fillWidth: true; implicitHeight: 48 }
            Caption { text: "Route metric: 900. Review existing route priorities before enabling. With this off, cellular will not become your default internet route. Saving does not connect." }
        }
        onAccepted: Mobile.saveProfile(win.selectedProfile.path || "", profileName.text, profileApn.text, profileRoam.checked, profileRoute.checked, ipType.currentText)
    }
    Dialog {
        id: pinDialog; modal: true; anchors.centerIn: parent
        width: Math.min(win.width - 32, 450); title: "Unlock SIM"
        standardButtons: Dialog.Ok | Dialog.Cancel
        contentItem: ColumnLayout {
            spacing: 14
            Body { text: "Incorrect PINs can lock your SIM. Use only your known PIN. This sends one unlock attempt." }
            Field { id: pinField; placeholderText: "SIM PIN"; echoMode: TextInput.Password; maximumLength: 8; inputMethodHints: Qt.ImhDigitsOnly | Qt.ImhSensitiveData | Qt.ImhNoPredictiveText }
        }
        onAccepted: { Mobile.sendPin(pinField.text); pinField.text = "" }
        onRejected: pinField.text = ""
        onClosed: pinField.text = ""
    }
}
