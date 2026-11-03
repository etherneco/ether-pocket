import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
Control {
 id:panel
 font.pixelSize:14
 property var control: Notifications
 property bool history:false
 property var collapsed: ({})
 property var cards: control.state.cards||[]
 property var filtered: cards.filter(c=>(history||c.active)&&(!query.text.length||(c.title+" "+c.body+" "+c.appName).toLowerCase().indexOf(query.text.toLowerCase())>=0)&&(app.currentIndex===0||c.appId===app.currentText)&&(priority.currentIndex===0||c.priority===priority.currentIndex-1))
 property var groups: {
  let result=[],lookup={};for(let c of filtered){let key=c.groupKey;if(!lookup[key]){lookup[key]={key:key,name:c.appName,appId:c.appId,rows:[],unread:0};result.push(lookup[key])}lookup[key].rows.push(c);if(c.active&&!c.read)lookup[key].unread++}return result
 }
 ColumnLayout {anchors.fill:parent;anchors.margins:12;spacing:8
  RowLayout {Layout.fillWidth:true
   Label {text:"Notifications · "+(panel.control.state.unread||0);font.pixelSize:18;font.bold:true;Layout.fillWidth:true;elide:Text.ElideRight}
   ToolButton {text:panel.history?"Current":"History";onClicked:panel.history=!panel.history}
  }
  TextField {id:query;Layout.fillWidth:true;placeholderText:"Search notifications";selectByMouse:true}
  RowLayout {Layout.fillWidth:true
   ComboBox {id:app;Layout.fillWidth:true;model:["All apps"].concat([...new Set(panel.cards.map(c=>c.appId))]);displayText:currentIndex===0?"All apps":currentText.split("-")[0]}
   ComboBox {id:priority;Layout.fillWidth:true;model:["All priorities","Low","Normal","High","Critical"]}
  }
  RowLayout {Layout.fillWidth:true
   Button {text:"Clear";enabled:!panel.control.state.locked;onClicked:panel.control.command("clear")}
   Button {text:"Delete history";visible:panel.history;enabled:!panel.control.state.locked;onClicked:panel.control.command("delete-history")}
   Button {text:"Export";visible:panel.history;enabled:!panel.control.state.locked;onClicked:panel.control.command("export")}
  }
  Label {visible:!panel.control.state.ready;text:"Notification service unavailable";wrapMode:Text.Wrap;Layout.fillWidth:true}
  Label {visible:panel.control.state.ready&&!panel.groups.length;text:panel.history?"No notification history":"You're all caught up";Layout.fillWidth:true;horizontalAlignment:Text.AlignHCenter}
  ListView {id:list;Layout.fillWidth:true;Layout.fillHeight:true;clip:true;spacing:10;model:panel.groups
   delegate:Column {id:group;required property var modelData;width:list.width;spacing:6
    Button {width:parent.width;text:(panel.collapsed[group.modelData.key]?"▸ ":"▾ ")+group.modelData.name+" · "+group.modelData.rows.length+" · "+group.modelData.unread+" unread";onClicked:{let x=Object.assign({},panel.collapsed);x[group.modelData.key]=!x[group.modelData.key];panel.collapsed=x}}
    Repeater {model:panel.collapsed[group.modelData.key]?[]:group.modelData.rows
     delegate:SwipeDelegate {id:card;required property var modelData;width:group.width;padding:12
      background:Rectangle {color:card.modelData.read?"#f5f7fa":"#eaf1ff";radius:14;border.color:"#dce3ec"}
      contentItem:ColumnLayout {spacing:5
       RowLayout {Layout.fillWidth:true
        Image {source:"image://icons/"+card.modelData.icon;sourceSize:Qt.size(24,24);Layout.preferredWidth:24;Layout.preferredHeight:24}
        Label {text:card.modelData.title;textFormat:Text.PlainText;font.bold:!card.modelData.read;wrapMode:Text.Wrap;Layout.fillWidth:true}
       }
       Label {text:card.modelData.body;textFormat:Text.PlainText;wrapMode:Text.Wrap;Layout.fillWidth:true;visible:text.length>0}
       Label {text:Qt.formatDateTime(new Date(card.modelData.timestamp*1000),"ddd HH:mm")+(card.modelData.persistent?" · Persistent":"");font.pixelSize:11;color:"#606f80"}
       Flow {Layout.fillWidth:true;spacing:4;visible:!panel.control.state.locked
        Repeater {model:card.modelData.active?card.modelData.actions:[];delegate:Button {required property var modelData;text:modelData.label;onClicked:panel.control.command("invoke",card.modelData.id,{key:modelData.key})}}
        Button {text:card.modelData.active?"Read":"Restore";onClicked:panel.control.command(card.modelData.active?"read":"restore",card.modelData.id)}
        Button {text:"Dismiss";visible:card.modelData.active;onClicked:panel.control.command("dismiss",card.modelData.id)}
       }
      }
      onClicked:if(!panel.control.state.locked){if(card.modelData.actions.some(a=>a.key==="default"))panel.control.command("invoke",modelData.id,{key:"default"});else panel.control.command("read",modelData.id)}
      swipe.right:Rectangle {width:card.width;height:card.height;color:"#dce6f5";Label {anchors.centerIn:parent;text:"Dismiss"}}
      swipe.onCompleted:{if(!panel.control.state.locked)panel.control.command("dismiss",modelData.id);swipe.close()}
     }
    }
   }
  }
  Label {text:panel.control.message;visible:text.length>0;wrapMode:Text.Wrap;Layout.fillWidth:true;font.pixelSize:12}
 }
}
