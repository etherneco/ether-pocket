import QtQuick
import QtQuick.Layouts
SettingsSection {id:card;property string title:"";property string description:""
 Text {text:card.title;color:card.tokens.ink;font.pixelSize:card.tokens.sectionTitle*card.tokens.fontScale;font.bold:true;wrapMode:Text.WordWrap;Layout.fillWidth:true}
 SettingsStatus {tokens:card.tokens;text:card.description;Layout.fillWidth:true}
}

