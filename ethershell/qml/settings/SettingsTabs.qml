import QtQuick
import QtQuick.Controls
Flickable {
 id:tabs;required property var tokens;property var model:[];property int currentIndex:0;signal selected(int index)
 implicitHeight:tokens.target;contentWidth:buttons.width;contentHeight:height;clip:true;boundsBehavior:Flickable.StopAtBounds
 Row {id:buttons;spacing:4
  Repeater {model:tabs.model
   SettingsAction {required property int index;required property var modelData;tokens:tabs.tokens;text:String(modelData);textSize:13;primary:index===tabs.currentIndex;implicitWidth:Math.max(50,implicitContentWidth+16);height:tabs.height;onClicked:tabs.selected(index)}
  }
 }
}

