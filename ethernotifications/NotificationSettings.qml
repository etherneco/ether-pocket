import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
ColumnLayout {
 id:page
 property var control: Notifications
 property var config:control.state.config||{}
 property var apps:[...new Set((control.state.cards||[]).map(c=>c.appId))].concat(Object.keys(config.apps||{})).filter((v,i,a)=>a.indexOf(v)===i)
 Layout.minimumWidth:0
 spacing:8
 component SettingSwitch:Switch {
  id:toggle
  font.pixelSize:14
  Layout.fillWidth:true
  Layout.minimumWidth:0
  implicitHeight:Math.max(48,contentItem.implicitHeight+topPadding+bottomPadding)
  contentItem:Text {text:toggle.text;leftPadding:toggle.indicator.width+toggle.spacing;verticalAlignment:Text.AlignVCenter;wrapMode:Text.Wrap;font:toggle.font;color:"#182638"}
 }
 component SettingLabel:Label {font.pixelSize:14}
 SettingLabel {text:"Notifications";font.pixelSize:18;font.bold:true}
 SettingLabel {text:control.state.ready?"One delivery policy for Settings and Quick Settings":"Notification service unavailable";wrapMode:Text.Wrap;Layout.fillWidth:true}
 SettingSwitch {text:"Enable notifications";checked:!!page.config.enabled;onClicked:page.control.configure({enabled:checked})}
 SettingSwitch {text:"Silent mode";checked:!!page.config.silent;onClicked:page.control.configure({silent:checked})}
 ComboBox {font.pixelSize:14;Layout.fillWidth:true;Layout.minimumWidth:0;implicitWidth:240;model:["DND off","Priority only","Alarms only","Total silence"];currentIndex:["off","priority","alarms","silence"].indexOf(page.config.dnd||"off");onActivated:i=>page.control.configure({dnd:["off","priority","alarms","silence"][i],manualDnd:true})}
 SettingSwitch {text:"Manual DND override";checked:!!page.config.manualDnd;onClicked:page.control.configure({manualDnd:checked})}
 SettingSwitch {text:"Allow critical system warnings in Priority mode";checked:!!page.config.criticalException;onClicked:page.control.configure({criticalException:checked})}
 ComboBox {font.pixelSize:14;Layout.fillWidth:true;Layout.minimumWidth:0;implicitWidth:240;model:["Show content allowed by app","Hide sensitive content","Count only","Hide notifications"];currentIndex:["all","sensitive","count","hidden"].indexOf(page.config.lockPrivacy||"sensitive");onActivated:i=>page.control.configure({lockPrivacy:["all","sensitive","count","hidden"][i]})}
 SettingLabel {text:"History retention (days)"}
 SpinBox {font.pixelSize:14;from:1;to:365;value:page.config.retentionDays||7;editable:true;onValueModified:page.control.configure({retentionDays:value})}
 SettingLabel {text:"Scheduled DND · local time";font.bold:true}
 SettingSwitch {text:"Enable schedule";checked:!!(page.config.schedule||{}).enabled;onClicked:page.schedule({enabled:checked})}
 RowLayout {
  SettingLabel {text:"Start"}
  SpinBox {font.pixelSize:14;from:0;to:23;value:Math.floor(((page.config.schedule||{}).start||0)/60);onValueModified:page.schedule({start:value*60+startMinute.value})}
  SpinBox {font.pixelSize:14;id:startMinute;from:0;to:59;value:((page.config.schedule||{}).start||0)%60;onValueModified:page.schedule({start:Math.floor(((page.config.schedule||{}).start||0)/60)*60+value})}
 }
 RowLayout {
  SettingLabel {text:"End"}
  SpinBox {font.pixelSize:14;from:0;to:23;value:Math.floor(((page.config.schedule||{}).end||0)/60);onValueModified:page.schedule({end:value*60+endMinute.value})}
  SpinBox {font.pixelSize:14;id:endMinute;from:0;to:59;value:((page.config.schedule||{}).end||0)%60;onValueModified:page.schedule({end:Math.floor(((page.config.schedule||{}).end||0)/60)*60+value})}
 }
 Flow {Layout.fillWidth:true;spacing:2
  Repeater {model:["M","T","W","T","F","S","S"];delegate:CheckBox {font.pixelSize:14;required property int index;required property string modelData;text:modelData;checked:((page.config.schedule||{}).days||[]).indexOf(index)>=0;onClicked:{let days=((page.config.schedule||{}).days||[]).slice();if(checked)days.push(index);else days=days.filter(d=>d!==index);page.schedule({days:days})}}}
 }
 SettingLabel {text:"Per-application policies";font.bold:true}
 Repeater {model:page.apps;delegate:ColumnLayout {
  id:app;required property string modelData
  property var policy:(page.config.apps||{})[modelData]||{}
  Layout.fillWidth:true
  SettingLabel {text:app.modelData;textFormat:Text.PlainText;wrapMode:Text.WrapAnywhere;Layout.fillWidth:true}
  SettingSwitch {text:"Enabled";checked:app.policy.enabled!==false;onClicked:page.control.appPolicy(app.modelData,{enabled:checked})}
  SettingSwitch {text:"Banners";checked:app.policy.banner!==false;onClicked:page.control.appPolicy(app.modelData,{banner:checked})}
  SettingSwitch {text:"DND priority exception";checked:!!app.policy.dndException;onClicked:page.control.appPolicy(app.modelData,{dndException:checked})}
  ComboBox {font.pixelSize:14;Layout.fillWidth:true;Layout.minimumWidth:0;implicitWidth:240;model:["App priority","Low","Normal","High"];currentIndex:(app.policy.priority===undefined?-1:app.policy.priority)+1;onActivated:i=>page.control.appPolicy(app.modelData,{priority:i-1})}
  ComboBox {font.pixelSize:14;Layout.fillWidth:true;Layout.minimumWidth:0;implicitWidth:240;model:["Default sound","Soft sound","Silent"];currentIndex:["default","soft","silent"].indexOf(app.policy.sound||"default");onActivated:i=>page.control.appPolicy(app.modelData,{sound:["default","soft","silent"][i]})}
  ComboBox {font.pixelSize:14;Layout.fillWidth:true;Layout.minimumWidth:0;implicitWidth:240;model:["Application groups","Thread / conversation","Category","No grouping"];currentIndex:["application","thread","category","none"].indexOf(app.policy.grouping||"thread");onActivated:i=>page.control.appPolicy(app.modelData,{grouping:["application","thread","category","none"][i]})}
  ComboBox {font.pixelSize:14;Layout.fillWidth:true;Layout.minimumWidth:0;implicitWidth:240;model:["Allow preview","Hide sensitive","Count only","Hidden"];currentIndex:["all","sensitive","count","hidden"].indexOf(app.policy.lockPrivacy||"sensitive");onActivated:i=>page.control.appPolicy(app.modelData,{lockPrivacy:["all","sensitive","count","hidden"][i]})}
 }}
 SettingLabel {text:"Vibration and deep-suspend wake are not verified. Inline reply requires an application reply API. EtherLock authentication is not installed.";wrapMode:Text.Wrap;Layout.fillWidth:true;font.pixelSize:12;color:"#606f80"}
 SettingLabel {text:page.control.message;wrapMode:Text.Wrap;Layout.fillWidth:true;visible:text.length>0}
 function schedule(patch){page.control.configure({schedule:Object.assign({},page.config.schedule,patch)})}
}
