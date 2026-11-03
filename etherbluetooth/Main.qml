import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import QtQuick.Window

ApplicationWindow {
    id: root
    visible: true
    width: 1200; height: 800
    minimumWidth: 360; minimumHeight: 540
    title: "EtherBluetooth"
    color: "#edf5ff"
    property string page: "devices"
    property string selectedPath: ""
    property var current: {
        for (let d of Bluetooth.devices) if (d.path === selectedPath) return d
        return ({})
    }
    property var adapterInfo: {
        for (let a of Bluetooth.adapters) if (a.path === Bluetooth.adapter) return a
        return ({})
    }
    property bool wide: width >= 1000
    property string recoveryAction: ""
    font.family: "Sans Serif"
    font.pixelSize: 15
    component Card: Rectangle {
        radius: 20; color: "#fcfdff"; border.color: "#d9e8fc"
    }
    component Action: Button {
        id: action
        implicitHeight: Math.max(52,contentItem.implicitHeight + 20)
        font.pixelSize: 15
        padding: 12
        background: Rectangle {radius: 14; color: !action.enabled ? "#f1f4fa" : action.down ? "#cce1ff" : "#e5f0ff"; border.color: "#d9e8fc"}
        contentItem: Text {text: action.text; font: action.font; horizontalAlignment: Text.AlignHCenter; verticalAlignment: Text.AlignVCenter; wrapMode: Text.Wrap; color: action.enabled ? "#0066ed" : "#9caac2"}
    }
    component Heading: Label {font.pixelSize: 23; font.bold: true; color: "#0b204d"; wrapMode: Text.Wrap}
    component Muted: Label {color: "#557096"; wrapMode: Text.Wrap; textFormat: Text.PlainText}
    background: Rectangle {
        gradient: Gradient {GradientStop {position: 0; color: "#f8fcff"} GradientStop {position: 1; color: "#dcecff"}}
        Rectangle {width: 480; height: 480; radius: 240; color: "#d7edff"; opacity: 0.45; x: -180; y: 250}
    }
    header: ToolBar {
        background: Rectangle {color: "#f6fbff"; border.color: "#d9e8fc"}
        RowLayout {
            anchors.fill: parent; anchors.margins: 12; spacing: 12
            Rectangle {width: 40; height: 40; radius: 13; color: "#0077ff"; Image {anchors.centerIn: parent; width: 30; height: 30; source: "qrc:/bluetooth.svg"}}
            Label {text: "EtherBluetooth"; color: "#102653"; font.bold: true; font.pixelSize: 20; Layout.fillWidth: true}
            Action {text: "Audio"; onClicked: {root.page = "audio"; Audio.refresh()}}
            Action {text: root.page === "doctor" ? "Urządzenia" : "Driver Doctor"; onClicked: {root.page = root.page === "doctor" ? "devices" : "doctor"; if(root.page === "doctor") Bluetooth.diagnose()}}
        }
        implicitHeight: 78
    }
    ScrollView {
        anchors.fill: parent; clip: true
        contentWidth: availableWidth
        ColumnLayout {
            width: parent.width; spacing: 16
            Item {Layout.preferredHeight: 4}
            Frame {
                visible: Bluetooth.error.length > 0
                Layout.fillWidth: true; Layout.leftMargin: 16; Layout.rightMargin: 16
                background: Rectangle {radius: 12; color: "#fff0e7"; border.color: "#f1c6a9"}
                Label {width: parent.width; text: Bluetooth.error; wrapMode: Text.Wrap; color: "#783c18"; textFormat: Text.PlainText}
            }
            GridLayout {
                visible: root.page === "devices"
                Layout.fillWidth: true; Layout.leftMargin: 16; Layout.rightMargin: 16
                columns: root.wide ? 3 : 1; columnSpacing: 16; rowSpacing: 16
                Card {
                    Layout.fillWidth: true; Layout.preferredWidth: 300; Layout.preferredHeight: controls.implicitHeight + 40
                    ColumnLayout {
                        id: controls
                        anchors {left: parent.left; right: parent.right; top: parent.top; margins: 20} spacing: 16
                        Heading {text: "Bluetooth"}
                        RowLayout {
                            Layout.fillWidth: true
                            Muted {text: root.adapterInfo.Powered ? "Włączony" : Bluetooth.adapters.length ? "Wyłączony" : "Brak kontrolera HCI"; Layout.fillWidth: true}
                            Switch {checked: !!root.adapterInfo.Powered; enabled: Bluetooth.adapters.length > 0; onClicked: Bluetooth.power(checked)}
                        }
                        ComboBox {
                            visible: Bluetooth.adapters.length > 0; Layout.fillWidth: true; implicitHeight: 52
                            model: Bluetooth.adapters; textRole: "Alias"
                            onActivated: Bluetooth.selectAdapter(Bluetooth.adapters[currentIndex].path)
                        }
                        Rectangle {Layout.fillWidth: true; height: 1; color: "#e0eafa"}
                        Muted {Layout.fillWidth: true; text: Bluetooth.adapters.length ? "Stan kontrolera pochodzi z BlueZ. Wyszukiwanie zatrzyma się po 30 sekundach." : "Usługa może działać bez kontrolera. Driver Doctor sprawdzi sterownik, firmware i inicjalizację sprzętu."}
                        Action {text: root.adapterInfo.Discovering ? "Zatrzymaj wyszukiwanie" : "+  Dodaj urządzenie"; Layout.fillWidth: true; enabled: !!root.adapterInfo.Powered; onClicked: Bluetooth.scan(!root.adapterInfo.Discovering)}
                        BusyIndicator {running: !!root.adapterInfo.Discovering; visible: running; Layout.alignment: Qt.AlignHCenter}
                        Switch {text: "Widoczność przez 2 minuty"; checked: !!root.adapterInfo.Discoverable; enabled: !!root.adapterInfo.Powered; onClicked: Bluetooth.discoverable(checked); Layout.fillWidth: true}
                        Action {text: "Diagnostyka sprzętu  →"; Layout.fillWidth: true; onClicked: {root.page = "doctor"; Bluetooth.diagnose()}}
                        Switch {text: "Powiadomienia Bluetooth"; checked: Bluetooth.notifications; onClicked: Bluetooth.notifications = checked}
                        Muted {text: "EtherPocket · BlueZ / D-Bus\nEtherneco LTD"; font.pixelSize: 12}
                    }
                }
                Card {
                    Layout.fillWidth: true; Layout.preferredWidth: 360; Layout.preferredHeight: Math.max(420, deviceList.implicitHeight + 40)
                    ColumnLayout {
                        id: deviceList
                        anchors {left: parent.left; right: parent.right; top: parent.top; margins: 20} spacing: 12
                        Heading {text: "Twoje urządzenia"}
                        Muted {text: "Połączone, sparowane i w pobliżu"}
                        Repeater {
                            model: Bluetooth.devices
                            delegate: ItemDelegate {
                                required property var modelData
                                Layout.fillWidth: true; implicitHeight: 90
                                background: Rectangle {radius: 14; color: root.selectedPath === modelData.path ? "#e1efff" : "#f5f9ff"; border.color: "#dfebfa"}
                                contentItem: RowLayout {
                                    Rectangle {width: 44; height: 44; radius: 14; color: "#0077ff"; Image {anchors.centerIn: parent; width: 28; height: 28; source: "qrc:/bluetooth.svg"}}
                                    ColumnLayout {
                                        Layout.fillWidth: true
                                        Label {text: modelData.name; font.bold: true; color: "#142d54"; elide: Text.ElideRight; Layout.fillWidth: true; textFormat: Text.PlainText}
                                        Muted {text: modelData.state; color: modelData.Connected ? "#009a6d" : "#557096"}
                                        Muted {text: modelData.category; font.pixelSize: 12}
                                    }
                                    Label {text: modelData.battery !== undefined ? modelData.battery + "%" : "›"; color: "#557096"}
                                }
                                onClicked: root.selectedPath = modelData.path
                            }
                        }
                        Muted {visible: Bluetooth.devices.length === 0; Layout.fillWidth: true; text: root.adapterInfo.Discovering ? "Szukanie urządzeń… Włącz tryb parowania na urządzeniu." : "Brak urządzeń. Włącz kontroler i rozpocznij wyszukiwanie."; Layout.topMargin: 48}
                    }
                }
                Card {
                    Layout.fillWidth: true; Layout.preferredWidth: 360; Layout.preferredHeight: Math.max(420, details.implicitHeight + 40)
                    ColumnLayout {
                        id: details
                        anchors {left: parent.left; right: parent.right; top: parent.top; margins: 20} spacing: 12
                        Heading {text: root.current.name || "Szczegóły urządzenia"; textFormat: Text.PlainText}
                        Muted {text: root.current.state || "Wybierz urządzenie z listy."}
                        Muted {text: root.current.error || ""; visible: text.length > 0; Layout.fillWidth: true}
                        ColumnLayout {
                            visible: !!root.current.path; Layout.fillWidth: true; spacing: 12
                            Muted {text: (root.current.category || "") + (root.current.battery !== undefined ? " · Bateria " + root.current.battery + "%" : "")}
                            Muted {text: root.current.RSSI !== undefined ? "Sygnał: " + root.current.RSSI + " dBm" : "Sygnał: niedostępny"}
                            Action {Layout.fillWidth: true; text: !root.current.Paired ? "Sparuj urządzenie" : root.current.Connected ? "Rozłącz" : "Połącz"; onClicked: Bluetooth.action(root.selectedPath, !root.current.Paired ? "pair" : root.current.Connected ? "disconnect" : "connect")}
                            Action {visible: root.current.state === "Pairing"; text: "Anuluj parowanie"; Layout.fillWidth: true; onClicked: Bluetooth.action(root.selectedPath,"cancel")}
                            Switch {text: "Zaufane urządzenie"; checked: !!root.current.Trusted; onClicked: Bluetooth.action(root.selectedPath,"trust",checked ? "on" : "off")}
                            Switch {text: "Ponów utracone połączenie"; checked: !!root.current.autoConnect; onClicked: Bluetooth.action(root.selectedPath,"autoConnect",checked ? "on" : "off")}
                            Muted {text: "Maks. 4 próby, tylko dla zaufanych urządzeń. Ręczne rozłączenie zatrzymuje próby."; font.pixelSize: 12; Layout.fillWidth: true}
                            TextField {id: alias; Layout.fillWidth: true; implicitHeight: 52; placeholderText: "Nowa nazwa lokalna"; maximumLength: 248}
                            Action {text: "Zmień nazwę"; Layout.fillWidth: true; enabled: alias.text.trim().length > 0; onClicked: {Bluetooth.action(root.selectedPath,"alias",alias.text); alias.clear()}}
                            Muted {text: "Usługi rozpoznane przez BlueZ"; font.bold: true}
                            Muted {Layout.fillWidth: true; text: (root.current.profiles || []).join("\n"); font.pixelSize: 12}
                            Muted {text: root.current.ServicesResolved ? "Usługi rozwiązane" : "Usługi jeszcze nierozwiązane"}
                            Muted {text: (root.current.inputNodes || []).length ? "Wejście jądra: " + root.current.inputNodes.join(", ") : "Brak potwierdzonego wejścia jądra dla tego urządzenia"; Layout.fillWidth: true; font.pixelSize: 12}
                            Action {text: "Inspektor GATT"; Layout.fillWidth: true; onClicked: Bluetooth.inspectGatt(root.selectedPath)}
                            Repeater {
                                model: Bluetooth.gatt
                                delegate: ColumnLayout {
                                    required property var modelData
                                    Layout.fillWidth: true
                                    Muted {text: modelData.UUID; Layout.fillWidth: true; font.pixelSize: 12}
                                    Action {text: "Odczytaj"; visible: (modelData.flags || []).indexOf("read") >= 0; onClicked: Bluetooth.readGatt(modelData.path)}
                                    Switch {text: "Powiadomienia GATT"; visible: (modelData.flags || []).indexOf("notify") >= 0 || (modelData.flags || []).indexOf("indicate") >= 0; checked: !!modelData.Notifying; onClicked: Bluetooth.notifyGatt(modelData.path,checked)}
                                }
                            }
                            Muted {text: "Ostatnie połączenie: " + (root.current.lastConnected || "brak zapisu"); Layout.fillWidth: true; font.pixelSize: 12}
                            Repeater {
                                model: root.current.history || []
                                delegate: Muted {required property var modelData; text: modelData.event + " · " + modelData.time; font.pixelSize: 12; Layout.fillWidth: true}
                            }
                            Action {text: "Zapomnij urządzenie"; Layout.fillWidth: true; onClicked: forget.open()}
                        }
                    }
                }
            }
            Card {
                visible: root.page === "audio"
                Layout.fillWidth: true; Layout.leftMargin: 16; Layout.rightMargin: 16
                Layout.preferredHeight: audioPanel.implicitHeight + 48
                ColumnLayout {
                    id: audioPanel
                    anchors {left: parent.left; right: parent.right; top: parent.top; margins: 24} spacing: 16
                    Heading {text: "Wyjście audio"}
                    Muted {Layout.fillWidth: true; text: "Dostępne wyjścia i wejścia z serwera audio. Połączenie Bluetooth nie oznacza, że profil audio jest dostępny."}
                    Action {text: "Odśwież audio"; onClicked: Audio.refresh()}
                    Repeater {
                        model: Audio.outputs
                        delegate: ColumnLayout {
                            required property var modelData
                            Layout.fillWidth: true; spacing: 8
                            Label {text: modelData.description; font.bold: true; color: "#142d54"; Layout.fillWidth: true; wrapMode: Text.Wrap; textFormat: Text.PlainText}
                            Muted {text: modelData.state + " · " + modelData.name; Layout.fillWidth: true}
                            Action {text: "Ustaw jako wyjście domyślne"; onClicked: Audio.select("output",modelData.name)}
                            RowLayout {
                                Layout.fillWidth: true
                                Slider {id: outputVolume; Layout.fillWidth: true; implicitHeight: 52; from: 0; to: 100; stepSize: 1; value: {const channels = Object.values(modelData.volume || {}); return channels.length ? parseInt(channels[0].value_percent) : 0} onMoved: volumeDebounce.restart()}
                                Label {text: Math.round(outputVolume.value) + "%"}
                                Timer {id: volumeDebounce; interval: 200; onTriggered: Audio.volume(modelData.name,Math.round(outputVolume.value))}
                            }
                            Switch {text: "Wycisz"; checked: !!modelData.mute; onClicked: Audio.mute(modelData.name,checked)}
                        }
                    }
                    Muted {visible: Audio.outputs.length === 0; text: "Brak wyjść audio. Sprawdź połączenie urządzenia, profil i serwer audio."; Layout.fillWidth: true}
                    Heading {text: "Wejście audio"}
                    Repeater {
                        model: Audio.inputs
                        delegate: Action {
                            required property var modelData
                            Layout.fillWidth: true; text: modelData.description
                            onClicked: Audio.select("input",modelData.name)
                        }
                    }
                    Heading {text: "Profile kart"}
                    Repeater {
                        model: Audio.cards
                        delegate: ColumnLayout {
                            id: cardEntry
                            required property var modelData
                            Layout.fillWidth: true
                            Muted {text: cardEntry.modelData.name; Layout.fillWidth: true}
                            Repeater {
                                model: Object.keys(cardEntry.modelData.profiles || {}).filter(function(key) { const available = cardEntry.modelData.profiles[key].available; return available !== "no" && available !== false })
                                delegate: Action {
                                    required property string modelData
                                    Layout.fillWidth: true
                                    text: (cardEntry.modelData.active_profile === modelData ? "✓  " : "") + modelData
                                    onClicked: Audio.profile(cardEntry.modelData.name,modelData)
                                }
                            }
                        }
                    }
                    Action {text: "Zaawansowane ustawienia audio"; onClicked: Audio.controlPanel()}
                    Muted {text: Audio.status; Layout.fillWidth: true; font.pixelSize: 12}
                }
            }
            Card {
                visible: root.page === "doctor"
                Layout.fillWidth: true; Layout.leftMargin: 16; Layout.rightMargin: 16
                Layout.preferredHeight: doctor.implicitHeight + 48
                ColumnLayout {
                    id: doctor
                    anchors {left: parent.left; right: parent.right; top: parent.top; margins: 24} spacing: 18
                    Heading {text: "Driver Doctor"; font.pixelSize: 30}
                    Muted {Layout.fillWidth: true; text: "Sprzęt → sterownik → firmware → HCI → BlueZ → wyszukiwanie. Raport tylko do odczytu; brak automatycznej instalacji sterowników."}
                    Action {text: Bluetooth.diagnosing ? "Sprawdzanie…" : "Uruchom diagnostykę"; enabled: !Bluetooth.diagnosing; onClicked: Bluetooth.diagnose()}
                    Action {text: "Odblokuj Bluetooth…"; enabled: Bluetooth.recoveryAvailable; onClicked: {root.recoveryAction = "unblock-bluetooth"; recovery.open()}}
                    Action {text: "Uruchom ponownie BlueZ…"; enabled: Bluetooth.recoveryAvailable; onClicked: {root.recoveryAction = "restart-service"; recovery.open()}}
                    Muted {visible: !Bluetooth.recoveryAvailable; text: "Naprawy wymagające administratora są niedostępne: brak pakietu pkexec."; Layout.fillWidth: true}
                    BusyIndicator {running: Bluetooth.diagnosing; visible: running}
                    Muted {text: Bluetooth.diagnosis.error || ""; visible: text.length > 0; Layout.fillWidth: true}
                    Repeater {
                        model: Bluetooth.diagnosis.checks || []
                        delegate: Rectangle {
                            required property var modelData
                            Layout.fillWidth: true; implicitHeight: check.implicitHeight + 28; radius: 14
                            color: modelData.status === "Working" ? "#eafaf3" : "#fff5e9"
                            ColumnLayout {
                                id: check
                                anchors {left: parent.left; right: parent.right; top: parent.top; margins: 14} spacing: 7
                                Label {text: modelData.stage + "  ·  " + modelData.status; font.bold: true; color: "#142d54"; Layout.fillWidth: true; wrapMode: Text.Wrap}
                                Muted {text: typeof modelData.evidence === "string" ? modelData.evidence : JSON.stringify(modelData.evidence); Layout.fillWidth: true}
                                Muted {text: modelData.repair; Layout.fillWidth: true; font.pixelSize: 13}
                            }
                        }
                    }
                    Muted {text: "Device tree: " + JSON.stringify(Bluetooth.diagnosis.device_tree || []); Layout.fillWidth: true}
                    Muted {text: "Firmware: " + (Bluetooth.diagnosis.firmware_compatibility || "Nie sprawdzono"); Layout.fillWidth: true}
                    Muted {text: "Brak kontrolera oznacza brak testu parowania, audio i urządzeń wejściowych. Poprawny stan BlueZ nie potwierdza działania sprzętu."; Layout.fillWidth: true}
                }
            }
            Item {Layout.preferredHeight: 16}
        }
    }
    Dialog {
        id: recovery; anchors.centerIn: parent; width: Math.min(root.width - 32,460); modal: true
        implicitHeight: Math.min(root.height - 32,340)
        title: "Potwierdź naprawę"
        standardButtons: Dialog.Ok | Dialog.Cancel
        contentItem: Label {width: recovery.availableWidth; text: root.recoveryAction === "restart-service" ? "Restart usługi Bluetooth rozłączy wszystkie urządzenia. System poprosi o uprawnienia administratora. Ta czynność nie naprawia brakującego sterownika." : "Usunięcie blokady programowej może włączyć zasilanie radia Bluetooth. System poprosi o uprawnienia administratora. Brakujący transport HCI pozostanie nierozwiązany."; wrapMode: Text.Wrap}
        onAccepted: Bluetooth.recover(root.recoveryAction)
    }
    Dialog {
        id: forget; anchors.centerIn: parent; width: Math.min(root.width - 32,420); modal: true
        implicitHeight: Math.min(root.height - 32,260)
        title: "Zapomnieć urządzenie?"
        standardButtons: Dialog.Ok | Dialog.Cancel
        contentItem: Label {width: forget.availableWidth; text: "BlueZ usunie klucze parowania. Następne połączenie będzie wymagać ponownego parowania."; wrapMode: Text.Wrap}
        onAccepted: {Bluetooth.action(root.selectedPath,"forget"); root.selectedPath = ""}
    }
    Dialog {
        id: pairingDialog; anchors.centerIn: parent; width: Math.min(root.width - 32,460); modal: true
        implicitHeight: Math.min(root.height - 32,440)
        visible: !!Bluetooth.pairing.kind
        closePolicy: Popup.NoAutoClose
        title: "Parowanie urządzenia"
        contentItem: ColumnLayout {
            width: pairingDialog.availableWidth; spacing: 16
            Muted {Layout.fillWidth: true; text: Bluetooth.pairing.device || ""}
            Label {text: Bluetooth.pairing.value || "Potwierdź żądanie na obu urządzeniach"; font.pixelSize: 24; font.bold: true; wrapMode: Text.Wrap; Layout.fillWidth: true; textFormat: Text.PlainText}
            TextField {id: pin; visible: Bluetooth.pairing.kind === "pin" || Bluetooth.pairing.kind === "passkey"; placeholderText: "PIN / passkey"; maximumLength: Bluetooth.pairing.kind === "pin" ? 16 : 6; Layout.fillWidth: true; implicitHeight: 56}
            Action {visible: Bluetooth.pairing.kind !== "display"; text: "Potwierdź"; Layout.fillWidth: true; onClicked: {Bluetooth.answer(true,pin.text); pin.clear()}}
            Action {text: "Odrzuć / anuluj"; Layout.fillWidth: true; onClicked: {const device = Bluetooth.pairing.device; Bluetooth.answer(false); Bluetooth.action(device,"cancel"); pin.clear()}}
        }
    }
}
