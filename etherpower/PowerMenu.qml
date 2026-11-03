import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import QtQuick.Window
import "../qml/settings" as S
Item {
 id:powerMenu;property real uiScale:1;property string action:"";property bool restoreHidden:false
 function open(){let window=powerMenu.Window.window;if(window){restoreHidden=!window.visible;window.showNormal();window.raise();window.requestActivate()}menu.open()}
 function close(){menu.close();confirmation.close()}
 S.SettingsTheme {id:theme;uiScale:powerMenu.uiScale}
 S.SettingsBottomSheet {id:menu;objectName:"etherPowerMenu";tokens:theme;title:"Power"
  onClosed:if(powerMenu.restoreHidden&&powerMenu.Window.window){powerMenu.Window.window.hide();powerMenu.restoreHidden=false}
  contentItem:ColumnLayout {
   S.SettingsStatus {tokens:theme;Layout.fillWidth:true;text:(Power.state.capacity===undefined?"Unavailable":Power.state.capacity+"%")+" · "+(Power.state.status||"Power state unavailable")}
   S.SettingsAction {tokens:theme;Layout.fillWidth:true;text:"Blank screen";onClicked:{menu.close();Power.screenOff()}}
   S.SettingsAction {tokens:theme;Layout.fillWidth:true;text:"Suspend";enabled:!!(Power.state.suspend||{}).verified&&!Power.busy;onClicked:{menu.close();Power.powerAction("suspend")}}
   S.SettingsStatus {tokens:theme;Layout.fillWidth:true;text:(Power.state.suspend||{}).error||"Verified sleep uses existing logind inhibitors"}
   S.SettingsAction {tokens:theme;Layout.fillWidth:true;text:"Restart…";onClicked:{powerMenu.action="restart";confirmation.open()}}
   S.SettingsAction {tokens:theme;Layout.fillWidth:true;text:"Shut down…";destructive:true;onClicked:{powerMenu.action="shutdown";confirmation.open()}}
  }
  footer:S.SettingsAction {tokens:theme;text:"Cancel";onClicked:menu.close()}
 }
 S.SettingsDialog {id:confirmation;tokens:theme;title:powerMenu.action==="shutdown"?"Shut down EtherPocket?":"Restart EtherPocket?"
  implicitHeight:260;height:Math.min(implicitHeight,parent.height/scale-24)
  contentItem:S.SettingsStatus {tokens:theme;text:"Save your work. This uses systemd-logind and requires administrator authentication. Existing blocking inhibitors are respected."}
  footer:RowLayout {
   S.SettingsAction {tokens:theme;Layout.fillWidth:true;text:"Cancel";onClicked:confirmation.close()}
   S.SettingsAction {tokens:theme;Layout.fillWidth:true;text:"Confirm";destructive:true;onClicked:{confirmation.close();menu.close();Power.powerAction(powerMenu.action)}}
  }
 }
 Connections {target:Power;function onPowerMenuRequested(){powerMenu.open()}}
}
