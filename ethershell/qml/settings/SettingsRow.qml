import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
ItemDelegate {
 id:row;required property var tokens
 property string title:"";property string description:"";property string glyph:"";property string value:""
 property bool arrow:true;property bool dense:false;property bool loading:false;property string error:""
 Layout.fillWidth:true;Layout.minimumWidth:0;implicitHeight:Math.max(dense?32:tokens.target,Math.max(body.implicitHeight,valueLabel.implicitHeight)+(dense?6:16));padding:0
 focusPolicy:Qt.StrongFocus;Accessible.name:title;Accessible.description:description+" "+value+" "+error
 opacity:enabled?1:tokens.disabledOpacity
 background:Rectangle {radius:10;color:row.down?row.tokens.soft:"transparent";border.width:row.activeFocus?2:0;border.color:row.tokens.accent}
 contentItem:RowLayout {
  spacing:10
  Rectangle {visible:row.glyph.length>0;Layout.preferredWidth:36;Layout.preferredHeight:36;radius:12;color:row.tokens.soft
   Image {anchors.centerIn:parent;width:22;height:22;visible:row.glyph.indexOf("icon:")===0;source:visible?"qrc:/icons/"+row.glyph.slice(5)+(row.tokens.dark?"-light":"")+".svg":"";fillMode:Image.PreserveAspectFit}
   Text {anchors.centerIn:parent;visible:row.glyph.indexOf("icon:")!==0;text:row.glyph;color:row.tokens.accent;font.pixelSize:20}
  }
  ColumnLayout {id:body;Layout.fillWidth:true;Layout.minimumWidth:0;spacing:3
   Text {text:row.title;color:row.tokens.ink;font.pixelSize:(row.dense?13:row.tokens.body)*row.tokens.fontScale;wrapMode:Text.Wrap;Layout.fillWidth:true;Layout.minimumWidth:0}
   Text {text:row.error||row.description;visible:text.length>0;color:row.error?row.tokens.danger:row.tokens.muted;font.pixelSize:row.tokens.caption*row.tokens.fontScale;wrapMode:Text.Wrap;Layout.fillWidth:true;Layout.minimumWidth:0}
  }
  Text {id:valueLabel;visible:row.value.length>0;Layout.maximumWidth:row.width*(row.dense?.6:.32);wrapMode:Text.WrapAnywhere;text:row.value;color:row.tokens.muted;font.pixelSize:row.tokens.caption*row.tokens.fontScale}
  Text {visible:row.arrow;text:row.loading?"…":"›";color:row.tokens.ink;font.pixelSize:24}
 }
}

