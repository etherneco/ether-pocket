import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import "../qml/settings" as S

ColumnLayout {
 id:page;objectName:"etherAudioPage";required property var tokens
 signal keyboardRequested()
 property string section:"output"
 property string pendingTest:""
 readonly property var state:AudioControl.state||({})
 readonly property var config:state.config||({})
 readonly property var sections:["output","input","volume","routing","applications","advanced"]
 spacing:tokens.sectionGap
 function choose(name){section=name;Qt.callLater(function(){let p=page.parent;while(p){if(p.contentY!==undefined){p.contentY=0;break}p=p.parent}})}
 component Card:S.SettingsSection {tokens:page.tokens;Layout.fillWidth:true}
 component Row:S.SettingsRow {tokens:page.tokens;Layout.fillWidth:true}
 component Status:S.SettingsStatus {tokens:page.tokens;Layout.fillWidth:true}
 component Action:S.SettingsAction {tokens:page.tokens;Layout.fillWidth:true}
 component Level:S.SettingsSlider {tokens:page.tokens;Layout.fillWidth:true;suffix:"%"}
 Status {visible:!page.state.ready;state:"warning";text:page.state.message||"EtherAudio is unavailable in this session"}
 Status {visible:!!AudioControl.message;text:AudioControl.message}
 Status {visible:!!page.state.recording;state:"warning";text:"Microphone in use · "+(page.state.recordingStreams||[]).map(r=>r.application||"Unknown application").join(", ")}
 S.SettingsSelect {tokens:page.tokens;Layout.fillWidth:true;title:"Sound & Notifications";model:["Output","Input","Volume","Audio Routing","Applications","Advanced"];currentIndex:page.sections.indexOf(page.section);onActivated:index=>page.choose(page.sections[index])}
 Card {visible:page.section==="output"
  S.SettingsSelect {tokens:page.tokens;Layout.fillWidth:true;title:"Output device";model:page.state.sinks||[];textRole:"description";currentIndex:model.findIndex(d=>d.name===page.state["default-sink"]);enabled:page.state.ready&&!AudioControl.busy;onActivated:index=>AudioControl.command("select","sink",{name:model[index].name})}
  Repeater {model:page.state.sinks||[];delegate:ColumnLayout {required property var modelData;Layout.fillWidth:true
   Row {title:modelData.description||modelData.name;description:modelData.state;arrow:false}
   Level {title:"Output volume";value:modelData.percent||0;onMoved:value=>{outputVolume.requested=Math.round(value);outputVolume.restart()}}
   Timer {id:outputVolume;property int requested:0;interval:200;onTriggered:AudioControl.command("volume","sink",{id:modelData.index,percent:requested})}
   S.SettingsToggle {tokens:page.tokens;Layout.fillWidth:true;title:"Mute output";checked:!!modelData.mute;onRequested:wanted=>AudioControl.command("mute","sink",{id:modelData.index,muted:wanted})}
  }}
  Action {text:"Play quiet test tone";enabled:page.state.ready&&!AudioControl.busy;onClicked:{page.pendingTest="playback";testConfirm.open()}}
  RowLayout {Layout.fillWidth:true
   Action {text:"I heard it";onClicked:AudioControl.command("result","playback",{result:"heard"})}
   Action {text:"No sound";onClicked:AudioControl.command("result","playback",{result:"not-heard"})}
  }
  Status {text:"Earpiece: "+((page.state.earpiece||{}).error||"Not verified")+"\nUSB and Bluetooth devices appear when the existing server exposes them. Analogue USB-C adapters and HFP call audio require separate validation."}
 }
 Card {visible:page.section==="input"
  S.SettingsSelect {tokens:page.tokens;Layout.fillWidth:true;title:"Microphone";model:page.state.sources||[];textRole:"description";currentIndex:model.findIndex(d=>d.name===page.state["default-source"]);enabled:page.state.ready&&!AudioControl.busy;onActivated:index=>AudioControl.command("select","source",{name:model[index].name})}
  Repeater {model:page.state.sources||[];delegate:ColumnLayout {required property var modelData;Layout.fillWidth:true
   Level {title:modelData.description||modelData.name;value:modelData.percent||0;onMoved:value=>{inputVolume.requested=Math.round(value);inputVolume.restart()}}
   Timer {id:inputVolume;property int requested:0;interval:200;onTriggered:AudioControl.command("volume","source",{id:modelData.index,percent:requested})}
   S.SettingsToggle {tokens:page.tokens;Layout.fillWidth:true;title:"Mute microphone";checked:!!modelData.mute;onRequested:wanted=>AudioControl.command("mute","source",{id:modelData.index,muted:wanted})}
  }}
  S.SettingsToggle {tokens:page.tokens;Layout.fillWidth:true;title:"Block managed microphone requests";checked:page.config.microphonePolicy==="deny";onRequested:wanted=>AudioControl.command("configure","",{microphonePolicy:wanted?"deny":"ask-each-time"})}
  Status {text:"Test input level: "+Math.round(AudioControl.level*100)+"% · sampled only during the explicit three-second test"}
  Action {text:"Record three-second microphone test";enabled:page.state.ready&&!AudioControl.busy;onClicked:{page.pendingTest="microphone";testConfirm.open()}}
  Action {text:"Play test sample";enabled:AudioControl.sampleAvailable;onClicked:AudioControl.playSample()}
  Action {text:"Delete test sample";enabled:AudioControl.sampleAvailable;onClicked:AudioControl.deleteSample()}
  Status {text:page.state.privacy||"Direct ALSA/Pulse access follows existing Unix permissions."}
 }
 Card {visible:page.section==="volume"
  Repeater {model:["media","call","ringtone","notification","alarm"];delegate:ColumnLayout {required property string modelData;Layout.fillWidth:true
   Level {title:modelData;value:(page.config.categories||{})[modelData]||0;enabled:page.state.ready;onMoved:value=>{categoryVolume.requested=Math.round(value);categoryVolume.restart()}}
   Timer {id:categoryVolume;property int requested:0;interval:200;onTriggered:AudioControl.command("category",modelData,{percent:requested})}
  }}
  Status {text:"Logical categories control real software streams by their backend media role. They are not independent hardware gain controls. Call volume does not certify modem call audio."}
 }
 Card {visible:page.section==="routing"
  S.SettingsToggle {tokens:page.tokens;Layout.fillWidth:true;title:"Automatic device selection";checked:!!page.config.automatic;onRequested:wanted=>AudioControl.command("configure","",{automatic:wanted})}
  Status {text:"Manual selection is remembered while that endpoint is available. Otherwise compatible Bluetooth/USB outputs are preferred, with speaker fallback. Active calls and microphone capture protect routes. External display connection preserves the current audio policy."}
  Status {visible:!!page.state.routeError;text:page.state.routeError||"";state:"warning"}
  Row {title:"Preferred output";description:page.config.preferredOutput||"Automatic";arrow:false}
  Row {title:"Preferred microphone";description:page.config.preferredInput||"Existing server default";arrow:false}
  Action {text:"Clear manual preferences";onClicked:AudioControl.command("configure","",{preferredOutput:"",preferredInput:""})}
  Status {text:"Voice calls: "+((page.state.callAudio||{}).error||"Not validated")}
 }
 Card {visible:page.section==="applications"
  Status {text:"Active playback streams. Application names come from the audio backend; unknown attribution stays unknown."}
  Repeater {model:page.state["sink-inputs"]||[];delegate:ColumnLayout {required property var modelData;Layout.fillWidth:true
   Row {title:modelData.application||"Unknown application";description:(modelData.category||"media")+" · "+(modelData.corked?"Paused":"Active");arrow:false}
   Level {title:"Stream volume";value:modelData.percent||0;onMoved:value=>{streamVolume.requested=Math.round(value);streamVolume.restart()}}
   Timer {id:streamVolume;property int requested:0;interval:200;onTriggered:AudioControl.command("volume","sink-input",{id:modelData.index,percent:requested})}
   S.SettingsToggle {tokens:page.tokens;Layout.fillWidth:true;title:"Mute stream";checked:!!modelData.mute;onRequested:wanted=>AudioControl.command("mute","sink-input",{id:modelData.index,muted:wanted})}
   S.SettingsSelect {tokens:page.tokens;Layout.fillWidth:true;title:"Stream output";model:page.state.sinks||[];textRole:"description";currentIndex:model.findIndex(d=>d.index===modelData.sink);onActivated:index=>AudioControl.command("move","",{stream:modelData.index,sink:model[index].name})}
  }}
  Repeater {model:page.state.recordingStreams||[];delegate:Row {required property var modelData;title:modelData.application||"Unknown recording application";description:"Recording · source "+modelData.source;arrow:false}}
  Status {text:page.state.focusPolicy||"No focus provider available"}
 }
 Card {visible:page.section==="advanced"
  Action {text:"Refresh audio state";onClicked:AudioControl.refresh()}
  Status {text:"Existing PipeWire/WirePlumber remain the audio server and hardware routing owner. EtherAudio uses their Pulse protocol; no second audio server is started."}
  Status {text:Object.entries((page.state.backendDiagnostics||{}).services||{}).map(r=>r[0]+": "+r[1]).join("\n")}
  Status {text:(page.state.backendDiagnostics||{}).alsaCards||"ALSA card metadata unavailable"}
  Row {title:"ALSA PCM interfaces";description:(page.state.backendDiagnostics||{}).alsaPcm||"Unavailable";onClicked:Core.control("audio-settings")}
  Action {text:"Bluetooth devices and audio profiles";onClicked:Core.control("bluetooth-settings")}
  Repeater {model:page.state.cards||[];delegate:Row {required property var modelData;title:modelData.name;description:"Driver: "+modelData.driver+"\nActive profile: "+modelData.active_profile+"\nProfiles: "+Object.keys(modelData.profiles||{}).join(", ");arrow:false}}
  Status {text:"Qualcomm: sm8150-asoc-snd / WCD934x Tavil, TFA9874 amplifiers; existing validated UCM speaker/microphone routes. No calibration, amplifier gains or DSP firmware is rewritten."}
  Repeater {model:page.state.diagnostics||[];delegate:Row {required property var modelData;title:modelData.kind+" · "+modelData.result;description:new Date(modelData.timestamp*1000).toLocaleString();arrow:false}}
 }
 S.SettingsDialog {id:testConfirm;tokens:page.tokens;title:page.pendingTest==="microphone"?"Record microphone?":"Play test tone?";standardButtons:Dialog.Ok|Dialog.Cancel
  contentItem:S.SettingsStatus {tokens:page.tokens;text:page.pendingTest==="microphone"?"Record three seconds now? The private sample can be played back and is deleted after one minute or on exit.":"Play a quiet half-second tone through the selected output? Check your current output volume first."}
  onAccepted:if(page.pendingTest==="microphone")AudioControl.recordTest();else AudioControl.command("play-test",page.state["default-sink"]||"",{consent:true})
 }
}
