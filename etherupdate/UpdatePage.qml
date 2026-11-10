import "../qml/StructuredData.js" as Data
import QtQuick
import QtQuick.Layouts
import QtQuick.Controls
import "../qml/settings" as S

ColumnLayout {
 id:page;objectName:"etherUpdatePage";required property var tokens
 readonly property var state:UpdateControl.state||({})
 readonly property var discovery:state.discovery||({})
 spacing:tokens.sectionGap
 component Card:S.SettingsSection {tokens:page.tokens;Layout.fillWidth:true}
 component Row:S.SettingsRow {tokens:page.tokens;Layout.fillWidth:true;arrow:false}
 component Status:S.SettingsStatus {tokens:page.tokens;Layout.fillWidth:true}
 component Action:S.SettingsAction {tokens:page.tokens;Layout.fillWidth:true;enabled:!!page.state.ready&&!page.state.busy&&!page.state.authorizing}
 function tx(id){return (state.history||[]).find(t=>t.id===id)||({})}
 Status {visible:!page.state.ready;state:"warning";text:"EtherUpdate service unavailable. Install and commission the agent to manage trusted releases."}
 Status {visible:!!UpdateControl.message;text:UpdateControl.message}
 Status {visible:!!page.state.lastError;state:"warning";text:page.state.lastError||""}
 Card {
  Row {title:"AutoUpdate access token";description:page.state.credentialConfigured?"Token configured · value hidden":"No token saved · public projects only"}
  S.SettingsInput {
   id:tokenField;objectName:"etherUpdateTokenInput";tokens:page.tokens;Layout.fillWidth:true
   placeholderText:"Enter the new API token";echoMode:TextInput.Password;passwordMaskDelay:0
   inputMethodHints:Qt.ImhHiddenText|Qt.ImhSensitiveData|Qt.ImhNoPredictiveText
   enabled:!!page.state.ready&&!page.state.busy&&!page.state.authorizing
   onKeyboardRequested:{Qt.inputMethod.show();page.keyboardRequested()}
  }
  Action {objectName:"etherUpdateSaveToken";text:"Save and Test Connection";enabled:!!page.state.ready&&!page.state.busy&&!page.state.authorizing&&tokenField.text.length>=20;onClicked:{let value=tokenField.text;tokenField.clear();UpdateControl.saveToken(value);value=""}}
  Action {text:"Remove Saved Token";visible:!!page.state.credentialConfigured;onClicked:removeToken.open()}
  Status {text:"Use a newly generated token. Saving requires administrator authentication; the saved value is never displayed."}
 }
 Card {
  Row {title:"Software Updates";description:page.discovery.status||"Not checked"}
  Row {title:"Last successful check";description:page.discovery.lastSuccessfulCheck?new Date(page.discovery.lastSuccessfulCheck*1000).toLocaleString():"No successful check recorded"}
  Row {title:"Available updates";description:String((page.discovery.updates||[]).filter(u=>u.status==="Update available").length)}
  Row {title:"Release channels";description:"Stable by default · selection is saved per component"}
  Status {visible:!(page.discovery.updates||[]).length;text:"No components commissioned. An administrator must map existing AutoUpdate projects and provision trusted publisher keys before installation."}
  Action {text:"Check for Updates";onClicked:UpdateControl.check()}
  Status {visible:!!page.state.busy;text:"Update operation in progress"}
  Status {visible:!!page.state.progress&&!!page.state.progress.total;text:"Downloaded "+Math.round(100*(page.state.progress||{}).bytes/((page.state.progress||{}).total||1))+"%"}
  S.SettingsAction {tokens:page.tokens;Layout.fillWidth:true;text:"Cancel Download";visible:!!page.state.progress&&!!page.state.progress.total;onClicked:UpdateControl.cancel()}
 }
 Repeater {
  model:page.discovery.updates||[]
  delegate:Card {
   required property var modelData
   Row {title:modelData.name;description:(modelData.installed||"Not installed")+" → "+(modelData.version||"No release")}
   Status {text:modelData.status+(modelData.reason?" · "+modelData.reason:"")}
   Row {title:"Release notes";description:modelData.notes||"No release notes"}
   Row {title:"Download and compatibility";description:Math.ceil((modelData.size||0)/1024)+" KiB · "+(modelData.compatible?"Compatible signed manifest":"Compatibility unverified")+(modelData.reboot?" · Reboot required":"")}
   Row {title:"Dependencies";description:Data.text(modelData.dependencies||{})}
   S.SettingsSelect {tokens:page.tokens;Layout.fillWidth:true;title:"Channel";model:["Stable","Beta","Nightly","Experimental"];currentIndex:Math.max(0,model.indexOf(modelData.channel));enabled:!page.state.busy;onActivated:index=>{let channel=["Stable","Beta","Nightly","Experimental"][index];if(channel==="Experimental"){experimental.project=modelData.project;experimental.open()}else UpdateControl.channel(modelData.project,channel,false)}}
   Action {text:"Download";visible:page.tx(modelData.transaction).state==="Available";onClicked:UpdateControl.download(modelData.transaction)}
   Action {text:"Review Installation";visible:page.tx(modelData.transaction).state==="Verified";onClicked:UpdateControl.prepare(modelData.transaction)}
  }
 }
 Card {
  visible:!!UpdateControl.plan.transaction
  Row {title:"Review approved installation";description:(UpdateControl.plan.package||"")+" "+(UpdateControl.plan.version||"")}
  Status {state:"warning";text:(UpdateControl.plan.recovery||"")+". Approval expires after two minutes. Installation requires administrator authentication."}
  Action {text:"Confirm Install";onClicked:UpdateControl.install()}
 }
 Card {
  Row {title:"History";description:"Success is recorded only after local health checks pass."}
  Repeater {model:page.state.history||[];delegate:Row {required property var modelData;title:(modelData.document.manifest||{}).package+" · "+modelData.state;description:new Date(modelData.updated*1000).toLocaleString()+" · "+(modelData.document.error||((modelData.document.recovery||{}).strategy)||"")}}
 }
 Card {
  Row {title:"Advanced";description:page.state.server||"https://autoupddate.etherneco.com"}
  Row {title:"Agent and trust";description:(page.state.agentVersion||"Unavailable")+" · "+(page.state.trustKeys||[]).filter(k=>!k.revoked).length+" active local signing keys"}
  Row {title:"Cache usage";description:Math.ceil((page.state.cacheUsage||0)/1024)+" KiB"}
  Status {text:"Versioned application recovery is supported. OS rollback, boot updates and self-update recovery are not commissioned. Debian installations require a locally verified manual recovery plan."}
  Status {text:"Scheduled discovery runs daily. Scheduled installation, rollout controls and server reports await supported contracts. Offline import uses the same signature checks."}
  Row {title:"Installed EtherPocket version";description:"No coordinated system release registered"}
 }
 S.SettingsDialog {tokens:page.tokens;id:experimental;property string project:"";title:"Use Experimental releases?";modal:true;standardButtons:Dialog.Ok|Dialog.Cancel;height:240;contentItem:Text {color:page.tokens.ink;text:"Experimental releases can disrupt critical components. Installation safety checks still apply.";wrapMode:Text.WordWrap} onAccepted:UpdateControl.channel(project,"Experimental",true)}
 S.SettingsDialog {tokens:page.tokens;id:removeToken;title:"Remove saved token?";standardButtons:Dialog.Ok|Dialog.Cancel;height:220;contentItem:Text {color:page.tokens.ink;text:"Private project access will stop. The API key itself remains valid until revoked in AutoUpdate Center.";wrapMode:Text.WordWrap} onAccepted:UpdateControl.removeToken()}
 signal keyboardRequested()
}
