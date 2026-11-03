import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import QtQuick.Window
ApplicationWindow {
 id:win;visible:true;width:460;height:850;minimumWidth:340;minimumHeight:480;title:"EtherSMS";color:"#f1f7ff"
 property bool desktop:!PocketDisplay && width>=900
 property bool conversationOpen:false
 property bool contactsMode:false
 property bool unreadOnly:false
 property var selected:({})
 property var selectedIds:[]
 property string pendingNumber:""
 property var prefs:SmsSettings.values
 readonly property color ink:"#122c50"
 readonly property color muted:"#617b9c"
 readonly property color blue:"#087dff"
 readonly property bool canSend:Sms.validRecipient(Sms.number)&&Sms.draft.trim().length>0&&Sms.estimate(Sms.draft).segments<=10&&!!SmsTransport.capabilities.canSend
 onActiveChanged:Sms.setVisible(active)
 Component.onCompleted:Sms.setVisible(active)
 component LabelText:Text {color:win.ink;font.pixelSize:15;wrapMode:Text.WordWrap;textFormat:Text.PlainText}
 component Action:Button {
  id:button;property bool primary:false
  implicitHeight:Math.max(48,contentItem.implicitHeight+24);implicitWidth:Math.max(48,contentItem.implicitWidth+28);font.pixelSize:15;padding:12;focusPolicy:Qt.StrongFocus
  contentItem:Text {text:button.text;color:button.primary?"white":win.ink;font:button.font;horizontalAlignment:Text.AlignHCenter;verticalAlignment:Text.AlignVCenter;elide:Text.ElideRight}
  background:Rectangle {radius:16;color:button.primary?win.blue:button.down?"#deebfc":"#f8fbff";border.color:button.primary?win.blue:"#d8e8fa";opacity:button.enabled?1:.45}
  Accessible.name:text
 }
 background:Rectangle {gradient:Gradient {GradientStop {position:0;color:"#f8fcff"}GradientStop {position:1;color:"#e9f4ff"}}}
 header:Rectangle {
  height:82;color:"#ffffff"
  RowLayout {anchors.fill:parent;anchors.margins:18;spacing:12
   Image {source:"qrc:/ethersms.svg";Layout.preferredWidth:40;Layout.preferredHeight:40}
   ColumnLayout {spacing:3;Layout.fillWidth:true
    LabelText {text:"EtherSMS";font.pixelSize:27;font.bold:true}
    LabelText {text:"Wiadomości · Dyktowanie · Lokalna AI";font.pixelSize:12;color:win.muted}
   }
   Action {text:"⚙";Accessible.name:"SMS & Messaging Settings";onClicked:Sms.openSettings()}
  }
 }
 ColumnLayout {anchors.fill:parent;spacing:0
  Rectangle {Layout.fillWidth:true;implicitHeight:statusLabel.implicitHeight+16;color:SmsTransport.capabilities.canSend?"#e7f5ef":"#fff2dc"
   LabelText {id:statusLabel;anchors.fill:parent;anchors.margins:8;horizontalAlignment:Text.AlignHCenter;font.pixelSize:12;text:SmsTransport.capabilities.canSend?"EtherMobile · "+SmsTransport.capabilities.network+" · SMS":"SMS unavailable · "+(SmsTransport.capabilities.network||"Checking modem…")}
  }
  RowLayout {Layout.fillWidth:true;Layout.fillHeight:true;spacing:0
   Rectangle {Layout.preferredWidth:win.desktop?340:0;Layout.fillWidth:!win.desktop;Layout.fillHeight:true;visible:win.desktop||!win.conversationOpen;color:"transparent"
    ColumnLayout {anchors.fill:parent;anchors.margins:14;spacing:12
     TextField {Layout.fillWidth:true;implicitHeight:46;placeholderText:"Szukaj wiadomości lub kontaktu";selectByMouse:true;onTextEdited:Sms.search(text);color:win.ink;background:Rectangle {color:"white";radius:16;border.color:"#d8e8fa"}}
     RowLayout {Layout.fillWidth:true
      Action {text:"Wszystkie";primary:!win.contactsMode&&!win.unreadOnly;Layout.fillWidth:true;onClicked:{win.contactsMode=false;win.unreadOnly=false}}
      Action {text:"Nieprzeczytane";primary:win.unreadOnly;Layout.fillWidth:true;onClicked:{win.contactsMode=false;win.unreadOnly=!win.unreadOnly}}
      Action {text:"Kontakty";primary:win.contactsMode;Layout.fillWidth:true;onClicked:win.contactsMode=!win.contactsMode}
     }
     ListView {id:threads;Layout.fillWidth:true;Layout.fillHeight:true;clip:true;spacing:2;model:win.contactsMode?Sms.contacts:Sms.conversations
      ScrollBar.vertical:ScrollBar {}
      delegate:ItemDelegate {
       required property var modelData;width:threads.width;height:win.unreadOnly&&!modelData.unread?0:90;visible:height>0
       background:Rectangle {radius:18;color:parent.down?"#deebfc":"#ffffff";border.color:Sms.number===modelData.number&&win.conversationOpen?"#b4d6ff":"#f0f6ff"}
       contentItem:RowLayout {spacing:12
        Rectangle {Layout.preferredWidth:48;Layout.preferredHeight:48;radius:24;gradient:Gradient {GradientStop {position:0;color:"#8dc7ff"}GradientStop {position:1;color:"#258aff"}}
LabelText {anchors.centerIn:parent;text:(modelData.name||modelData.number||"?").charAt(0).toUpperCase();font.pixelSize:25;color:"white"}}
        ColumnLayout {Layout.fillWidth:true;spacing:4
         LabelText {text:modelData.name||modelData.number;font.pixelSize:17;font.bold:true;Layout.fillWidth:true;maximumLineCount:1;elide:Text.ElideRight}
         LabelText {text:win.contactsMode?modelData.number:modelData.body||"";Layout.fillWidth:true;color:win.muted;font.pixelSize:13;maximumLineCount:1;elide:Text.ElideRight}
        }
        ColumnLayout {
         LabelText {text:win.contactsMode?"":Qt.formatDateTime(new Date(modelData.timestamp),"dd.MM hh:mm");font.pixelSize:10;color:win.muted}
         LabelText {text:modelData.unread?String(modelData.unread):modelData.state==="Uncertain"||modelData.state==="Failed"?"!":"›";font.bold:true;color:win.blue;Layout.alignment:Qt.AlignRight}
        }
       }
       onClicked:{Sms.open(modelData.number);win.conversationOpen=true}
       onPressAndHold:if(win.contactsMode){contactNumber.text=modelData.number;contactName.text=modelData.name;contactDialog.open()}
      }
      LabelText {anchors.centerIn:parent;width:parent.width-30;horizontalAlignment:Text.AlignHCenter;visible:threads.count===0;text:win.contactsMode?"Brak kontaktów\nDodaj pierwszy kontakt.":"Twoje wiadomości\nRozpocznij rozmowę. Historia zostanie zapisana na tym urządzeniu.";color:win.muted;font.pixelSize:16}
     }
     Action {text:win.contactsMode?"＋ Dodaj kontakt":"＋ Nowa wiadomość";primary:true;Layout.fillWidth:true;onClicked:if(win.contactsMode){contactNumber.text="";contactName.text="";contactDialog.open()}else{recipient.text="";newMessage.open()}}
     RowLayout {Layout.fillWidth:true
      LabelText {text:Sms.unread+" nieprzeczytanych";font.pixelSize:11;color:win.muted;Layout.fillWidth:true}
      Action {text:"Kopia";onClicked:backupDialog.open()}
     }
    }
   }
   Rectangle {visible:win.desktop;Layout.preferredWidth:1;Layout.fillHeight:true;color:"#d8e8fa"}
   Item {Layout.fillWidth:true;Layout.fillHeight:true;visible:win.desktop||win.conversationOpen
    ColumnLayout {anchors.fill:parent;anchors.margins:win.desktop?24:12;spacing:10
     RowLayout {Layout.fillWidth:true
      Action {text:"‹";visible:!win.desktop;Accessible.name:"Back to conversations";onClicked:{win.conversationOpen=false;Sms.open("")}}
      ColumnLayout {Layout.fillWidth:true
       LabelText {text:(Sms.contacts.find(c=>c.number===Sms.number)||{}).name||Sms.number||"Wybierz rozmowę";font.pixelSize:20;font.bold:true;Layout.fillWidth:true}
       LabelText {text:Sms.number?"SMS · "+Sms.number:"Wiadomości zostają na Twoim urządzeniu";font.pixelSize:12;color:win.muted}
      }
      Action {text:"⋮";Accessible.name:"Conversation actions";onClicked:conversationMenu.open()}
     }
     TextField {Layout.fillWidth:true;visible:win.conversationOpen;placeholderText:"Szukaj w rozmowie";implicitHeight:48;onTextEdited:Sms.searchMessages(text)}
     RowLayout {visible:win.selectedIds.length>0;Layout.fillWidth:true
      LabelText {text:win.selectedIds.length+" selected";Layout.fillWidth:true}
      Action {text:"Usuń";onClicked:deleteSelected.open()}
      Action {text:"Anuluj";onClicked:win.selectedIds=[]}
     }
     RowLayout {Layout.fillWidth:true;visible:Sms.hasOlder||Sms.hasNewer
      Action {text:"↑ Starsze";enabled:Sms.hasOlder;onClicked:Sms.older()}
      Action {text:"↓ Nowsze";enabled:Sms.hasNewer;onClicked:Sms.newer()}
     }
     ListView {id:bubbles;Layout.fillWidth:true;Layout.fillHeight:true;clip:true;spacing:12;model:Sms.messages;verticalLayoutDirection:ListView.TopToBottom;onCountChanged:Qt.callLater(()=>positionViewAtEnd());ScrollBar.vertical:ScrollBar {}
      delegate:Column {
       id:bubbleRow;required property var modelData;required property int index;width:bubbles.width;spacing:8
       property bool outgoing:modelData.direction==="out"
       LabelText {width:parent.width;horizontalAlignment:Text.AlignHCenter;font.pixelSize:11;color:win.muted;text:Qt.formatDateTime(new Date(modelData.timestamp),"dddd, dd MMMM");visible:index===0||String(Sms.messages[index-1].timestamp).slice(0,10)!==String(modelData.timestamp).slice(0,10)}
       Rectangle {width:Math.min(parent.width*.86,Math.max(130,messageText.implicitWidth+32));height:messageText.implicitHeight+meta.implicitHeight+34;x:bubbleRow.outgoing?parent.width-width:0;radius:20;color:bubbleRow.outgoing?"#268cff":"#e8eef6";border.width:win.selectedIds.indexOf(modelData.id)>=0?2:0;border.color:win.ink
        Column {anchors.fill:parent;anchors.margins:14;spacing:8
         LabelText {id:messageText;width:parent.width;text:modelData.body;font.pixelSize:16;color:bubbleRow.outgoing?"white":win.ink}
         LabelText {id:meta;width:parent.width;text:Qt.formatDateTime(new Date(modelData.timestamp),"hh:mm")+(bubbleRow.outgoing?" · "+modelData.state:"");font.pixelSize:10;color:bubbleRow.outgoing?"#e6f2ff":win.muted;horizontalAlignment:Text.AlignRight}
        }
        MouseArea {anchors.fill:parent;onPressAndHold:{win.selected=modelData;messageMenu.open()}onClicked:if(win.selectedIds.length){let ids=win.selectedIds.slice();let i=ids.indexOf(modelData.id);if(i<0)ids.push(modelData.id);else ids.splice(i,1);win.selectedIds=ids}}
       }
       LabelText {visible:!!modelData.error;text:modelData.error;width:parent.width;color:"#b52e49";font.pixelSize:11}
      }
      LabelText {anchors.centerIn:parent;width:parent.width-24;horizontalAlignment:Text.AlignHCenter;visible:bubbles.count===0;text:Sms.number?"Napisz pierwszą wiadomość":"Wybierz rozmowę lub utwórz nową wiadomość";color:win.muted}
     }
     Action {visible:!bubbles.atYEnd&&bubbles.count>0;text:"↓ Najnowsze";Layout.alignment:Qt.AlignHCenter;onClicked:bubbles.positionViewAtEnd()}
     LabelText {visible:Speech.state!=="Ready";text:Speech.state;Layout.fillWidth:true;color:Speech.state==="Recording"?"#b52e49":win.muted;font.pixelSize:12}
     ProgressBar {visible:Speech.state==="Recording";Layout.fillWidth:true;from:0;to:1;value:Math.min(1,Speech.level*5)}
     RowLayout {visible:Speech.state==="Recording"||Speech.state==="Processing";Layout.fillWidth:true
      Action {text:"Stop";visible:Speech.state==="Recording";onClicked:Speech.stop()}
      Action {text:"Anuluj";onClicked:Speech.cancel()}
     }
     Rectangle {Layout.fillWidth:true;implicitHeight:composerRow.implicitHeight+18;radius:26;color:"white";border.color:"#d8e8fa";visible:!!Sms.number
      RowLayout {id:composerRow;anchors.fill:parent;anchors.margins:9;spacing:8
       Action {text:Speech.state==="Recording"?"■":"●";Accessible.name:"Record offline dictation";enabled:!!win.prefs.dictation&&Speech.state!=="Processing";onClicked:if(Speech.state==="Recording")Speech.stop();else Speech.start(win.prefs.language,win.prefs.speechModel,win.prefs.microphone)}
       ScrollView {Layout.fillWidth:true;Layout.preferredHeight:Math.min(130,Math.max(46,composer.implicitHeight));clip:true
        TextArea {id:composer;objectName:"messageComposer";placeholderText:"Napisz lub podyktuj wiadomość…";text:Sms.draft;wrapMode:TextEdit.Wrap;selectByMouse:true;color:win.ink;font.pixelSize:16;onTextChanged:if(text!==Sms.draft)Sms.draft=text;onActiveFocusChanged:if(activeFocus)Sms.keyboard();background:Rectangle {color:"transparent"}}
       }
       Action {text:win.prefs.language.toUpperCase();Accessible.name:"Dictation language";onClicked:languageMenu.open()}
       Action {objectName:"sendButton";text:"➤";primary:true;Accessible.name:"Send message";enabled:win.canSend;onClicked:if(win.prefs.confirmSend)sendConfirm.open();else Sms.send()}
      }
     }
     RowLayout {visible:!!Sms.number;Layout.fillWidth:true
      Action {text:Sms.aiBusy?"Przetwarzanie…":"✧ Korekta AI";enabled:!!win.prefs.aiEnabled&&!Sms.aiBusy&&Sms.draft.trim().length>0;onClicked:aiMenu.open()}
      LabelText {text:Sms.estimate(Sms.draft).units+" · "+Sms.estimate(Sms.draft).segments+" SMS · "+Sms.estimate(Sms.draft).encoding;Layout.fillWidth:true;horizontalAlignment:Text.AlignRight;color:win.muted;font.pixelSize:10}
     }
    }
   }
  }
  LabelText {Layout.fillWidth:true;Layout.margins:8;visible:!!Sms.error;text:Sms.error;color:"#b52e49";font.pixelSize:12}
 }
 Menu {id:languageMenu;MenuItem {text:"Polski";onTriggered:SmsSettings.set("language","pl")}MenuItem {text:"English";onTriggered:SmsSettings.set("language","en")}MenuItem {text:"Automatic";onTriggered:SmsSettings.set("language","auto")}}
 Menu {id:aiMenu;Repeater {model:[{id:"correct",label:"Correct spelling & punctuation"},{id:"shorten",label:"Shorten"},{id:"formal",label:"More formal"},{id:"friendly",label:"More friendly"},{id:"translate",label:"Translate PL ↔ EN"},{id:"summarize",label:"Summarize"}];delegate:MenuItem {required property var modelData;text:modelData.label;onTriggered:Sms.correct(modelData.id)}}}
 Menu {id:conversationMenu;MenuItem {text:"Add / edit contact";enabled:Sms.validRecipient(Sms.number);onTriggered:{contactNumber.text=Sms.number;contactName.text=(Sms.contacts.find(c=>c.number===Sms.number)||{}).name||"";contactDialog.open()}}MenuItem {text:"Stop playback";onTriggered:Sms.stopPlayback()}MenuItem {text:"SMS & Messaging Settings";onTriggered:Sms.openSettings()}}
 Menu {id:messageMenu;MenuItem {text:"Retry failed message as draft";enabled:win.selected.state==="Failed";onTriggered:Sms.retry(win.selected.id)}MenuItem {text:"Copy";onTriggered:Sms.copy(win.selected.body)}MenuItem {text:"Read aloud";enabled:!!win.prefs.ttsEnabled;onTriggered:Sms.speak(win.selected.body)}MenuItem {text:"Select";onTriggered:win.selectedIds=[win.selected.id]}MenuItem {text:"Delete";onTriggered:{win.selectedIds=[win.selected.id];deleteSelected.open()}}}
 Dialog {id:deleteSelected;anchors.centerIn:parent;modal:true;title:"Delete selected messages?";standardButtons:Dialog.Ok|Dialog.Cancel;onAccepted:{for(let id of win.selectedIds)Sms.remove(id);win.selectedIds=[]}}
 Dialog {id:newMessage;anchors.centerIn:parent;modal:true;width:Math.min(win.width-32,380);title:"Nowa wiadomość";standardButtons:Dialog.Ok|Dialog.Cancel
  TextField {id:recipient;width:parent.width;placeholderText:"Numer telefonu, np. +48…";inputMethodHints:Qt.ImhDialableCharactersOnly;onAccepted:if(Sms.validRecipient(text))newMessage.accept()}
  onAccepted:if(Sms.validRecipient(recipient.text)){Sms.open(recipient.text);win.conversationOpen=true}else newMessage.open()
 }
 Dialog {id:sendConfirm;anchors.centerIn:parent;modal:true;width:Math.min(win.width-32,390);title:"Wyślij SMS?";standardButtons:Dialog.Ok|Dialog.Cancel;LabelText {width:parent.width;text:"Do: "+Sms.number+"\n"+Sms.estimate(Sms.draft).segments+" SMS. Operator może naliczyć opłatę."}onAccepted:Sms.send()}
 Dialog {id:contactDialog;anchors.centerIn:parent;modal:true;width:Math.min(win.width-32,380);title:"Kontakt";standardButtons:Dialog.Save|Dialog.Cancel
  ColumnLayout {width:parent.width;TextField {id:contactName;Layout.fillWidth:true;placeholderText:"Imię i nazwisko"}TextField {id:contactNumber;Layout.fillWidth:true;placeholderText:"Numer telefonu"}Action {text:"Usuń kontakt";onClicked:deleteContact.open()}}
  onAccepted:Sms.saveContact(contactNumber.text,contactName.text)
 }
 Dialog {id:deleteContact;anchors.centerIn:parent;modal:true;title:"Delete this contact?";standardButtons:Dialog.Ok|Dialog.Cancel;onAccepted:{Sms.deleteContact(contactNumber.text);contactDialog.close()}}
 Dialog {id:backupDialog;anchors.centerIn:parent;modal:true;width:Math.min(win.width-32,380);title:"Private SQLite backup";standardButtons:Dialog.Save|Dialog.Cancel;TextField {id:backupPath;width:parent.width;placeholderText:"New absolute path, e.g. /home/mobian/sms-backup.sqlite"}onAccepted:Sms.backup(backupPath.text)}
 Dialog {id:proposalDialog;anchors.centerIn:parent;modal:true;width:Math.min(win.width-32,600);title:"Review AI suggestion";standardButtons:Dialog.Apply|Dialog.Cancel
  ScrollView {width:parent.width;implicitHeight:Math.min(400,win.height*.5);Column {width:parent.width;spacing:14;LabelText {width:parent.width;text:"Original\n"+Sms.draft}LabelText {width:parent.width;text:"Proposed\n"+Sms.proposal}}}
  onApplied:{Sms.accept();close()}onRejected:Sms.reject()
 }
 Connections {target:Sms;function onProposalChanged(){if(Sms.proposal.length)proposalDialog.open()}function onDraftChanged(){if(composer.text!==Sms.draft)composer.text=Sms.draft}}
}
