import "../qml" as UI
import QtQuick
import QtQuick.Layouts
import "../qml/settings" as S

ColumnLayout {
 id:page;objectName:"etherSensorsPage";required property var tokens
 readonly property var state:SensorControl.state||({})
 readonly property var config:state.config||({})
 spacing:tokens.sectionGap
 component Card:S.SettingsSection {tokens:page.tokens;Layout.fillWidth:true}
 component Row:S.SettingsRow {tokens:page.tokens;Layout.fillWidth:true;arrow:false}
 component Action:S.SettingsAction {tokens:page.tokens;Layout.fillWidth:true}
 component Status:S.SettingsStatus {tokens:page.tokens;Layout.fillWidth:true}
 Component.onDestruction:SensorControl.stopTest()
 Status {visible:!page.state.ready;state:"warning";text:"EtherSensors service unavailable"}
 Status {visible:!!SensorControl.message;text:SensorControl.message}
 Card {
  Row {title:"Sensors";description:"Availability comes from native driver discovery. Physical response requires a real device test."}
  Action {text:"Refresh sensor status";onClicked:SensorControl.refresh()}
  Repeater {model:page.state.sensors||[];delegate:ColumnLayout {
   required property var modelData
   Layout.fillWidth:true
   Row {title:(modelData.name||modelData.type)+" · "+modelData.status;description:(modelData.physicalPresence||(modelData.physical?"Physical interface":"Derived"))+" · "+(modelData.units||"Units unverified")+"\n"+(modelData.reason||"")+"\nDriver: "+(modelData.driver||"Unknown")+" · Calibration: "+(modelData.calibration||"Unknown")}
   Action {text:"Test for 30 seconds";visible:!!modelData.measurementAvailable;onClicked:SensorControl.test(modelData.id)}
  }}
  UI.DataView {tokens:page.tokens;Layout.fillWidth:true;visible:Object.keys(SensorControl.sample||{}).length>0;value:SensorControl.sample}
  Action {text:"Stop sensor test";visible:page.state.activeSubscriptions>0;onClicked:SensorControl.stopTest()}
 }
 Card {
  Row {title:"Display & Motion";description:"Rotation lock is active. Auto rotation, raise to wake, gestures and phone-motion controls await validated motion sensors."}
  S.SettingsToggle {tokens:page.tokens;Layout.fillWidth:true;title:"Rotation lock";checked:page.config.rotationLock!==false;enabled:false}
  Row {title:"Brightness and calls";description:"Automatic brightness and proximity blanking are unavailable until real light and near/far readings are validated."}
 }
 Card {
  Row {title:"Calibration";description:"Accelerometer, gyroscope and compass calibration require validated inputs. Factory calibration remains unchanged."}
 }
 Card {
  Row {title:"Privacy";description:"Application access expires after five minutes. Background access requires explicit approval. Sensor history is disabled."}
  Action {text:"Review application access";onClicked:SensorControl.review()}
  Repeater {model:SensorControl.management.requests||[];delegate:ColumnLayout {
   required property var modelData;Layout.fillWidth:true
   Row {title:modelData.app;description:modelData.rate+" Hz polling · "+(modelData.background?"Background requested":"Foreground only")}
   Action {text:"Allow this session";onClicked:SensorControl.resolve(modelData.owner,true)}
   Action {text:"Deny";onClicked:SensorControl.resolve(modelData.owner,false)}
  }}
  Repeater {model:SensorControl.management.grants||[];delegate:Action {
   required property var modelData;text:"Revoke "+modelData.owner;onClicked:SensorControl.revoke(modelData.owner)
  }}
  Row {title:"Sensor activity";description:(page.state.activeSubscriptions||0)+" subscriptions · "+(page.state.profile||"Unknown")}
 }
 Card {
  Row {title:"Advanced diagnostics";description:"Sampling frequencies are unverified. Managed polling is limited to 10 Hz; Battery Saver caps it at 1 Hz. Fusion is blocked until real inputs are validated."}
  Action {text:"Show redacted diagnostic export";onClicked:SensorControl.diagnostics()}
 }
}
