import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import QtQuick.Window
ApplicationWindow {
 id:win;visible:true;width:420;height:850;minimumWidth:340;minimumHeight:480
 title:"EtherPhone";color:"#f2f7ff";flags:Qt.Window | (PocketDisplay?Qt.FramelessWindowHint:0)
 property int tab:0
 property string query:""
 property var prefs:Phone.state.config||({})
 property var status:Phone.state.status||({})
 property var calls:Phone.state.calls||[]
 property real unit:PocketDisplay?Math.max(1,Math.min(win.width/420,win.height/850)):1
 property var editing:({})
 component LabelText:Text {textFormat:Text.PlainText;color:"#183454";font.pixelSize:14;wrapMode:Text.WordWrap}
 component Action:Button {
  id:b;property bool primary:false;property int labelSize:15;implicitHeight:48;implicitWidth:Math.max(48,contentItem.implicitWidth+24)
  contentItem:Text {text:b.text;color:b.primary?"white":"#183454";font.pixelSize:b.labelSize;horizontalAlignment:Text.AlignHCenter;verticalAlignment:Text.AlignVCenter;elide:Text.ElideRight}
  background:Rectangle {color:b.primary?"#087dff":b.down?"#deebfc":"white";radius:16;border.color:"#d8e8fa";opacity:b.enabled?1:.4}
  Accessible.name:text
 }
 Item {width:Math.min(win.width/win.unit,800);height:win.height/win.unit;x:(win.width-width*win.unit)/2;scale:win.unit;transformOrigin:Item.TopLeft
 ColumnLayout {anchors.fill:parent;anchors.margins:14;spacing:8
  RowLayout {Layout.fillWidth:true
   LabelText {text:"EtherPhone";font.pixelSize:28;font.bold:true;Layout.fillWidth:true}
   Action {text:"×";Accessible.name:"Close EtherPhone";onClicked:win.close()}
  }
  LabelText {Layout.fillWidth:true;text:status.voice?(status.registered?"Network registered · voice control exposed":"Voice control · network unavailable"):"Cellular calling unavailable";font.bold:true;color:status.registered?"#217351":"#8a531c"}
  LabelText {Layout.fillWidth:true;text:Phone.message||Phone.state.lastFailure||"Calls and two-way audio are not verified.";font.pixelSize:12;maximumLineCount:3;elide:Text.ElideRight}
  StackLayout {Layout.fillWidth:true;Layout.fillHeight:true;currentIndex:win.tab
   ScrollView {clip:true;contentWidth:availableWidth
    ColumnLayout {width:parent.width;spacing:10
     Repeater {model:win.calls;delegate:Rectangle {
      required property var modelData;Layout.fillWidth:true;implicitHeight:callColumn.implicitHeight+24;color:"#e1efff";radius:18
      ColumnLayout {id:callColumn;anchors.fill:parent;anchors.margins:12
       LabelText {text:modelData.name||modelData.number||"Private caller";font.pixelSize:22;Layout.fillWidth:true}
       LabelText {text:modelData.state+" · "+modelData.duration+"s (observed active time)";Layout.fillWidth:true}
       LabelText {visible:!!modelData.requested;text:"Requested: "+modelData.requested+" · awaiting modem";Layout.fillWidth:true}
       RowLayout {Layout.fillWidth:true
        Action {text:"Answer";primary:true;visible:modelData.state==="Incoming";enabled:!Phone.busy;Layout.fillWidth:true;onClicked:Phone.command("answer",modelData.key,{})}
        Action {text:modelData.state==="Incoming"||modelData.state==="Waiting"?"Decline":"End call";enabled:!Phone.busy;Layout.fillWidth:true;onClicked:Phone.command(modelData.state==="Incoming"||modelData.state==="Waiting"?"decline":"end",modelData.key,{})}
       }
       RowLayout {Action {text:"Mute";enabled:false}Action {text:"Speaker";enabled:false}}
       LabelText {text:"Voice audio routes, Bluetooth call audio and hold are unverified.";font.pixelSize:12;Layout.fillWidth:true}
      }
     }}
     TextField {font.pixelSize:26;id:digits;objectName:"dialNumber";Layout.fillWidth:true;implicitHeight:54;placeholderText:"Phone number";horizontalAlignment:Text.AlignHCenter;maximumLength:128;selectByMouse:true;inputMethodHints:Qt.ImhDialableCharactersOnly;Accessible.name:"Phone number"}
     RowLayout {Layout.fillWidth:true
      Action {text:"Paste";Layout.fillWidth:true;onClicked:digits.text=Phone.pasteNumber()}
      Action {text:"⌫";Accessible.name:"Delete digit";Layout.fillWidth:true;onClicked:digits.text=digits.text.slice(0,-1)}
      Action {text:"Save";Layout.fillWidth:true;onClicked:win.editContact({numbers:[digits.text]})}
     }
     GridLayout {columns:3;rowSpacing:8;columnSpacing:8;Layout.fillWidth:true
      Repeater {model:["1","2","3","4","5","6","7","8","9","*","0","#"]
       delegate:Action {required property string modelData;objectName:"key-"+modelData;Layout.fillWidth:true;implicitHeight:54;text:modelData
        onClicked:{if(win.calls.length){var c=win.calls.find(c=>c.state==="Active");if(c)Phone.command("dtmf",c.key,{tone:modelData})}else digits.text+=modelData}
        onPressAndHold:if(modelData==="0"&&!win.calls.length)digits.text+="+"
       }
      }
     }
     Action {text:"+";Accessible.name:"International prefix";Layout.fillWidth:true;visible:!win.calls.length;onClicked:digits.text+="+"}
     Action {objectName:"dialCall";text:"Call";primary:true;Layout.fillWidth:true;visible:!win.calls.length;enabled:!!status.voice&&!Phone.busy&&digits.text.trim().length>0
      onClicked:{if(["112","999"].indexOf(digits.text.trim())>=0)emergency.open();else Phone.command("dial","",{number:digits.text})}
     }
     LabelText {Layout.fillWidth:true;font.pixelSize:12;text:Phone.state.emergencyWarning||"Emergency calling is unverified. Keep a known-working phone available.";color:"#8a531c"}
     Repeater {model:(Phone.state.contacts||[]).filter(c=>digits.text.length>1&&c.numbers.some(n=>n.indexOf(digits.text)>=0)).slice(0,4)
      delegate:Action {required property var modelData;text:modelData.name+" · "+modelData.numbers[0];Layout.fillWidth:true;onClicked:digits.text=modelData.numbers[0]}
     }
     Repeater {model:(Phone.state.history||[]).filter(c=>digits.text.length>1&&c.number.indexOf(digits.text)>=0).slice(0,3)
      delegate:Action {required property var modelData;text:"Recent · "+modelData.number;Layout.fillWidth:true;onClicked:digits.text=modelData.number}
     }
    }
   }
   ColumnLayout {spacing:8
    TextField {font.pixelSize:16;id:recentSearch;Layout.fillWidth:true;implicitHeight:48;placeholderText:"Search call history";selectByMouse:true}
    ComboBox {font.pixelSize:14;id:filter;Layout.fillWidth:true;implicitHeight:48;model:["All","Incoming","Outgoing","Missed","Rejected","Failed","Uncertain"]}
    ListView {id:recents;Layout.fillWidth:true;Layout.fillHeight:true;clip:true;spacing:8
     model:(Phone.state.history||[]).filter(c=>(filter.currentIndex===0||c.result===filter.currentText)&&(c.number+" "+c.name).toLowerCase().indexOf(recentSearch.text.toLowerCase())>=0)
     delegate:Rectangle {required property var modelData;width:recents.width;height:138;color:"white";radius:16
      ColumnLayout {anchors.fill:parent;anchors.margins:12
       LabelText {Layout.fillWidth:true;text:modelData.name||modelData.number||"Private caller";font.bold:true;font.pixelSize:19}
       LabelText {Layout.fillWidth:true;text:modelData.result+" · "+new Date(modelData.start*1000).toLocaleString()+" · "+modelData.duration+"s";font.pixelSize:12}
       RowLayout {Action {text:"Call back";onClicked:{digits.text=modelData.number;win.tab=0}}Action {text:"Save";onClicked:win.editContact({numbers:[modelData.number]})}Action {text:"Delete";onClicked:Phone.command("history-delete",modelData.id,{})}}
      }
     }
     LabelText {anchors.centerIn:parent;visible:recents.count===0;text:"No matching call events"}
    }
    Action {text:"Clear history…";Layout.fillWidth:true;onClicked:clearHistory.open()}
   }
   ColumnLayout {
    TextField {font.pixelSize:16;id:contactSearch;Layout.fillWidth:true;implicitHeight:48;placeholderText:"Search contacts";selectByMouse:true}
    ComboBox {font.pixelSize:14;id:contactFilter;Layout.fillWidth:true;implicitHeight:48;model:["All contacts","Favourites","Recent contacts"]}
    Action {text:"New contact";primary:true;Layout.fillWidth:true;onClicked:win.editContact({})}
    ListView {id:contacts;Layout.fillWidth:true;Layout.fillHeight:true;clip:true;spacing:8
     model:(Phone.state.contacts||[]).filter(c=>(contactFilter.currentIndex!==1||c.favourite)&&(contactFilter.currentIndex!==2||c.recent)&&(c.name+" "+c.numbers.join(" ")+" "+c.notes).toLowerCase().indexOf(contactSearch.text.toLowerCase())>=0).sort((a,b)=>contactFilter.currentIndex===2?(b.recent||0)-(a.recent||0):0)
     delegate:ItemDelegate {required property var modelData;width:contacts.width;height:76
      contentItem:Column {LabelText {text:(modelData.favourite?"★ ":"")+modelData.name;font.bold:true}LabelText {text:modelData.numbers.join(" · ");font.pixelSize:12;width:contacts.width-32;elide:Text.ElideRight;maximumLineCount:1}}
      onClicked:win.editContact(modelData)
     }
     LabelText {anchors.centerIn:parent;visible:contacts.count===0;text:"No contacts"}
    }
   }
   ScrollView {clip:true;contentWidth:availableWidth
    ColumnLayout {width:parent.width;spacing:12
     CallSettings {Layout.fillWidth:true;control:Phone}
     LabelText {text:"Contact import and backup";font.pixelSize:21;font.bold:true;Layout.fillWidth:true}
     TextField {font.pixelSize:16;id:vcardPath;Layout.fillWidth:true;implicitHeight:48;placeholderText:"Local .vcf file path";selectByMouse:true}
     Action {text:"Import vCard";Layout.fillWidth:true;enabled:!Phone.busy;onClicked:Phone.importVcard(vcardPath.text)}
     Action {text:"Export contacts privately";Layout.fillWidth:true;onClicked:Phone.exportFile("contacts")}
     Action {text:"Back up contact database";Layout.fillWidth:true;onClicked:Phone.command("backup-contacts","",{})}
     LabelText {text:"Diagnostics";font.pixelSize:21;font.bold:true;Layout.fillWidth:true}
     LabelText {Layout.fillWidth:true;text:"Modem: "+(status.modem?"Detected":"Unavailable")+"\nSIM ready: "+!!status.simReady+"\nRegistered: "+!!status.registered+"\nVoice control: "+!!status.voice+"\nIMS: "+(Phone.state.ims||"Unknown")+"\nVoLTE: "+(Phone.state.volte||"Unverified")+"\nCall audio: "+((Phone.state.audio||{}).error||"Unverified")+"\nIncoming wake: "+(Phone.state.incomingWake||"Not tested")+"\nRingtone: "+(Phone.state.ringtone||"Unverified")+"\nReal call and two-way audio: not verified"}
     Action {text:"Export redacted diagnostics";Layout.fillWidth:true;onClicked:Phone.exportFile("diagnostics")}
     Action {text:"Refresh backend";Layout.fillWidth:true;onClicked:Phone.refresh()}
    }
   }
  }
  RowLayout {Layout.fillWidth:true;spacing:6
   Repeater {model:["Dial","Recents","Contacts","Settings"];delegate:Action {required property string modelData;required property int index;text:modelData;labelSize:12;primary:win.tab===index;Layout.fillWidth:true;implicitWidth:0;onClicked:win.tab=index}}
  }
 }
 }
 function editContact(c){win.editing=c;contactName.text=c.name||"";contactNumbers.text=(c.numbers||[]).join(", ");contactEmails.text=(c.emails||[]).join(", ");contactNotes.text=c.notes||"";photo.text=c.photo||"";favourite.checked=!!c.favourite;contactDialog.open()}
 Dialog {font.pixelSize:16;id:contactDialog;objectName:"contactEditor";title:win.editing.id?"Edit contact":"New contact";modal:true;parent:Overlay.overlay;transformOrigin:Item.TopLeft;scale:win.unit;x:(win.width-width*scale)/2;y:Math.max(10,(win.height-height*scale)/2);width:Math.min(parent.width/win.unit-20,500);height:Math.min(parent.height/win.unit-20,710)
  contentItem:ScrollView {clip:true;contentWidth:availableWidth;ColumnLayout {width:parent.width;spacing:10
   TextField {font.pixelSize:16;id:contactName;Layout.fillWidth:true;implicitHeight:48;placeholderText:"Name";Accessible.name:"Contact name"}
   TextField {font.pixelSize:16;id:contactNumbers;Layout.fillWidth:true;implicitHeight:48;placeholderText:"Numbers, separated by commas";Accessible.name:"Contact numbers"}
   TextField {font.pixelSize:16;id:contactEmails;Layout.fillWidth:true;implicitHeight:48;placeholderText:"Email addresses, separated by commas";Accessible.name:"Email addresses"}
   TextField {font.pixelSize:16;id:photo;Layout.fillWidth:true;implicitHeight:48;placeholderText:"Photo: file:///…";Accessible.name:"Contact photo"}
   TextArea {font.pixelSize:15;id:contactNotes;Layout.fillWidth:true;implicitHeight:90;placeholderText:"Notes";wrapMode:TextEdit.Wrap}
   CheckBox {font.pixelSize:15;id:favourite;text:"Favourite";implicitHeight:48}
   Action {text:"Use number in dialer";Layout.fillWidth:true;onClicked:{digits.text=contactNumbers.text.split(",")[0].trim();win.tab=0;contactDialog.close()}}
   Action {text:"Save contact";primary:true;Layout.fillWidth:true;enabled:!Phone.busy&&contactName.text.trim().length>0;onClicked:{Phone.command("contact-save","",{id:win.editing.id||"",name:contactName.text,numbers:contactNumbers.text.split(",").map(n=>n.trim()).filter(n=>n.length),emails:contactEmails.text.split(",").map(n=>n.trim()).filter(n=>n.length),notes:contactNotes.text,photo:photo.text,favourite:favourite.checked});contactDialog.close()}}
   Action {text:"Delete contact";visible:!!win.editing.id;Layout.fillWidth:true;onClicked:{Phone.command("contact-delete",win.editing.id,{});contactDialog.close()}}
   Action {text:"Cancel";Layout.fillWidth:true;onClicked:contactDialog.close()}
  }}
 }
 Dialog {font.pixelSize:16;id:emergency;modal:true;title:"Emergency calling is unverified";anchors.centerIn:parent;transformOrigin:Item.Center;scale:win.unit;width:Math.min(parent.width/win.unit-24,480);height:280;standardButtons:Dialog.Yes|Dialog.Cancel
  contentItem:LabelText {text:(Phone.state.emergencyWarning||"Use a known-working phone.")+"\nAttempt "+digits.text+"? This places a real call request."}
  onAccepted:Phone.command("dial","",{number:digits.text,emergencyConfirmed:true})
 }
 Dialog {font.pixelSize:16;id:clearHistory;modal:true;title:"Delete all call history?";anchors.centerIn:parent;standardButtons:Dialog.Yes|Dialog.Cancel;onAccepted:Phone.command("history-clear","",{confirmed:true})}
}
