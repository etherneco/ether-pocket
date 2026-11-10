import "../qml" as UI
import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import "../qml/settings" as S

ColumnLayout {
 id:page;objectName:"etherPowerPage"
 required property var tokens
 signal keyboardRequested()
 property string section:"overview"
 property string metric:"capacity"
 property bool technical:false
 property bool draftsSeeded:false
 property var customPolicies:[]
 property var customGpu:({})
 property bool customLoaded:false
 readonly property var snapshot:Power.state.ready?Power.state:({})
 readonly property var config:snapshot.config||({})
 readonly property var profile:snapshot.profileState||({})
 readonly property var sections:[{id:"battery",title:"Battery",description:"Health, runtime and warnings"},{id:"charging",title:"Charging",description:"USB-C, input power and charging limits"},{id:"profiles",title:"Power Profiles",description:"Balanced, Power Saver, Performance and Custom"},{id:"display",title:"Display Power",description:"Brightness, timeouts and external sessions"},{id:"sleep",title:"Sleep & Wake",description:"Verified sleep, inhibitors and resume evidence"},{id:"thermal",title:"Thermal",description:"Verified temperatures and kernel cooling"},{id:"history",title:"Power History",description:"Hour, day, week and month"},{id:"advanced",title:"Advanced",description:"CPU/GPU frequencies and driver evidence"}]
 spacing:tokens.sectionGap
 function value(v,suffix,decimals){return v===undefined||v===null?"Unavailable":Number(v).toFixed(decimals===undefined?1:decimals)+(suffix||"")}
 function choose(id){section=id;Qt.callLater(function(){let p=page.parent;while(p){if(p.contentY!==undefined){p.contentY=0;break}p=p.parent}});if(id==="history")Power.loadHistory(24)}
 function seed(){let t=config.thresholds||{};low.text=String(t.low||20);critical.text=String(t.critical||10);emergency.text=String(t.emergency||5);cpuWarning.text=String(config.thermalWarningC||80);batteryWarning.text=String(config.batteryWarningC||45);draftsSeeded=!!Power.state.ready}
 Connections {target:Power;function onChanged(){if(!page.draftsSeeded&&Power.state.ready)page.seed()}}
 Component.onCompleted:{seed();Power.loadHistory(24)}
 component Card:S.SettingsSection {tokens:page.tokens;Layout.fillWidth:true}
 component Info:S.SettingsInfoCard {tokens:page.tokens;Layout.fillWidth:true}
 component Status:S.SettingsStatus {tokens:page.tokens;Layout.fillWidth:true}
 component Row:S.SettingsRow {tokens:page.tokens;Layout.fillWidth:true}
 component Action:S.SettingsAction {tokens:page.tokens;Layout.fillWidth:true}
 component Input:S.SettingsInput {tokens:page.tokens;Layout.fillWidth:true;enabled:!!Power.state.ready;onKeyboardRequested:page.keyboardRequested()}
 Info {title:page.value(page.snapshot.capacity,"%",0);description:(page.snapshot.status||"Power service unavailable")+" · "+(page.snapshot.externalPower?"External power detected":"Battery / no external source verified")+"\nBattery: "+page.value(page.snapshot.batteryTemperatureC," °C")+" · Profile: "+(page.profile.effective||"Unavailable")}
 Status {visible:!Power.state.ready;state:"warning";text:Power.state.message||"Waiting for the real power service; no battery measurements are assumed."}
 Status {visible:!!page.snapshot.batteryWarning||!!page.snapshot.thermalWarning;state:"warning";text:page.snapshot.thermalWarning?"Thermal warning: kernel protections remain enabled":"Battery warning: "+(page.snapshot.batteryWarning||"")}
 Row {visible:page.section!=="overview";title:"All power sections";description:(page.sections.find(s=>s.id===page.section)||{}).title||"Battery & Power";onClicked:page.choose("overview")}
 Repeater {model:page.section==="overview"?page.sections:[];delegate:Row {required property var modelData;objectName:"powerSection-"+modelData.id;title:modelData.title;description:modelData.description;onClicked:page.choose(modelData.id)}}
 Card {visible:page.section==="overview"||page.section==="battery"
  Row {title:"Estimated runtime";description:((page.snapshot.runtime||{}).current||{}).minutes!==undefined?"About "+page.snapshot.runtime.current.minutes+" minutes · smoothed estimate":"Unavailable — insufficient battery-only discharge history";arrow:false}
  Row {title:"Battery health";description:(page.snapshot.health||"Unavailable")+" · Driver-reported status";arrow:false}
  Row {title:"Voltage and current";description:page.value(page.snapshot.voltageV," V",3)+" · "+page.value(page.snapshot.currentA," A",3);arrow:false}
  Row {title:"Capacity measurements";description:"Full: "+page.value(page.snapshot.fullCapacityAh," Ah",3)+"\nDesign: "+page.value(page.snapshot.designCapacityAh," Ah",3)+"\nWear: "+page.value(page.snapshot.healthPercent,"%",1);arrow:false}
  Row {title:"Charge cycle counter";description:page.value(page.snapshot.cycleCount,"",0)+" · Driver-reported; independently unverified";arrow:false}
  Status {text:"Positive battery current denotes discharge on this verified driver. Full-capacity and internal charge-counter calibration are separate; unavailable health metrics are not invented."}
 }
 Card {visible:page.section==="battery"
  Status {text:"Warning thresholds (%) · Emergency < Critical < Low"}
  Status {text:"Saved: low "+((page.config.thresholds||{}).low||20)+"% · critical "+((page.config.thresholds||{}).critical||10)+"% · emergency "+((page.config.thresholds||{}).emergency||5)+"%"}
  Input {id:low;objectName:"powerLowThreshold";placeholderText:"Low battery (%)";inputMethodHints:Qt.ImhDigitsOnly}
  Input {id:critical;placeholderText:"Critical battery (%)";inputMethodHints:Qt.ImhDigitsOnly}
  Input {id:emergency;placeholderText:"Emergency battery (%)";inputMethodHints:Qt.ImhDigitsOnly}
  Action {text:"Save warning thresholds";enabled:!Power.busy;onClicked:Power.configure({thresholds:{low:Number(low.text),critical:Number(critical.text),emergency:Number(emergency.text)}})}
  S.SettingsToggle {tokens:page.tokens;Layout.fillWidth:true;title:"Enable Saver on low battery";description:"Uses the same verified CPU/GPU profile; never stops sharing or other services";checked:page.config.lowBatteryAction==="power-saver";onRequested:wanted=>Power.configure({lowBatteryAction:wanted?"power-saver":"notify"})}
  S.SettingsToggle {tokens:page.tokens;Layout.fillWidth:true;title:"Request emergency shutdown";description:"Opens the power menu for confirmation; never forces shutdown";checked:page.config.emergencyAction==="request-shutdown";onRequested:wanted=>Power.configure({emergencyAction:wanted?"request-shutdown":"notify"})}
 }
 Card {visible:page.section==="charging"
  Repeater {model:page.snapshot.supplies||[];delegate:Row {required property var modelData;title:modelData.name;description:(modelData.real_type||modelData.type||"Unknown supply")+" · Present: "+(modelData.present||"Unknown")+"\nVoltage: "+page.value(modelData.voltageV," V",3)+" · Input current: "+page.value(modelData.inputCurrentA," A",3)+"\nInput estimate: "+page.value(modelData.estimatedInputPowerW," W",3)+"\nPD: "+(modelData.pdNegotiated===true?"Active":modelData.pdNegotiated===false?"Inactive":"Unverified")+"\n"+(modelData.typec_mode||"");arrow:false}}
  Info {title:"Charging controls";description:(page.snapshot.chargeLimit||{}).error||"No verified charge-percentage control"}
  Row {title:"Charger temperature";description:page.value(page.snapshot.chargerTemperatureC," °C");arrow:false}
  Row {title:"Battery charging power";description:page.value(page.snapshot.batteryChargingPowerW," W",3);arrow:false}
  Status {text:"Nominal USB_PD type does not prove PD negotiation. USB present and online may disagree on this vendor driver. No thermal protection, calibration, USB role or charger register is changed."}
 }
 Card {visible:page.section==="overview"||page.section==="profiles"
  Status {text:"Requested: "+(page.profile.requested||"None")+"\nEffective: "+(page.profile.effective||"Unavailable")+(page.profile.error?"\n"+page.profile.error:"")}
  Repeater {model:[{id:"balanced",title:"Balanced",description:"Dynamic schedutil governor with the original verified maximums"},{id:"power-saver",title:"Power Saver",description:"Conservative governor, supported CPU/GPU caps and reduced nonessential shell refresh"},{id:"performance",title:"Performance",description:"Performance governor within the original frequency limits"}];delegate:Row {required property var modelData;objectName:"powerProfile-"+modelData.id;title:modelData.title;description:modelData.description;value:page.profile.effective===modelData.id?"Active":"";enabled:!Power.busy&&!!Power.state.ready;onClicked:Power.profile(modelData.id)}}
  Action {text:"Restore original kernel settings";enabled:!Power.busy&&!!Power.state.ready;onClicked:Power.restore()}
 }
 Card {visible:page.section==="profiles"
  Status {text:"Custom profile · only advertised governors/frequencies are accepted. CPU limits use kHz, GPU limit uses Hz. Unknown keys and policies are rejected."}
  Action {text:"Load current settings";enabled:!!Power.state.ready;onClicked:{page.customPolicies=((page.snapshot.controls||{}).cpu||[]).map(p=>Object.assign({},p));page.customGpu=Object.assign({},(page.snapshot.controls||{}).gpu||{});page.customLoaded=true}}
  Repeater {id:customCpu;model:page.customPolicies
   delegate:ColumnLayout {
    id:policyEditor;required property var modelData;Layout.fillWidth:true
    readonly property var profileValues:({governor:governorChoice.currentText,maxKHz:frequencyChoice.model[frequencyChoice.currentIndex]})
    Row {title:"CPU · "+policyEditor.modelData.id;description:"Cores: "+policyEditor.modelData.cores;arrow:false}
    Label {text:"Governor";color:page.tokens.ink}
    ComboBox {id:governorChoice;Layout.fillWidth:true;model:policyEditor.modelData.governors||[];currentIndex:model.indexOf(policyEditor.modelData.governor);Accessible.name:"CPU governor"}
    Label {text:"Maximum CPU frequency";color:page.tokens.ink}
    ComboBox {id:frequencyChoice;Layout.fillWidth:true;model:(policyEditor.modelData.frequenciesKHz||[]).filter(f=>f>=policyEditor.modelData.minKHz&&f<=policyEditor.modelData.maxKHz);currentIndex:model.indexOf(policyEditor.modelData.maxKHz);displayText:currentIndex>=0?Number(model[currentIndex]/1000).toLocaleString()+" MHz":"Select a frequency";delegate:ItemDelegate {required property var modelData;width:frequencyChoice.width;text:Number(modelData/1000).toLocaleString()+" MHz"} Accessible.name:"Maximum CPU frequency"}
   }
  }
  Label {visible:page.customLoaded&&!!page.customGpu.path;text:"Maximum GPU frequency";color:page.tokens.ink}
  ComboBox {id:gpuFrequency;visible:page.customLoaded&&!!page.customGpu.path;Layout.fillWidth:true;model:(page.customGpu.frequenciesHz||[]).filter(f=>f>=page.customGpu.minHz&&f<=page.customGpu.maxHz);currentIndex:model.indexOf(page.customGpu.maxHz);displayText:currentIndex>=0?Number(model[currentIndex]/1000000).toLocaleString()+" MHz":"Select a frequency";delegate:ItemDelegate {required property var modelData;width:gpuFrequency.width;text:Number(modelData/1000000).toLocaleString()+" MHz"} Accessible.name:"Maximum GPU frequency"}
  Action {text:"Apply Custom profile";enabled:!Power.busy&&!!Power.state.ready&&page.customLoaded&&page.customPolicies.length>0;onClicked:{let cpu={};for(let i=0;i<customCpu.count;i++){let item=customCpu.itemAt(i);cpu[item.modelData.id]=item.profileValues}let settings={cpu:cpu};if(gpuFrequency.visible&&gpuFrequency.currentIndex>=0)settings.gpuMaxHz=gpuFrequency.model[gpuFrequency.currentIndex];Power.profile("custom",JSON.stringify(settings))}}

 }
 Card {visible:page.section==="display"
  S.SettingsSlider {tokens:page.tokens;Layout.fillWidth:true;title:"Panel brightness";value:Number(Core.telemetry.brightness||0);from:1;to:100;suffix:"%";enabled:!!Core.telemetry.brightnessWritable;onMoved:value=>Power.setBrightness(Math.round(value))}
  Status {text:"Separate battery and external-power brightness preferences are stored by the existing user Settings provider."}
  S.SettingsSelect {tokens:page.tokens;Layout.fillWidth:true;title:"Timeout on battery";model:[{label:"Never",seconds:0},{label:"15 seconds",seconds:15},{label:"30 seconds",seconds:30},{label:"1 minute",seconds:60},{label:"2 minutes",seconds:120},{label:"5 minutes",seconds:300}];textRole:"label";currentIndex:Math.max(0,model.findIndex(x=>x.seconds===page.config.batteryTimeout));onActivated:index=>Power.configure({batteryTimeout:model[index].seconds})}
  S.SettingsSelect {tokens:page.tokens;Layout.fillWidth:true;title:"Timeout on external power";model:[{label:"Never",seconds:0},{label:"15 seconds",seconds:15},{label:"30 seconds",seconds:30},{label:"1 minute",seconds:60},{label:"2 minutes",seconds:120},{label:"5 minutes",seconds:300}];textRole:"label";currentIndex:Math.max(0,model.findIndex(x=>x.seconds===page.config.externalTimeout));onActivated:index=>Power.configure({externalTimeout:model[index].seconds})}
  S.SettingsToggle {tokens:page.tokens;Layout.fillWidth:true;title:"Preserve active external display";description:"Suppress whole-screen timeout while an external output is active; no XRandR reconfiguration";checked:page.config.externalDisplayPolicy!=="allow-blank";onRequested:wanted=>Power.configure({externalDisplayPolicy:wanted?"preserve-session":"allow-blank"})}
  Row {title:"Effective session timeout";description:(Power.session.timeoutSeconds===undefined?"Unavailable":Power.session.timeoutSeconds===0?"Never":Power.session.timeoutSeconds+" seconds")+"\nAutomatic brightness: no verified light provider";arrow:false}
  Action {text:"Blank screen using the existing safe workaround";onClicked:Power.screenOff()}
  Status {text:"Software blanking keeps the panel powered to preserve reliable wake. It is not proof of hardware power-down or a measured wattage reduction. Internal-only blanking with AR glasses remains unverified."}
 }
 Card {visible:page.section==="sleep"
  Info {title:(page.snapshot.suspend||{}).verified?"Verified suspend available":"Suspend is blocked";description:(page.snapshot.suspend||{}).error||"Uses logind and existing inhibitors"}
  Row {title:"Advertised kernel states";description:(((page.snapshot.suspend||{}).current||{}).advertisedStates||[]).join(", ")+" · "+(((page.snapshot.suspend||{}).current||{}).memSleep||"Unavailable");arrow:false}
  Row {title:"Power button";description:"Short press: existing blank/wake handler\nLong press: touch power menu\nPower + Volume Down: existing screenshot chord";arrow:false}
  Action {text:"Request verified suspend";enabled:!!(page.snapshot.suspend||{}).verified&&!Power.busy;onClicked:Power.powerAction("suspend")}
  Status {text:"No unattended suspend test is run without a verified wake path. Wake controls remain read-only; a listed kernel state is not proof that resume works."}
  Repeater {model:(((page.snapshot.suspend||{}).current||{}).wakeSources||[]);delegate:Row {required property var modelData;title:modelData.device.split("/").slice(-1)[0];description:"Wake setting: "+modelData.effective;arrow:false}}
 }
 Card {visible:page.section==="thermal"
  Row {title:"CPU temperature";description:page.value(page.snapshot.cpuTemperatureC," °C")+" · Verified TSENS CPU zones";arrow:false}
  Row {title:"GPU temperature";description:page.value(page.snapshot.gpuTemperatureC," °C")+" · gpuss-max-step mapping";arrow:false}
  Row {title:"Battery / charger";description:page.value(page.snapshot.batteryTemperatureC," °C")+" / "+page.value(page.snapshot.chargerTemperatureC," °C");arrow:false}
  Input {id:cpuWarning;placeholderText:"CPU warning (60–95 °C)";inputMethodHints:Qt.ImhDigitsOnly}
  Input {id:batteryWarning;placeholderText:"Battery warning (35–50 °C)";inputMethodHints:Qt.ImhDigitsOnly}
  Action {text:"Save thermal warnings";enabled:!Power.busy;onClicked:Power.configure({thermalWarningC:Number(cpuWarning.text),batteryWarningC:Number(batteryWarning.text)})}
  S.SettingsToggle {tokens:page.tokens;Layout.fillWidth:true;title:"Use Saver on thermal warning";description:"Optional supported frequency limits; kernel safety remains enabled";checked:page.config.thermalAction==="power-saver";onRequested:wanted=>Power.configure({thermalAction:wanted?"power-saver":"notify"})}
 }
 Card {visible:page.section==="overview"||page.section==="history"
  Row {title:"Measured signals";description:"Battery terminal: "+page.value(page.snapshot.batteryPowerW," W",3)+"\nUSB input estimate: "+page.value(page.snapshot.usbInputPowerW," W",3)+"\nTotal-device power: Unavailable";arrow:false}
  Status {text:"History: "+Power.history.length+" aggregated points · gaps mean unavailable data"}
  RowLayout {Layout.fillWidth:true;Repeater {model:[{hours:1,title:"Hour"},{hours:24,title:"Day"},{hours:168,title:"Week"},{hours:720,title:"Month"}];delegate:S.SettingsAction {required property var modelData;tokens:page.tokens;Layout.fillWidth:true;text:modelData.title;onClicked:Power.loadHistory(modelData.hours)}}}
  S.SettingsSelect {tokens:page.tokens;Layout.fillWidth:true;title:"History metric";model:[{id:"capacity",label:"Battery (%)"},{id:"batteryPowerW",label:"Battery terminal power (W)"},{id:"usbInputPowerW",label:"USB input estimate (W)"},{id:"batteryTemperatureC",label:"Battery temperature (°C)"},{id:"cpuTemperatureC",label:"CPU temperature (°C)"}];textRole:"label";currentIndex:Math.max(0,model.findIndex(x=>x.id===page.metric));onActivated:index=>{page.metric=model[index].id;plot.requestPaint()}}
  Canvas {id:plot;objectName:"powerHistoryGraph";Layout.fillWidth:true;Layout.preferredHeight:160
   onPaint:{let c=getContext("2d");c.reset();c.fillStyle=page.tokens.soft;c.fillRect(0,0,width,height);let rows=Power.history;let valid=rows.filter(r=>typeof r[page.metric]==="number"&&isFinite(r[page.metric]));c.fillStyle=page.tokens.muted;c.font="12px sans-serif";if(valid.length<2){c.fillText("Waiting for enough measured samples",12,26);return}let lo=Math.min.apply(null,valid.map(r=>r[page.metric]));let hi=Math.max.apply(null,valid.map(r=>r[page.metric]));if(hi===lo){hi+=1;lo-=1}let first=rows[0].timestamp,last=rows[rows.length-1].timestamp;c.fillText(hi.toFixed(1),8,16);c.fillText(lo.toFixed(1),8,height-8);c.strokeStyle=page.tokens.accent;c.lineWidth=2;c.beginPath();let started=false;for(let r of rows){if(typeof r[page.metric]!=="number"){started=false;continue}let x=38+(width-50)*(r.timestamp-first)/Math.max(1,last-first);let y=18+(height-38)*(hi-r[page.metric])/(hi-lo);if(started)c.lineTo(x,y);else c.moveTo(x,y);started=true}c.stroke()}
   onWidthChanged:requestPaint()
   Connections {target:Power;function onChanged(){plot.requestPaint()}}
  }
  Status {text:"USB input and battery measurements are separate. No exact per-application energy or total device consumption is claimed."}
 }
 Card {visible:page.section==="advanced"
  Repeater {model:(page.snapshot.controls||{}).cpu||[];delegate:Row {required property var modelData;title:modelData.id+" · CPU "+modelData.cores;description:"Governor: "+modelData.governor+"\nFrequency: "+page.value(modelData.currentKHz/1000," MHz")+"\nLimits: "+page.value(modelData.minKHz/1000," MHz")+" – "+page.value(modelData.maxKHz/1000," MHz")+"\nAvailable governors: "+modelData.governors.join(", ");arrow:false}}
  Row {title:"GPU";description:((page.snapshot.controls||{}).gpu||{}).governor||"Unavailable";arrow:false}
  Action {text:page.technical?"Hide technical evidence":"Show technical evidence";onClicked:page.technical=!page.technical}
  UI.DataView {tokens:page.tokens;Layout.fillWidth:true;visible:page.technical;value:({controls:page.snapshot.controls,thermalZones:page.snapshot.thermalZones,coolingDevices:page.snapshot.coolingDevices,registry:page.snapshot.hardwareRegistry,suspend:page.snapshot.suspend,display:Power.session})}
  Status {text:"Per-process CPU, RSS and I/O are resource-impact indicators, not validated per-application electrical power. No competing power manager or vendor safety control is installed."}
  Action {text:"Inspect my applications' resource impact";enabled:!Power.busy;onClicked:Power.inspectProcesses()}
  Repeater {model:Power.processes;delegate:Row {required property var modelData;title:modelData.name+" · PID "+modelData.pid;description:"CPU time: "+page.value(modelData.cpuSeconds," s")+" · CPU: "+page.value(modelData.cpuPercentOfOneCore,"%")+"\nMemory: "+page.value(modelData.rssBytes===null?null:modelData.rssBytes/1048576," MiB")+"\nI/O read: "+page.value(modelData.ioReadBytes," B",0)+" · Written: "+page.value(modelData.ioWriteBytes," B",0);arrow:false}}
 }
 Action {text:Power.busy?"Reading power state…":"Refresh power information";enabled:!Power.busy;onClicked:Power.refresh()}
 Status {text:Power.message||Power.state.message||"Read-only measurements and verified power controls"}
}
