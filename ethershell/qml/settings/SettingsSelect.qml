import QtQuick
import QtQuick.Controls
SettingsAction {
 id:select;property var model:[];property int currentIndex:0;property string textRole:"";property string valueRole:"";property string title:"Choose"
 readonly property var currentItem:model.length?model[Math.max(0,currentIndex)]:null
 readonly property var currentValue:valueRole&&currentItem?currentItem[valueRole]:currentItem
 readonly property string currentText:currentItem===null?"Unavailable":textRole?String(currentItem[textRole]):String(currentItem)
 signal activated(int index)
 text:currentText+"  ⌄"
 onClicked:sheet.open()
 SettingsBottomSheet {
  id:sheet;tokens:select.tokens;title:select.title
  ListView {implicitHeight:Math.min(380,contentHeight);implicitWidth:280;clip:true;model:select.model
   delegate:SettingsRow {required property int index;required property var modelData;tokens:select.tokens;width:ListView.view.width;title:select.textRole?String(modelData[select.textRole]):String(modelData);value:index===select.currentIndex?"✓":"";arrow:false;onClicked:{select.currentIndex=index;select.activated(index);sheet.close()}}
  }
 }
}

