import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
ColumnLayout {
 id:row;required property var tokens;property string title:"";property real value:0;property real from:0;property real to:100;property real stepSize:1;property string suffix:"";signal moved(real value)
 Layout.fillWidth:true;spacing:2
 Text {text:row.title+"  "+Math.round(row.value*100)/100+row.suffix;color:row.tokens.ink;font.pixelSize:row.tokens.body*row.tokens.fontScale;wrapMode:Text.WordWrap;Layout.fillWidth:true}
 Slider {id:slider;Layout.fillWidth:true;implicitHeight:row.tokens.target;from:row.from;to:row.to;stepSize:row.stepSize;value:row.value;Accessible.name:row.title;onMoved:row.moved(value)
  background:Rectangle {x:slider.leftPadding;y:slider.topPadding+slider.availableHeight/2-3;width:slider.availableWidth;height:6;radius:3;color:row.tokens.soft;Rectangle {width:slider.visualPosition*parent.width;height:parent.height;radius:3;color:row.tokens.accent}}
  handle:Rectangle {x:slider.leftPadding+slider.visualPosition*(slider.availableWidth-width);y:slider.topPadding+slider.availableHeight/2-height/2;width:24;height:24;radius:12;color:row.tokens.accent;border.color:slider.activeFocus?row.tokens.ink:row.tokens.surface;border.width:2}
 }
}

