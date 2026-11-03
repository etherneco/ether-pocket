import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import QtQuick.Window
Window {
 id:bannerWindow
 required property var host
 property var control:Notifications
 property var card:control.banner
 transientParent:null
 title:"EtherNotifications · Banner"
 visible:!!card.id&&!control.state.locked
 flags:Qt.Window|Qt.FramelessWindowHint|Qt.WindowStaysOnTopHint|Qt.WindowDoesNotAcceptFocus
 x:host.screen.virtualX+((host.notificationScreenWidth||host.screen.width)-width)/2
 y:host.screen.virtualY+host.notificationSafeTop+8*host.unit
 width:Math.min((host.notificationScreenWidth||host.screen.width)-24*host.unit,480*host.unit)
 height:Math.min((content.implicitHeight+24)*host.unit,host.screen.height-host.notificationSafeTop-120*host.unit)
 color:"transparent"
 Component.onCompleted:Core.configureWindow(bannerWindow,"dock",0)
 Rectangle {anchors.fill:parent;radius:16;color:"#f8fbff";border.color:"#a8bdd6"}
 Item {width:parent.width/host.unit;height:parent.height/host.unit;scale:host.unit;transformOrigin:Item.TopLeft
 SwipeDelegate {anchors.fill:parent;padding:12;font.pixelSize:14;background:Item {}
  contentItem:ColumnLayout {id:content;spacing:6
   RowLayout {Layout.fillWidth:true
    Label {text:(bannerWindow.card.appName||"")+" · "+(bannerWindow.card.title||"");textFormat:Text.PlainText;elide:Text.ElideRight;font.bold:true;Layout.fillWidth:true}
    ToolButton {text:"×";onClicked:bannerWindow.control.nextBanner()}
   }
   Label {text:bannerWindow.card.body||"";textFormat:Text.PlainText;wrapMode:Text.Wrap;maximumLineCount:3;elide:Text.ElideRight;Layout.fillWidth:true}
   Flow {Layout.fillWidth:true;spacing:4
    Repeater {model:bannerWindow.card.actions||[];delegate:Button {required property var modelData;text:modelData.label;onClicked:{bannerWindow.control.command("invoke",bannerWindow.card.id,{key:modelData.key});bannerWindow.control.nextBanner()}}}
   }
  }
  onClicked:{if((bannerWindow.card.actions||[]).some(a=>a.key==="default"))bannerWindow.control.command("invoke",bannerWindow.card.id,{key:"default"});else bannerWindow.host.home("notices");bannerWindow.control.nextBanner()}
  swipe.right:Rectangle {width:bannerWindow.width;height:bannerWindow.height;color:"#e7edf5";Label {anchors.centerIn:parent;text:"Dismiss"}}
  swipe.onCompleted:{bannerWindow.control.command("dismiss",bannerWindow.card.id);bannerWindow.control.nextBanner();swipe.close()}
 }
 }
}
