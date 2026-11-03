import QtQuick
import QtQuick.Controls
import QtQuick.Layouts

ApplicationWindow {
 id: root
 width: 480; height: 900; minimumWidth: 320; minimumHeight: 480
 visible: true; title: "EtherCamera"; color: "#101820"
 flags: Qt.Window | Qt.FramelessWindowHint
 font.pixelSize: 14
 property bool videoMode: false
 component Caption: Label { color: "#edf3f9"; font.pixelSize: 14; wrapMode: Text.Wrap }
 component TouchButton: Button {
  font.pixelSize: 14; implicitHeight: 48
  contentItem: Text {text: parent.text; font: parent.font; color: parent.enabled ? "#edf3f9" : "#7c8792"; horizontalAlignment: Text.AlignHCenter; verticalAlignment: Text.AlignVCenter}
  background: Rectangle {radius: 12; color: parent.down ? "#355778" : "#243443"; border.color: parent.activeFocus ? "#74b9ff" : "#405467"}
 }
 ColumnLayout {
  anchors.fill: parent; anchors.margins: 16; spacing: 12
  RowLayout {
   Layout.fillWidth: true
   Caption {text: "EtherCamera"; font.pixelSize: 23; font.bold: true; Layout.fillWidth: true}
   TouchButton {text: "Zamknij"; onClicked: root.close()}
  }
  Rectangle {
   Layout.fillWidth: true; Layout.fillHeight: true; radius: 16; color: "#070c11"; clip: true
   Image {id: preview; objectName: "preview"; anchors.fill: parent; source: Camera.imageSource; fillMode: Image.PreserveAspectFit; cache: false; visible: Camera.hasFrame && !Camera.privateState}
   ColumnLayout {
    anchors.centerIn: parent; width: Math.min(parent.width-36,460); spacing: 18
    visible: !Camera.hasFrame
    Caption {Layout.fillWidth: true; horizontalAlignment: Text.AlignHCenter; font.pixelSize: 22; font.bold: true
     text: Camera.privateState ? "Kamera zablokowana" : Camera.devices.length === 0 ? "Wbudowane kamery niedostępne" : Camera.active ? "Uruchamianie obrazu…" : "Gotowy do uruchomienia kamery"}
    Caption {Layout.fillWidth: true; horizontalAlignment: Text.AlignHCenter; color: "#a9bacb"
     text: Camera.privateState ? "Odblokuj telefon. Usługa EtherLock musi być dostępna." : Camera.devices.length === 0 ? "Nie wykryto obsługiwanej kamery. Sprawdź instalację sterownika i połączenie urządzenia." : "Dotknij „Uruchom kamerę”, aby udzielić dostępu i rozpocząć podgląd. Odsłoń tylny obiektyw."}
    Caption {Layout.fillWidth: true; horizontalAlignment: Text.AlignHCenter; color: "#a9bacb"; visible: !Camera.privateState && Camera.devices.length === 0
     text: "Na tym systemie można użyć obsługiwanej kamery USB UVC przez OTG. Zdjęcia i filmy wymagają obrazu z fizycznej kamery."}
   }
   Rectangle {
    visible: Camera.recording; color: "#c53642"; radius: 10; width: 150; height: 36; anchors.top: parent.top; anchors.horizontalCenter: parent.horizontalCenter; anchors.topMargin: 12
    Caption {anchors.centerIn: parent; text: "● REC  00:" + (Camera.seconds < 10 ? "0" : "") + Camera.seconds}
   }
  }
  Caption {objectName: "status"; Layout.fillWidth: true; visible: text.length>0; text: Camera.message; color: "#b8d8f4"}
  RowLayout {visible:Camera.active&&!root.videoMode;Layout.fillWidth:true
   TouchButton {text:"Location permission";Layout.fillWidth:true;onClicked:Camera.requestLocation()}
   CheckBox {id:photoLocation;text:"Photo location";checked:false;onToggled:Camera.enableLocation(checked)}
  }
  Caption {Layout.fillWidth: true; visible: Camera.permissionDenied; color: "#ffd297"; text: "Dostęp wyłączony. Zmień uprawnienie w Ustawienia → Aplikacje → Kamera."}
  RowLayout {
   Layout.fillWidth: true; visible: !Camera.active
   ComboBox {id: device; objectName: "device"; Layout.fillWidth: true; implicitHeight: 48; font.pixelSize: 14; model: Camera.devices; textRole: "name"; displayText: count>0 ? currentText : "Brak dostępnej kamery"; enabled: !Camera.busy && !Camera.privateState && count>0}
   TouchButton {objectName: "refresh"; text: "Wykryj"; enabled: !Camera.busy; onClicked: Camera.refresh()}
  }
  TouchButton {
   objectName: "start"; Layout.fillWidth: true; visible: !Camera.active; text: "Uruchom kamerę"
   enabled: Camera.devices.length>0 && !Camera.busy && !Camera.privateState && !Camera.permissionDenied
   onClicked: consent.open()
  }
  RowLayout {
   Layout.alignment: Qt.AlignHCenter; spacing: 12
   TouchButton {objectName: "photoMode"; text: root.videoMode ? "Zdjęcie" : "● Zdjęcie"; enabled: !Camera.recording && !Camera.busy; onClicked: root.videoMode=false}
   TouchButton {objectName: "videoMode"; text: root.videoMode ? "● Film" : "Film"; enabled: !Camera.recording && !Camera.busy; onClicked: root.videoMode=true}
  }
  TouchButton {
   objectName: "shutter"; Layout.fillWidth: true; implicitHeight: 62
   text: Camera.recording ? "■ Zatrzymaj i zapisz film" : root.videoMode ? "● Nagraj film" : "Zrób zdjęcie"
   enabled: !Camera.busy && !Camera.privateState && (Camera.recording || Camera.hasFrame)
   onClicked: {if (Camera.recording) Camera.stopRecording(); else if (root.videoMode) microphone.open(); else Camera.photo()}
  }
  RowLayout {
   Layout.fillWidth: true
   TouchButton {objectName: "release"; text: "Wyłącz kamerę"; Layout.fillWidth: true; enabled: Camera.active && !Camera.busy; onClicked: Camera.release()}
   TouchButton {objectName: "gallery"; text: "Galeria"; Layout.fillWidth: true; enabled: !Camera.privateState && !Camera.busy; onClicked: Camera.gallery()}
  }
 }
 Dialog {
  id: consent; objectName: "consent"; anchors.centerIn: parent; width: Math.min(root.width-32,400); modal: true; title: "Dostęp do kamery"
  contentItem: ColumnLayout {spacing: 16
   Label {Layout.fillWidth: true; wrapMode: Text.Wrap; font.pixelSize: 15; text: "Uruchomić wybraną kamerę i wyświetlić podgląd? Mikrofon pozostanie wyłączony."}
   TouchButton {objectName: "consentAccept"; Layout.fillWidth: true; text: "Zezwól i uruchom"; onClicked: {consent.close(); Camera.start(Camera.devices[device.currentIndex].id)}}
   TouchButton {objectName: "consentCancel"; Layout.fillWidth: true; text: "Anuluj"; onClicked: consent.close()}
  }
 }
 Dialog {
  id: microphone; objectName: "microphone"; anchors.centerIn: parent; width: Math.min(root.width-32,400); modal: true; title: "Dźwięk filmu"
  contentItem: ColumnLayout {spacing: 12
   Label {Layout.fillWidth: true; wrapMode: Text.Wrap; font.pixelSize: 15; text: "Czy nagrywać także mikrofon telefonu? Film: maksymalnie 60 sekund, do 640 × 480, 15 kl./s."}
   TouchButton {objectName: "recordAudio"; Layout.fillWidth: true; text: "Zezwól na mikrofon i nagraj"; onClicked: {microphone.close(); Camera.record(true)}}
   TouchButton {objectName: "recordSilent"; Layout.fillWidth: true; text: "Nagraj bez dźwięku"; onClicked: {microphone.close(); Camera.record(false)}}
   TouchButton {objectName: "recordCancel"; Layout.fillWidth: true; text: "Anuluj"; onClicked: microphone.close()}
  }
 }
 Connections {target: Camera; function onChanged(){if(!Camera.active)photoLocation.checked=false;if(Camera.privateState){consent.close();microphone.close()}}}
 onActiveChanged: if (!active) {consent.close(); microphone.close()}
}
