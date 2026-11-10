import "../qml" as UI
import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import "../qml/settings" as S

ColumnLayout {
 id:hardware;objectName:"hardwarePage"
 required property var tokens
 signal keyboardRequested()
 property string category:""
 property string filter:""
 property var selected:({})
 property bool advanced:false
 property string pendingMedia:""
 readonly property var snapshot:Hardware.state.ready?Hardware.state:({available:Hardware.state.available,ready:false,message:Hardware.state.message})
 Connections {target:Hardware;function onChanged(){if(!Hardware.state.ready){detail.close();hardware.selected={}}}}
 readonly property var rows:category||filter?(snapshot.components||[]).filter(r=>(!category||r.category===category)&&(!filter||(r.title+" "+r.status+" "+r.reason).toLowerCase().indexOf(filter.toLowerCase())>=0)):[]
 spacing:tokens.sectionGap
 function details(row){selected=row;advanced=false;detail.open()}
 function choose(value){category=value;filter="";Qt.callLater(function(){let p=hardware.parent;while(p){if(p.contentY!==undefined){p.contentY=0;break}p=p.parent}})}
 function facts(row){
  let d=row.details||{};let lines=[]
  if(Array.isArray(d))return d.map(c=>c.id+": "+c.status+"\n"+(c.failureReason||"Verified for the reported scope")).join("\n\n")
  let labels={architecture:"Architecture",cores:"CPU cores",totalBytes:"Total memory",availableBytes:"Available memory",swapTotalBytes:"Swap",capacityBytes:"Capacity",connection:"Connection",enabled:"Output enabled",touchscreen:"Touchscreen input",interface:"Interface",operstate:"Link state",radioEnabled:"Radio enabled",hardwareRadioEnabled:"Hardware radio enabled",signalPercent:"Signal (%)",powered:"Controller powered",discovering:"Discovery active",manufacturer:"Manufacturer",model:"Model",firmwareRevision:"Firmware revision",simPresent:"SIM present",registration:"Registration code",controlTransport:"Control transport",state:"Backend state",current_speed:"USB speed",maximum_speed:"Maximum USB speed",data_role:"Data role",power_role:"Power role",mode:"Current mode",kind:"Device type",type:"Supply type",status:"Supply state",capacity:"Battery (%)",online:"External power online",kernel:"Kernel",configAvailable:"Kernel configuration available"}
  for(let k in labels){if(d[k]!==undefined&&d[k]!==null&&d[k]!==""){let value=d[k];if(k.endsWith("Bytes"))value=(Number(value)/1073741824).toFixed(2)+" GiB";if(typeof value==="boolean")value=value?"Yes":"No";lines.push(labels[k]+": "+value)}}
  if(d.captureNodes)lines.push("ALSA capture nodes: "+d.captureNodes.length+" (physical microphone untested)")
  if(d.playbackNodes)lines.push("ALSA playback nodes: "+d.playbackNodes.length+" (physical speaker untested)")
  if(d.mounts)lines.push("Mounted filesystems: "+d.mounts.length)
  if(d.channels)lines.push("Exposed sensor channels: "+d.channels.length)
  if(d.modes)lines.push("Advertised modes: "+d.modes.join(", "))
  if(d.states)lines.push("Advertised suspend states: "+d.states.join(", "))
  if(d.temp)lines.push("Battery temperature: "+(Number(d.temp)/10).toFixed(1)+" °C")
  if(d.capabilities)for(let id in d.capabilities){let c=d.capabilities[id];lines.push(id+": "+(c.operational===true?"Verified":c.operational===false?"Not operational":"Not tested"))}
  return lines.join("\n")||"Detection evidence is available. Expand technical details for exposed interfaces and diagnostic evidence."
 }
 function stateColour(state){return state==="Working"?tokens.success:["Detected","Not tested"].indexOf(state)>=0?tokens.muted:tokens.warning}
 S.SettingsInfoCard {tokens:hardware.tokens;Layout.fillWidth:true;visible:!hardware.category;title:(hardware.snapshot.system||{}).device||"Hardware & Drivers";description:((hardware.snapshot.system||{}).os||{}).PRETTY_NAME||hardware.snapshot.message||"Reading hardware evidence…"}
 S.SettingsStatus {tokens:hardware.tokens;Layout.fillWidth:true;state:hardware.snapshot.available?"neutral":"warning";text:hardware.snapshot.ready?(hardware.snapshot.components||[]).length+" components · "+(hardware.snapshot.failedDiagnostics||[]).length+" diagnostics need attention · "+hardware.snapshot.verifiedAt:"Hardware service unavailable or starting. No hardware state is assumed."}
 S.SettingsInfoCard {tokens:hardware.tokens;Layout.fillWidth:true;visible:!hardware.category;title:"System overview";description:{
  let cpu=(hardware.snapshot.components||[]).find(r=>r.id==="cpu")||{};let memory=((hardware.snapshot.components||[]).find(r=>r.id==="memory")||{}).details||{};let mounts=(((hardware.snapshot.components||[]).find(r=>r.id==="filesystems")||{}).details||{}).mounts||[];let disk=mounts.find(m=>m.mount==="/")||{};
  return (cpu.title||"CPU unverified")+"\nMemory: "+(memory.totalBytes?(memory.totalBytes/1073741824).toFixed(1)+" GiB":"Unknown")+"\nStorage: "+(disk.totalBytes?(disk.availableBytes/1073741824).toFixed(1)+" GiB free of "+(disk.totalBytes/1073741824).toFixed(1)+" GiB":"Unknown")+"\nKernel: "+((hardware.snapshot.system||{}).kernel||"Unknown")
 }}
 S.SettingsAction {tokens:hardware.tokens;Layout.fillWidth:true;text:Hardware.busy?"Checking hardware…":"Refresh hardware";enabled:!Hardware.busy&&!!hardware.snapshot.available;onClicked:Hardware.refresh(hardware.category||"all")}
 S.SettingsAction {tokens:hardware.tokens;Layout.fillWidth:true;text:"Run read-only diagnostics";enabled:!Hardware.busy&&!!hardware.snapshot.ready;onClicked:Hardware.diagnose(hardware.category||"all")}
 S.SettingsStatus {tokens:hardware.tokens;Layout.fillWidth:true;text:"Detection and driver binding are separate from functional verification. Radio scans, AP activation, media capture and suspend are never started by these checks."}
 S.SettingsSection {tokens:hardware.tokens;Layout.fillWidth:true
  S.SettingsRow {tokens:hardware.tokens;Layout.fillWidth:true;title:hardware.category?"All hardware categories":"Hardware categories";description:hardware.category?((hardware.snapshot.categories||[]).find(c=>c.id===hardware.category)||{}).title||hardware.category:"Select a category below";onClicked:hardware.choose("")}
  Repeater {model:hardware.category?[]:hardware.snapshot.categories||[];delegate:S.SettingsRow {required property var modelData;tokens:hardware.tokens;Layout.fillWidth:true;title:modelData.title;description:modelData.count+" components";onClicked:hardware.choose(modelData.id)}}
 }
 S.SettingsInput {tokens:hardware.tokens;Layout.fillWidth:true;placeholderText:"Filter hardware…";text:hardware.filter;onTextEdited:hardware.filter=text;onKeyboardRequested:hardware.keyboardRequested()}
 S.SettingsSection {tokens:hardware.tokens;Layout.fillWidth:true
  Repeater {model:hardware.rows;delegate:S.SettingsRow {objectName:"hardwareDevice";required property var modelData;tokens:hardware.tokens;Layout.fillWidth:true;title:modelData.title;description:modelData.status+(modelData.reason?" · "+modelData.reason:"");onClicked:hardware.details(modelData)}}
 }
 S.SettingsInfoCard {tokens:hardware.tokens;Layout.fillWidth:true;visible:hardware.rows.length===0&&(!!hardware.category||!!hardware.filter);title:"No matching components";description:"An absent standard interface does not prove that an Android vendor device is unsupported."}
 S.SettingsSection {tokens:hardware.tokens;Layout.fillWidth:true
  S.SettingsRow {tokens:hardware.tokens;Layout.fillWidth:true;title:"Shared capability registry";description:"The same evidence is available to every EtherPocket module";onClicked:{hardware.selected={title:"Capability registry",status:"Read-only",details:hardware.snapshot.capabilities||[]};hardware.advanced=true;detail.open()}}
  S.SettingsRow {tokens:hardware.tokens;Layout.fillWidth:true;title:"Inspect session graphics, displays and audio";description:"Read current user services; no recording or playback";onClicked:{Hardware.inspectSession();sessionSheet.open()}}
  S.SettingsRow {tokens:hardware.tokens;Layout.fillWidth:true;title:"Microphone recording test";description:"Explicit three-second recording, deleted immediately afterwards";onClicked:{hardware.pendingMedia="microphone";mediaConfirm.open()}}
  S.SettingsRow {tokens:hardware.tokens;Layout.fillWidth:true;title:"Speaker playback test";description:"Explicit quiet tone through your current default output";onClicked:{hardware.pendingMedia="speaker";mediaConfirm.open()}}
 }
 S.SettingsSection {tokens:hardware.tokens;Layout.fillWidth:true
  S.SettingsStatus {tokens:hardware.tokens;Layout.fillWidth:true;text:"Drivers & Firmware · Review compatible Debian diagnostic tools. These tools do not install a kernel driver or vendor firmware. Kernel, modem and protected-partition changes require separate maintenance."}
  Repeater {model:["iw","v4l-utils","mesa-utils","alsa-utils","pulseaudio-utils"];delegate:S.SettingsRow {required property string modelData;tokens:hardware.tokens;Layout.fillWidth:true;title:modelData;description:"Check installed state, repository candidate and compatibility";enabled:!Hardware.busy;onClicked:{Hardware.planRepair(modelData);repairSheet.open()}}}
 }
 S.SettingsSection {tokens:hardware.tokens;Layout.fillWidth:true
  S.SettingsRow {tokens:hardware.tokens;Layout.fillWidth:true;title:"Diagnostic history";description:"Search and filter the latest 200 of up to 1,000 state transitions";onClicked:{Hardware.loadHistory();historySheet.open()}}
  S.SettingsRow {tokens:hardware.tokens;Layout.fillWidth:true;title:"Export JSON report";description:"Redacted report in Documents/EtherHardware";onClicked:Hardware.exportReport("json")}
  S.SettingsRow {tokens:hardware.tokens;Layout.fillWidth:true;title:"Export text report";description:"Hardware, drivers, capabilities and history";onClicked:Hardware.exportReport("text")}
 }
 S.SettingsStatus {tokens:hardware.tokens;Layout.fillWidth:true;text:Hardware.message||hardware.snapshot.message||""}
 S.SettingsBottomSheet {id:detail;objectName:"hardwareDetailSheet";tokens:hardware.tokens;title:hardware.selected.title||"Device details";standardButtons:Dialog.Close
  contentItem:ScrollView {implicitHeight:Math.min(420,detail.parent.height/detail.scale-150);clip:true;contentWidth:availableWidth
   ColumnLayout {width:parent.width;spacing:12
    S.SettingsStatus {tokens:hardware.tokens;Layout.fillWidth:true;text:hardware.selected.status||"Unknown";color:hardware.stateColour(hardware.selected.status)}
    S.SettingsStatus {tokens:hardware.tokens;Layout.fillWidth:true;text:hardware.selected.reason||"Evidence is scoped to this component"}
    S.SettingsStatus {tokens:hardware.tokens;Layout.fillWidth:true;text:hardware.facts(hardware.selected)}
    S.SettingsAction {tokens:hardware.tokens;Layout.fillWidth:true;text:hardware.advanced?"Hide driver and technical evidence":"Show driver and technical evidence";onClicked:hardware.advanced=!hardware.advanced}
    UI.DataView {tokens:hardware.tokens;Layout.fillWidth:true;visible:hardware.advanced;value:({details:hardware.selected.details||{},driver:hardware.selected.driver||{},nodes:hardware.selected.nodes||[],service:hardware.selected.service||null,path:hardware.selected.path||"",verifiedAt:hardware.selected.verifiedAt||null})}
   }
  }
  footer:S.SettingsAction {tokens:hardware.tokens;text:"Close";onClicked:detail.close()}
 }
 S.SettingsBottomSheet {id:sessionSheet;tokens:hardware.tokens;title:"Session evidence";standardButtons:Dialog.Close
  contentItem:ScrollView {implicitHeight:Math.min(420,sessionSheet.parent.height/sessionSheet.scale-150);clip:true;contentWidth:availableWidth
   UI.DataView {tokens:hardware.tokens;width:parent.width;value:Hardware.session}
  }
  footer:S.SettingsAction {tokens:hardware.tokens;text:"Close";onClicked:sessionSheet.close()}
 }
 S.SettingsBottomSheet {id:repairSheet;tokens:hardware.tokens;title:"Review diagnostic tool";standardButtons:Dialog.Close
  contentItem:ColumnLayout {spacing:12
   ScrollView {Layout.fillWidth:true;implicitHeight:Math.min(350,repairSheet.parent.height/repairSheet.scale-220);clip:true;contentWidth:availableWidth
    UI.DataView {tokens:hardware.tokens;width:parent.width;value:Hardware.repairPlan.package?Hardware.repairPlan:{status:Hardware.message||"Checking compatibility..."}}
   }
   S.SettingsAction {tokens:hardware.tokens;Layout.fillWidth:true;text:Hardware.repairPlan.alreadyInstalled?"Already installed":"Install reviewed tool";enabled:!Hardware.busy&&!!Hardware.repairPlan.package&&!Hardware.repairPlan.alreadyInstalled;onClicked:Hardware.installReviewedTool()}
  }
  footer:S.SettingsAction {tokens:hardware.tokens;text:"Close";onClicked:repairSheet.close()}
 }
 S.SettingsBottomSheet {id:historySheet;tokens:hardware.tokens;title:"Diagnostic history";standardButtons:Dialog.Close
  contentItem:ColumnLayout {
   S.SettingsInput {id:historyQuery;tokens:hardware.tokens;Layout.fillWidth:true;placeholderText:"Search history…";onKeyboardRequested:hardware.keyboardRequested()}
   S.SettingsInput {id:historyComponent;tokens:hardware.tokens;Layout.fillWidth:true;placeholderText:"Component ID (optional)";onKeyboardRequested:hardware.keyboardRequested()}
   S.SettingsAction {tokens:hardware.tokens;Layout.fillWidth:true;text:"Apply filters";onClicked:Hardware.loadHistory(historyQuery.text,historyComponent.text)}
   ScrollView {Layout.fillWidth:true;implicitHeight:Math.max(70,Math.min(230,historySheet.parent.height/historySheet.scale-340));clip:true;contentWidth:availableWidth
    S.SettingsStatus {tokens:hardware.tokens;width:parent.width;text:Hardware.history.map(r=>r.timestamp+"\n"+r.component+": "+r.previous+" → "+r.current+"\n"+r.reason).join("\n\n")||"No matching state transitions"}
   }
   S.SettingsAction {tokens:hardware.tokens;Layout.fillWidth:true;text:"Clear shared history…";enabled:!Hardware.busy;onClicked:clearConfirm.open()}
  }
  footer:S.SettingsAction {tokens:hardware.tokens;text:"Close";onClicked:historySheet.close()}
 }
 S.SettingsDialog {id:mediaConfirm;tokens:hardware.tokens;title:hardware.pendingMedia==="microphone"?"Record microphone?":"Play test tone?";standardButtons:Dialog.Ok|Dialog.Cancel
  contentItem:S.SettingsStatus {tokens:hardware.tokens;text:hardware.pendingMedia==="microphone"?"This records three seconds from the current default input into a private temporary file and deletes it. Begin only when you are ready.":"This plays a quiet half-second tone through the current default output. Check the route and volume before starting."}
  onAccepted:Hardware.mediaTest(hardware.pendingMedia)
 }
 S.SettingsDialog {id:clearConfirm;tokens:hardware.tokens;title:"Clear shared diagnostic history?";standardButtons:Dialog.Ok|Dialog.Cancel
  contentItem:S.SettingsStatus {tokens:hardware.tokens;text:"This removes saved transitions for all users. PolicyKit administrator authentication is required."}
  onAccepted:Hardware.clearHistory()
 }
}
