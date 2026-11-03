import QtQuick
import QtQuick.Layouts
import "../qml/settings" as S

ColumnLayout {
 id:page;objectName:"etherLocationPage";required property var tokens
 readonly property var state:LocationControl.state||({})
 readonly property var config:state.config||({})
 readonly property var management:LocationControl.management||({})
 spacing:tokens.sectionGap
 component Card:S.SettingsSection {tokens:page.tokens;Layout.fillWidth:true}
 component Row:S.SettingsRow {tokens:page.tokens;Layout.fillWidth:true;arrow:false}
 component Status:S.SettingsStatus {tokens:page.tokens;Layout.fillWidth:true}
 Status {visible:!page.state.ready;state:"warning";text:"EtherLocation service unavailable. No real device fix is implied."}
 Status {visible:!!LocationControl.message;text:LocationControl.message}
 Card {
  S.SettingsToggle {tokens:page.tokens;Layout.fillWidth:true;title:"Location";description:"GNSS runs only for authorised requests or a bounded diagnostic test.";checked:!!page.config.enabled;enabled:!!page.state.ready;onRequested:wanted=>LocationControl.configure({enabled:wanted})}
  Row {title:page.state.fixStatus||"Unavailable";description:(page.state.active?"GNSS active":"GNSS idle")+" · "+(page.state.provider||"No active provider")+" · "+(page.state.accuracy!==null&&page.state.accuracy!==undefined?"±"+Math.round(page.state.accuracy)+" m":"Accuracy unavailable")}
  Row {title:"Last update";description:page.state.lastUpdate?new Date(page.state.lastUpdate*1000).toLocaleString():"No real position received"}
  Row {title:"Active applications";description:(page.state.activeApplications||[]).join(", ")||"None"}
  S.SettingsSelect {tokens:page.tokens;Layout.fillWidth:true;title:"Accuracy and power";model:["High accuracy","Balanced","Battery saving"];currentIndex:Math.max(0,["high","balanced","saving"].indexOf(page.config.accuracy));onActivated:index=>LocationControl.configure({accuracy:["high","balanced","saving"][index]})}
  S.SettingsSelect {tokens:page.tokens;Layout.fillWidth:true;title:"Approximate location grid";model:["1 km","10 km","50 km"];currentIndex:Math.max(0,[1000,10000,50000].indexOf(page.config.grid));onActivated:index=>LocationControl.configure({grid:[1000,10000,50000][index]})}
 }
 Card {
  Row {title:"Application permissions";description:"Review while unlocked. Grants last for this service session. Background access requires the separate explicit action below. Ask every time grants one bounded session."}
  S.SettingsAction {tokens:page.tokens;Layout.fillWidth:true;text:"Refresh permissions, history and satellites";onClicked:LocationControl.review()}
  Repeater {model:page.management.requests||[];delegate:ColumnLayout {required property var modelData;Layout.fillWidth:true
   Row {title:modelData.app;description:"Requested "+modelData.options.precision+(modelData.options.background?" · background":" · while using")+(modelData.options.origin?" · "+modelData.options.origin:"")}
   S.SettingsAction {tokens:page.tokens;Layout.fillWidth:true;text:"Allow approximate while using";onClicked:LocationControl.resolve(modelData.token,"allow-while-using","approximate",false)}
   S.SettingsAction {tokens:page.tokens;Layout.fillWidth:true;text:"Allow precise while using";onClicked:LocationControl.resolve(modelData.token,"allow-while-using","precise",false)}
   S.SettingsAction {tokens:page.tokens;Layout.fillWidth:true;text:"Allow approximate once (ask every time)";onClicked:LocationControl.resolve(modelData.token,"ask-every-time","approximate",false)}
   S.SettingsAction {tokens:page.tokens;Layout.fillWidth:true;text:"Deny";onClicked:LocationControl.resolve(modelData.token,"deny","approximate",false)}
   S.SettingsAction {tokens:page.tokens;Layout.fillWidth:true;visible:modelData.options.background;text:"Explicitly authorise precise background use, including while locked";onClicked:LocationControl.resolve(modelData.token,"allow-while-using","precise",true)}
  }}
  Repeater {model:page.management.permissions||[];delegate:ColumnLayout {required property var modelData;Layout.fillWidth:true
   Row {title:modelData.app;description:modelData.policy+" · "+modelData.precision+(modelData.background?" · background authorised":" · foreground only")}
   S.SettingsAction {tokens:page.tokens;Layout.fillWidth:true;text:"Revoke "+modelData.app;onClicked:LocationControl.revoke(modelData.app,modelData.origin)}
  }}
  Row {title:"Permission history";description:(page.management.permissionHistory||[]).slice(-20).map(r=>new Date(r.timestamp*1000).toLocaleString()+" · "+r.app+" · "+r.policy+" · "+r.precision).join("\n")||"No decisions in this service session"}
 }
 Card {
  Row {title:"Local history";description:"Off by default. Never uploaded. Stores fresh fixes only during authorised use while unlocked; enabling history does not start GNSS."}
  S.SettingsToggle {tokens:page.tokens;Layout.fillWidth:true;title:"Record local location history";checked:!!page.config.history;onRequested:wanted=>LocationControl.configure({history:wanted})}
  S.SettingsSelect {tokens:page.tokens;Layout.fillWidth:true;title:"Retention";model:["1 day","7 days","30 days"];currentIndex:Math.max(0,[1,7,30].indexOf(page.config.retention));onActivated:index=>LocationControl.configure({retention:[1,7,30][index]})}
  S.SettingsAction {tokens:page.tokens;Layout.fillWidth:true;text:"Export GPX";onClicked:LocationControl.historyExport("GPX")}
  S.SettingsAction {tokens:page.tokens;Layout.fillWidth:true;text:"Export GeoJSON";onClicked:LocationControl.historyExport("GeoJSON")}
  S.SettingsAction {tokens:page.tokens;Layout.fillWidth:true;text:"Delete all history";onClicked:LocationControl.deleteHistory("all")}
  Repeater {model:(page.management.history||[]).slice(0,30);delegate:ColumnLayout {required property var modelData;Layout.fillWidth:true
   Row {title:new Date(modelData.timestamp*1000).toLocaleString();description:modelData.provider+" · ±"+Math.round(modelData.accuracy)+" m · "+modelData.latitude.toFixed(4)+", "+modelData.longitude.toFixed(4)}
   S.SettingsAction {tokens:page.tokens;Layout.fillWidth:true;text:"Delete this entry";onClicked:LocationControl.deleteHistory(JSON.stringify([modelData.id]))}
  }}
 }
 Card {
  Row {title:"Maps";description:"EtherMAP provides OSM maps, licensed offline regions, saved places, local tracks, GPX, optional consented IP fallback, search and routing. Device permissions remain on this Location page."}  S.SettingsAction {tokens:page.tokens;Layout.fillWidth:true;text:"Open EtherMAP";onClicked:Core.launch("ethermap.desktop")}
  Row {title:"Maps privacy and storage";description:"Open Maps settings for map style, offline storage, IP consent, track retention and background requests. Online routing requires a permitted configured provider; offline navigation is unavailable."}
 }
 Card {
  Row {title:"Local geofences";description:"Zones evaluate only fresh accurate fixes during authorised positioning. Two fixes at least 10 seconds apart establish a transition; initial presence is silent. Geofences do not start background tracking."}
  S.SettingsInput {id:zoneId;tokens:page.tokens;Layout.fillWidth:true;placeholderText:"Zone identifier · home"}
  S.SettingsInput {id:lat;tokens:page.tokens;Layout.fillWidth:true;placeholderText:"Latitude · User-supplied latitude"}
  S.SettingsInput {id:lon;tokens:page.tokens;Layout.fillWidth:true;placeholderText:"Longitude · User-supplied longitude"}
  S.SettingsInput {id:radius;tokens:page.tokens;Layout.fillWidth:true;placeholderText:"Radius (metres) · 200"}
  S.SettingsAction {tokens:page.tokens;Layout.fillWidth:true;text:"Save zone (60 second dwell)";onClicked:LocationControl.zone(zoneId.text,{latitude:Number(lat.text),longitude:Number(lon.text),radius:Number(radius.text),dwell:60,enabled:true})}
  Repeater {model:Object.keys(page.management.zones||{});delegate:ColumnLayout {required property string modelData;Layout.fillWidth:true
   Row {title:modelData;description:((page.management.zones||{})[modelData]||{}).radius+" m"}
   S.SettingsAction {tokens:page.tokens;Layout.fillWidth:true;text:"Delete zone";onClicked:LocationControl.deleteZone(modelData)}
   S.SettingsAction {tokens:page.tokens;Layout.fillWidth:true;text:((page.management.zones||{})[modelData]||{}).enabled?"Disable zone":"Enable zone";onClicked:{let z=Object.assign({},page.management.zones[modelData]);z.enabled=!z.enabled;LocationControl.zone(modelData,z)}}
  }}
 }
 Card {
  Row {title:"GNSS diagnostics";description:"Qualcomm LOC over QRTR node 0 · direct session-owned libqmi client. Internal GNSS is not operational until a real fix is verified. No modem firmware or Android partitions are changed."}  S.SettingsSelect {tokens:page.tokens;Layout.fillWidth:true;title:"Offline backend (disable location first)";model:["Internal Qualcomm LOC","Existing local gpsd receiver"];enabled:!page.config.enabled;currentIndex:page.config.backend==="gpsd"?1:0;onActivated:index=>LocationControl.configure({backend:index===1?"gpsd":"qualcomm-loc",networkAuthorized:false})}  S.SettingsAction {tokens:page.tokens;Layout.fillWidth:true;text:"Authorise online positioning through existing GeoClue";enabled:!page.config.enabled;onClicked:LocationControl.configure({backend:"geoclue",networkAuthorized:true})}  Status {text:"GeoClue may upload Wi-Fi/cellular observations to its configured providers. Selecting it explicitly authorises those requests. It is never selected by default."}  S.SettingsAction {tokens:page.tokens;Layout.fillWidth:true;text:"Authorise GeoClue fallback alongside GNSS";enabled:!page.config.enabled&&page.config.backend!=="geoclue";onClicked:LocationControl.configure({networkAuthorized:true})}  S.SettingsAction {tokens:page.tokens;Layout.fillWidth:true;text:"Disable online network positioning";enabled:!page.config.enabled;onClicked:LocationControl.configure({networkAuthorized:false,backend:page.config.backend==="geoclue"?"qualcomm-loc":page.config.backend})}  Row {title:"Network fallback";description:page.state.networkFallbackState||"Disabled"}
  Row {title:"Satellite visibility";description:page.state.satellitesVisible===null||page.state.satellitesVisible===undefined?"Not reported":String(page.state.satellitesVisible)+" reported; used-in-fix count unavailable"}  Row {title:"Position diagnostics";description:page.management.location?((page.management.location.kind==="live"?"Live":"Last-known")+" · "+page.management.location.fixType+"\n"+page.management.location.latitude.toFixed(6)+", "+page.management.location.longitude.toFixed(6)+" · ±"+Math.round(page.management.location.accuracy)+" m\n"+new Date(page.management.location.timestamp*1000).toLocaleString()+" · "+Math.round(page.management.location.age)+" s old"):"No real position reported. Refresh diagnostics while unlocked."}
  Repeater {model:page.management.satellites||[];delegate:Row {required property var modelData;title:(modelData.constellation||"Unknown constellation")+" · "+(modelData.id===undefined?"ID unavailable":modelData.id);description:modelData.signal===undefined?"Signal unavailable":modelData.signal+" dB-Hz"}}
  Row {title:"Time to first fix";description:page.state.ttff===null||page.state.ttff===undefined?"No verified fix":page.state.ttff+" seconds"}
  S.SettingsAction {tokens:page.tokens;Layout.fillWidth:true;text:"Test GNSS for 90 seconds";enabled:!!page.config.enabled&&!page.state.active;onClicked:LocationControl.testGnss()}
  S.SettingsAction {tokens:page.tokens;Layout.fillWidth:true;text:"Export redacted diagnostics";onClicked:LocationControl.diagnostics(false)}
  S.SettingsAction {tokens:page.tokens;Layout.fillWidth:true;text:"Export diagnostics including precise last-known location";onClicked:LocationControl.diagnostics(true)}
  Status {visible:!!page.state.lastError;state:"warning";text:page.state.lastError||""}
  Row {title:"Network positioning";description:page.state.networkProvider||"Disabled"}
  Row {title:"Security boundary";description:"Backend checks the unique D-Bus sender, executable identity, permission, foreground window and lock state. Same-user X11 applications can access processes and hardware directly; strong isolation requires a sandbox/portal deployment."}
 }
}
