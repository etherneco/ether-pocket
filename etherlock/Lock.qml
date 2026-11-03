import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
Rectangle {
 id:root
 color:"#f6f8fc"
 property string credential:""
 property bool pin:true
 property bool shift:false
 property bool symbols:false
 readonly property real u:Math.max(1,Math.min(width/420,height/920))
 property string now:Qt.formatDateTime(new Date(),"HH:mm")
 property string date:Qt.formatDateTime(new Date(),"dddd, d MMMM")
 readonly property bool error:Auth.feedback.indexOf("failed")>=0||Auth.feedback.indexOf("unavailable")>=0
 gradient:Gradient {GradientStop {position:0;color:"#eaf2ff"}GradientStop {position:.48;color:"#f8faff"}GradientStop {position:1;color:"#f2f6fc"}}
 function input(text){
  for(let c of text){
   if(c==="\r"||c==="\n"){Auth.submit(credential);credential=""}
   else if(c==="\b"||c==="\x7f")credential=credential.slice(0,-1)
   else if(c==="\x1b") {credential="";Auth.cancel()}
   else if(c==="\x15")credential=""
   else if(c.charCodeAt(0)>=32&&credential.length<256)credential+=c
  }
 }
 component Key:Button {
  id:key
  property bool accent:false
  property bool quiet:false
  property real textSize:15
  implicitHeight:50*root.u
  leftPadding:8*root.u;rightPadding:8*root.u
  font.pixelSize:textSize*root.u;font.weight:Font.Medium
  opacity:enabled?1:.42
  background:Rectangle {
   radius:17*root.u
   color:key.down?(key.accent?"#1d4ed8":"#e0ebfa"):(key.accent?"#2563eb":key.quiet?"transparent":"#ffffff")
   border.width:key.activeFocus?2:1
   border.color:key.activeFocus?"#2563eb":key.quiet?"transparent":"#d7e1ef"
   Behavior on color {ColorAnimation {duration:100}}
  }
  contentItem:Text {text:key.text;color:key.accent?"#ffffff":"#203650";font:key.font;horizontalAlignment:Text.AlignHCenter;verticalAlignment:Text.AlignVCenter}
  scale:down?.97:1
  Behavior on scale {NumberAnimation {duration:90}}
 }
 Connections {target:Auth;function onClearInput(){root.credential=""}function onKeyInput(text){root.input(text)}}
 Timer {interval:1000;running:true;repeat:true;onTriggered:{root.now=Qt.formatDateTime(new Date(),"HH:mm");root.date=Qt.formatDateTime(new Date(),"dddd, d MMMM")}}
 ScrollView {anchors.fill:parent;contentWidth:availableWidth;clip:true
  ColumnLayout {width:Math.min(root.width-40*root.u,400*root.u);x:(root.width-width)/2;spacing:9*root.u
   Item {Layout.preferredHeight:Math.max(16*root.u,root.height*.035)}
   RowLayout {Layout.alignment:Qt.AlignHCenter;spacing:7*root.u
    Rectangle {width:6*root.u;height:6*root.u;radius:width/2;color:"#2563eb"}
    Text {text:"ETHERLOCK";color:"#536d8a";font.pixelSize:11*root.u;font.letterSpacing:2*root.u;font.weight:Font.Medium}
   }
   Text {text:root.now;color:"#162b46";font.pixelSize:54*root.u;font.weight:Font.Light;Layout.alignment:Qt.AlignHCenter}
   Text {text:root.date;color:"#536d8a";font.pixelSize:14*root.u;Layout.alignment:Qt.AlignHCenter}
   Item {Layout.preferredHeight:8*root.u}
   Text {text:"Welcome back";color:"#162b46";font.pixelSize:21*root.u;font.weight:Font.DemiBold;Layout.alignment:Qt.AlignHCenter}
   Text {text:"Use your Linux account password";color:"#536d8a";font.pixelSize:13*root.u;Layout.alignment:Qt.AlignHCenter}
   Rectangle {Layout.fillWidth:true;Layout.preferredHeight:56*root.u;radius:18*root.u;color:"#ffffff";border.width:1;border.color:root.error?"#c7485c":"#c4d3e5"
    Text {anchors.centerIn:parent;text:root.credential.length?"●  ●  ●  ●":"Enter password";color:root.credential.length?"#203650":"#667c96";font.pixelSize:16*root.u}
   }
   Text {Layout.fillWidth:true;text:root.error?Auth.feedback:Auth.waiting?"Your session stays private until you unlock.":Auth.feedback;color:root.error?"#b42338":"#536d8a";wrapMode:Text.Wrap;horizontalAlignment:Text.AlignHCenter;font.pixelSize:12*root.u}
   GridLayout {columns:3;columnSpacing:10*root.u;rowSpacing:9*root.u;Layout.fillWidth:true;visible:root.pin
    Repeater {model:["1","2","3","4","5","6","7","8","9","Clear","0","⌫"]
     Key {required property string modelData;text:modelData;textSize:modelData.length>1?12:25;quiet:modelData==="Clear"||modelData==="⌫";Layout.fillWidth:true;Layout.preferredHeight:56*root.u;enabled:Auth.waiting;onClicked:{if(modelData==="Clear")root.credential="";else if(modelData==="⌫")root.credential=root.credential.slice(0,-1);else root.input(modelData)}}
    }
   }
   ColumnLayout {visible:!root.pin;Layout.fillWidth:true;spacing:6*root.u
    Repeater {model:root.symbols?["1234567890","!@#$%^&*()","-_=+[]{}",";:'\"/?,.\\|"]:["qwertyuiop","asdfghjkl","zxcvbnm"]
     RowLayout {required property string modelData;Layout.fillWidth:true;spacing:3*root.u
      Repeater {model:modelData.split("");Key {required property string modelData;text:root.shift?modelData.toUpperCase():modelData;textSize:16;Layout.fillWidth:true;Layout.preferredWidth:28*root.u;Layout.preferredHeight:45*root.u;enabled:Auth.waiting;onClicked:root.input(text)}}
     }
    }
    RowLayout {Layout.fillWidth:true;spacing:4*root.u
     Key {text:"⇧";Layout.fillWidth:true;onClicked:root.shift=!root.shift}
     Key {text:root.symbols?"ABC":"#+=";Layout.fillWidth:true;onClicked:root.symbols=!root.symbols}
     Key {text:"Space";Layout.fillWidth:true;enabled:Auth.waiting;onClicked:root.input(" ")}
     Key {text:"⌫";Layout.fillWidth:true;enabled:Auth.waiting;onClicked:root.credential=root.credential.slice(0,-1)}
    }
   }
   Key {text:"Unlock  →";accent:true;textSize:16;Layout.fillWidth:true;Layout.preferredHeight:52*root.u;enabled:Auth.waiting&&root.credential.length>0;onClicked:{Auth.submit(root.credential);root.credential=""}}
   RowLayout {Layout.fillWidth:true;spacing:6*root.u
    Key {text:root.pin?"Use letters":"Use numbers";quiet:true;Layout.fillWidth:true;onClicked:{root.credential="";root.pin=!root.pin}}
    Key {text:"Try again";quiet:true;visible:!Auth.waiting;Layout.fillWidth:true;onClicked:Auth.begin()}
   }
   Text {Layout.fillWidth:true;text:"Account password only · no separate PIN\nEmergency calling unavailable";color:"#526a85";font.pixelSize:11*root.u;wrapMode:Text.Wrap;horizontalAlignment:Text.AlignHCenter;lineHeight:1.35}
   Item {Layout.preferredHeight:20*root.u}
  }
 }
}
