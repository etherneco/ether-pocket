import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import "../ethernotifications" as N
ApplicationWindow {
 id:root;visible:true;width:360;height:900;color:"#f6f8fc"
 property bool settingsMode:false
 property real unit:1
 property real notificationSafeTop:0
 property real notificationScreenWidth:width
 function home(destination){}
 Item {width:root.width/root.unit;height:root.height/root.unit;scale:root.unit;transformOrigin:Item.TopLeft
 N.NotificationCenter {anchors.fill:parent;visible:!root.settingsMode}
 ScrollView {id:settingsScroll;anchors.fill:parent;anchors.margins:12;visible:root.settingsMode;contentWidth:availableWidth;clip:true
  N.NotificationSettings {width:settingsScroll.availableWidth}
 }
 }
 QtObject {id:bannerHost;property var screen:({virtualX:0,virtualY:0,width:root.width,height:root.height});property real unit:root.unit;property real notificationSafeTop:0;function home(destination){}}
 N.NotificationBanner {host:bannerHost;objectName:"notificationBanner";visible:root.bannerMode}
 property bool bannerMode:false
}
