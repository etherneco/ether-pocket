import QtQuick.Controls
SettingsDialog {title:"Authorization required";standardButtons:Dialog.Ok;contentItem:SettingsStatus {tokens:parent.tokens;text:"The system service checks your permissions. Confirm in the existing PolicyKit dialog if prompted."}}
