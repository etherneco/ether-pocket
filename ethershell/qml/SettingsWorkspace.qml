import QtQuick
import "../ethernotifications" as NotificationUi
import QtQuick.Controls
import QtQuick.Layouts
import "settings" as S
import "../ethershare" as Sharing
import "../etherhardware" as HardwareUi
import "../etherpower" as PowerUi
import "../etheraudio" as AudioUi
import "../ethercamera" as CameraUi
import "../etherfingerprint" as FingerprintUi
import "../etherlocation" as LocationUi
import "../etherupdate" as UpdateUi
import "../ethersensors" as SensorsUi
import "../etherbackup" as BackupUi
import "../etherphone" as PhoneUi
import "../etherlock" as LockUi
import "../diagnostics.js" as Diagnostics

Item {
 id:workspace;objectName:"settingsWorkspace"
 property string route:"home"
 property string search:""
 property string appSearch:""
 property int appLimit:40
 property string pendingFocus:""
 signal closed();signal openMobile(string section);signal openStore();signal keyboardRequested()
 S.SettingsTheme {id:theme;uiScale:workspace.width>0?workspace.mapToItem(null,1,0).x-workspace.mapToItem(null,0,0).x:1}
 readonly property var categories:[
  {id:"location",title:"Location",icon:"icon:location",description:"GNSS, privacy, offline maps, history and geofences"},
  {id:"network",title:"Network & Internet",icon:"icon:wifi",description:"Wi-Fi, mobile network, SIM, VPN and DNS"},
  {id:"devices",title:"Connected Devices",icon:"icon:bluetooth",description:"Bluetooth, USB, displays and audio"},
  {id:"appearance",title:"Display & Appearance",icon:"icon:sun",description:"Brightness, theme, wallpaper and scaling"},
  {id:"sound",title:"Sound & Notifications",icon:"icon:volume",description:"Volume, audio routing and notifications"},
  {id:"power",title:"Battery & Power",icon:"icon:battery",description:"Battery, charging and power preferences"},
  {id:"storage",title:"Storage",icon:"icon:storage",description:"Capacity, mounted volumes and files"},
  {id:"security",title:"Security & Privacy",icon:"icon:lock",description:"Screen lock, authentication and trust"},
  {id:"apps",title:"Applications",icon:"icon:apps",description:"Installed apps, defaults, startup and updates"},
  {id:"input",title:"Keyboard & Input",icon:"icon:keyboard",description:"EtherKeyboard, language and gestures"},
  {id:"system",title:"System",icon:"icon:info",description:"Device, Debian, memory, services and recovery"},
  {id:"etherneco",title:"Etherneco",icon:"icon:home",description:"EtherShell, EtherAIR and application distribution"}
 ]
 readonly property var settingsIndex:[
  {route:"fingerprints",title:"Fingerprints",description:"Fingerprint manager, enrollment availability, security and diagnostics"},
  {route:"sensors",title:"Sensors & Motion",description:"Sensor availability, motion, calibration, privacy and diagnostics"},
  {route:"backup",title:"Backup & Restore",description:"Encrypted backup, verification, recovery points and isolated restore"},
  {route:"updates",title:"Software Updates",description:"System updates, channels, verification, history and recovery"},
  {route:"location",title:"Location",description:"GNSS, satellites, precise and approximate permissions, offline maps and geofences"},
  {route:"calls",title:"Calls",description:"Calling, VoLTE, call audio, privacy and diagnostics"},
  {route:"camera",title:"Camera",description:"Camera devices, capture support, photography, video, privacy and diagnostics"},
  {route:"hardware",title:"Hardware & Drivers",description:"System, CPU, GPU, memory, diagnostics, firmware, capabilities, cameras and sensors"},
  {route:"wifi",title:"Wi-Fi",description:"Wireless networks, saved connections, IP, DNS and gateway",key:"wifi-radio"},
  {route:"sms",title:"SMS & Messaging",description:"Messages, offline dictation, local AI and speech playback"},
  {route:"sharing",title:"Internet Sharing",description:"EtherShare, USB tethering, hotspot, Ethernet and routing"},
  {route:"mobile",title:"Mobile Network",description:"Cellular data, APN, LTE, roaming and usage"},
  {route:"sim",title:"SIM Cards",description:"SIM PIN, PUK, operator and slot"},
  {route:"bluetooth",title:"Bluetooth",description:"Pair, connect, discover and forget devices"},
  {route:"appearance",title:"Theme",description:"Display & Appearance, light, dark, automatic",key:"setting-theme"},
  {route:"appearance",title:"High contrast and animations",description:"Display & Appearance, contrast, motion, window previews and effects",key:"setting-effects"},
  {route:"appearance",title:"Accent colour and glass opacity",description:"Display & Appearance, transparency, blue, violet, rose",key:"setting-wallpaper"},
  {route:"appearance",title:"Brightness",description:"Display & Appearance, panel backlight",key:"setting-brightness"},
  {route:"appearance",title:"Font and interface scaling",description:"Display & Appearance, text size and scale",key:"setting-scale"},
  {route:"appearance",title:"Wallpaper",description:"Display & Appearance, image and gradient",key:"setting-wallpaper"},
  {route:"appearance",title:"External displays",description:"Display & Appearance, EtherAir, resolution, orientation",key:"setting-external"},
  {route:"sound",title:"Volume and output device",description:"Sound, microphone, speakers, audio routing",key:"setting-volume"},
  {route:"sound",title:"Notifications",description:"Sound, preferences and current notifications",key:"setting-notifications"},
  {route:"power",title:"Battery and sleep",description:"Power, charging, temperature, suspend and timeout"},
  {route:"storage",title:"Storage usage",description:"Files, space, mounted and removable volumes"},
  {route:"security",title:"Screen lock and authentication",description:"Security, privacy, permissions, certificates and trusted devices"},
  {route:"apps",title:"Installed applications",description:"Apps, defaults, startup, packages and updates"},
  {route:"input",title:"Touch keyboard",description:"Keyboard & Input, EtherKeyboard, physical keyboard and mouse",key:"setting-keyboard"},
  {route:"input",title:"Keyboard size and terminal font",description:"Keyboard & Input, keyboard scaling, automatic keyboard and terminal text",key:"setting-keyboard"},
  {route:"input",title:"Keyboard language",description:"Keyboard & Input, EN English, PL Polski, layouts",key:"setting-language"},
  {route:"input",title:"Dock and gestures",description:"Keyboard & Input, back swipe, compact dock and sidebar",key:"setting-gestures"},
  {route:"system",title:"Device information",description:"System, CPU, memory, kernel, Debian and date"},
  {route:"system",title:"Services and logs",description:"System, developer options, diagnostics and recovery",key:"setting-services"},
  {route:"network",title:"Hotspot, VPN, Proxy and DNS",description:"Network & Internet, existing provider capability",key:"setting-network-advanced"},
  {route:"etherneco",title:"Etherneco integrations",description:"EtherPocket, EtherAIR, EtherRemote, EtherMCP, EtherTrust, EtherFleet and Distributor"}
 ]
 readonly property var results:search.trim()?settingsIndex.concat(categories.map(c=>({route:c.id,title:c.title,description:c.description}))).filter(s=>(s.title+" "+s.description).toLowerCase().indexOf(search.trim().toLowerCase())>=0):[]
 function go(destination,key){
  if(destination==="mobile"||destination==="sim"){openMobile(destination==="sim"?"SIM Cards":"Mobile Data");return}
  pendingFocus=key||"";route=destination;Core.inspectSettings(destination);Qt.callLater(focusPending)
 }
 function focusPending(){
  if(!pendingFocus||!content.item)return
  function find(item){if(item.objectName===workspace.pendingFocus)return item;let all=item.children||[];for(let i=0;i<all.length;i++){let hit=find(all[i]);if(hit)return hit}return null}
  let hit=find(content.item);if(hit){hit.forceActiveFocus();let p=hit.mapToItem(content.item,0,0);page.contentItem.contentY=Math.max(0,Math.min(page.contentItem.contentHeight-page.height,p.y-12));pendingFocus=""}
 }
 function back(){if(route==="home")closed();else if(route==="fingerprints")go("security");else if(route==="camera")go("apps");else if(route==="updates"||route==="backup"||route==="sensors")go("system");else if(route==="hardware")go("system");else if(route==="calls"||route==="wifi"||route==="bluetooth"||route==="sharing")go("network");else go("home")}
 function note(title,message){notice.title=title;noticeText.text=message;notice.open()}
 function confirm(message,action){confirmText.text=message;confirmation.action=action;confirmation.open()}
 function bytes(v){let n=Number(v||0);return n>=1e9?(n/1e9).toFixed(1)+" GB":n>=1e6?(n/1e6).toFixed(1)+" MB":n+" B"}
 function status(id){
  if(id==="network")return (Core.networks.find(n=>n.active)||{}).ssid||((Mobile.status.operator||"Mobile")+" · "+(Mobile.status.state||"Unavailable"))
  if(id==="devices")return Core.telemetry.bluetoothConnections+" Bluetooth connected"
  if(id==="power")return (Core.telemetry.battery||"Unavailable")+"% · "+(Core.telemetry.charging||"Unknown")
  return ""
 }
 Component.onCompleted:Core.inspectSettings(route)
 Rectangle {anchors.fill:parent;color:theme.background}
 ColumnLayout {
  anchors.fill:parent;anchors.margins:theme.padding;spacing:theme.gap
  S.SettingsHeader {tokens:theme;title:workspace.route==="fingerprints"?"Fingerprints":workspace.route==="home"?"Settings":workspace.route==="wifi"?"Wi-Fi":workspace.route==="bluetooth"?"Bluetooth":workspace.route==="calls"?"Calls":workspace.route==="sms"?"SMS & Messaging":workspace.route==="sharing"?"Internet Sharing":workspace.route==="sensors"?"Sensors & Motion":workspace.route==="backup"?"Backup & Restore":workspace.route==="updates"?"Software Updates":workspace.route==="location"?"Location":workspace.route==="camera"?"Camera":workspace.route==="hardware"?"Hardware & Drivers":(workspace.categories.find(c=>c.id===workspace.route)||{}).title||"Settings";subtitle:"EtherPocket";onBack:workspace.back();onMore:actions.open()}
  S.SettingsSearch {id:searchField;objectName:"settingsSearch";tokens:theme;Layout.fillWidth:true;visible:workspace.route==="home";text:workspace.search;onTextEdited:workspace.search=text;onKeyboardRequested:workspace.keyboardRequested()}
  S.SettingsPage {
   id:page;objectName:"settingsPageScroll";tokens:theme;Layout.fillWidth:true;Layout.fillHeight:true
   Loader {id:content;width:Math.min(page.availableWidth,900);x:(page.availableWidth-width)/2;sourceComponent:workspace.search.trim()&&workspace.route==="home"?searchResults:workspace.route==="fingerprints"?fingerprintsPage:workspace.route==="home"?homePage:workspace.route==="calls"?callsPage:workspace.route==="sms"?smsPage:workspace.route==="sharing"?sharingPage:workspace.route==="sensors"?sensorsPage:workspace.route==="backup"?backupPage:workspace.route==="updates"?updatesPage:workspace.route==="location"?locationPage:workspace.route==="camera"?cameraPage:workspace.route==="hardware"?hardwarePage:workspace.route==="network"?networkPage:workspace.route==="wifi"?wifiPage:workspace.route==="bluetooth"?bluetoothPage:workspace.route==="devices"?devicesPage:workspace.route==="appearance"?appearancePage:workspace.route==="sound"?soundPage:workspace.route==="power"?powerPage:workspace.route==="storage"?storagePage:workspace.route==="security"?securityPage:workspace.route==="apps"?appsPage:workspace.route==="input"?inputPage:workspace.route==="system"?systemPage:ethernecoPage;onLoaded:{page.contentItem.contentY=0;Qt.callLater(workspace.focusPending)}}
  }
  S.SettingsStatus {tokens:theme;visible:!!Core.message;text:Core.message;Layout.fillWidth:true;maximumLineCount:3}
 }
 component Body:ColumnLayout {spacing:theme.sectionGap}
 component Section:S.SettingsSection {tokens:theme}
 component Row:S.SettingsRow {tokens:theme}
 component Toggle:S.SettingsToggle {tokens:theme}
 component Action:S.SettingsAction {tokens:theme;Layout.fillWidth:true}
 component Status:S.SettingsStatus {tokens:theme;Layout.fillWidth:true}
 component Title:Text {color:theme.ink;font.pixelSize:theme.sectionTitle*theme.fontScale;font.bold:true;wrapMode:Text.WordWrap;Layout.fillWidth:true}
 component Info:S.SettingsInfoCard {tokens:theme}
 component Input:S.SettingsInput {tokens:theme;Layout.fillWidth:true;onKeyboardRequested:workspace.keyboardRequested()}
 component Slider:S.SettingsSlider {tokens:theme}
 Component {id:homePage;GridLayout {columns:width>=700?2:1;columnSpacing:16;rowSpacing:16;
  Repeater {model:workspace.categories;delegate:Section {required property var modelData
   S.SettingsCategoryCard {tokens:theme;objectName:modelData.id==="network"?"networkInternetEntry":"category-"+modelData.id;title:modelData.title;description:workspace.status(modelData.id)||modelData.description;glyph:modelData.icon;onClicked:workspace.go(modelData.id)}
  }}
 }}
 Component {id:searchResults;Body {
  Status {text:workspace.results.length+" matching settings"}
  Section {Repeater {model:workspace.results;delegate:Row {required property var modelData;objectName:"search-"+(modelData.key||modelData.route);title:modelData.title;description:modelData.description;onClicked:{let chosen=modelData;workspace.search="";workspace.go(chosen.route,chosen.key)}}}}
  Info {visible:workspace.results.length===0;title:"No matching settings";description:"Search a setting name, category or keyword."}
 }}
 Component {id:smsPage;SmsSettingsPage {tokens:theme;onKeyboardRequested:workspace.keyboardRequested()}}
 Component {id:sharingPage;Sharing.SharePage {tokens:theme;onKeyboardRequested:workspace.keyboardRequested()}}
 Component {id:hardwarePage;HardwareUi.HardwarePage {tokens:theme;onKeyboardRequested:workspace.keyboardRequested()}}
 Component {id:updatesPage;UpdateUi.UpdatePage {tokens:theme;onKeyboardRequested:workspace.keyboardRequested()}}
 Component {id:backupPage;BackupUi.BackupPage {tokens:theme;onKeyboardRequested:workspace.keyboardRequested()}}
 Component {id:sensorsPage;SensorsUi.SensorsPage {tokens:theme}}
 Component {id:locationPage;LocationUi.LocationPage {tokens:theme}}
 Component {id:fingerprintsPage;FingerprintUi.FingerprintPage {tokens:theme}}
 Component {id:cameraPage;CameraUi.CameraPage {tokens:theme}}
 Component {id:callsPage;PhoneUi.CallSettings {control:Phone;tokens:theme}}
 Component {id:networkPage;Body {
  Section {
   Row {title:"Calls";description:"Calling, VoLTE, audio, privacy and diagnostics";onClicked:workspace.go("calls")}
   Row {title:"Wi-Fi";glyph:"icon:wifi";description:(Core.networks.find(n=>n.active)||{}).ssid||"No active network reported";onClicked:workspace.go("wifi")}
   Row {objectName:"mobileNetworkEntry";title:"Mobile Network";glyph:"icon:mobile";description:(Mobile.status.operator||"Unavailable")+" · "+(Mobile.status.state||"Unavailable");onClicked:workspace.openMobile("Mobile Data")}
   Row {objectName:"smsMessagingEntry";title:"SMS & Messaging";glyph:"icon:messages";description:"Messages, offline voice dictation and local AI";onClicked:workspace.go("sms")}
   Row {objectName:"internetSharingEntry";title:"Internet Sharing";glyph:"icon:sharing";description:(Share.state.active||[]).length?"EtherShare active":"USB, hotspot, Ethernet and routing";onClicked:workspace.go("sharing")}
   Row {title:"SIM Cards";glyph:"icon:sim";description:Mobile.status.simOperator||Mobile.status.sim||"Unavailable";onClicked:workspace.openMobile("SIM Cards")}
   Row {title:"Bluetooth";glyph:"icon:bluetooth";description:Core.telemetry.bluetoothPowered?Core.telemetry.bluetoothConnections+" connected":"Off or unavailable";onClicked:workspace.go("bluetooth")}
  }
  Section {objectName:"setting-network-advanced";Title {text:"Other network services"}
   Repeater {model:["VPN","Proxy","DNS"];delegate:Row {required property string modelData;title:modelData;description:modelData==="DNS"?"Current DNS in Wi-Fi and APN details":"No dedicated verified Settings provider";onClicked:workspace.note(modelData,modelData==="DNS"?"Wi-Fi details show effective DNS. Cellular per-profile DNS can be edited in APN settings. Advanced NetworkManager profiles remain available through the established editor.":"This Settings integration cannot configure this service safely. Existing NetworkManager profiles are preserved; use the established advanced connection editor where supported.")}}
   Row {title:"Network Diagnostics";description:"Read actual modem and packet-path evidence";onClicked:workspace.openMobile("Diagnostics")}
   Action {text:"Advanced NetworkManager editor";onClicked:Core.control("network-settings")}
  }
 }}
 Component {id:wifiPage;Body {
  Section {
   Toggle {objectName:"wifi-radio";title:"Wi-Fi";description:Core.settingsData.wifiRadio||"Reading radio state…";checked:Core.settingsData.wifiRadio==="enabled";onRequested:wanted=>workspace.confirm(wanted?"Enable Wi-Fi?":"Disable Wi-Fi? This may disconnect remote access.",function(){Core.control("wifi",wanted?"on":"off");Core.inspectSettings("wifi")})}
   Row {title:"Current network";description:(Core.networks.find(n=>n.active)||{}).ssid||"Not connected";value:((Core.networks.find(n=>n.active)||{}).signal||"—")+"%";onClicked:workspace.note("Connection details",(Core.settingsData.wifiDetails||[]).map(r=>r.title.replace("GENERAL.","")+": "+r.value).join("\n")||"No connection details reported")}
   Action {text:"Scan for networks";enabled:!Core.busy;onClicked:Core.control("scan")}
  }
  Section {Title {text:"Available networks"}
   Repeater {model:Core.networks;delegate:Row {required property var modelData;title:modelData.ssid;description:(modelData.active?"Connected · ":"")+modelData.security;value:modelData.signal+"%";onClicked:{wifiConnect.ssid=modelData.ssid;wifiPassword.text="";wifiConnect.open()}}}
   Status {visible:Core.networks.length===0;text:"No cached networks. Scan explicitly to refresh."}
  }
  Section {Title {text:"Saved networks"}
   Repeater {model:Core.settingsData.savedWifi||[];delegate:Row {required property var modelData;title:modelData.name;description:"Saved by NetworkManager";onClicked:{wifiProfile.profile=modelData;wifiProfile.open()}}}
  }
  Section {Title {text:"IP, gateway and DNS"}
   Repeater {model:Core.settingsData.wifiDetails||[];delegate:Row {required property var modelData;title:modelData.title.replace("GENERAL.","");description:modelData.value;arrow:false}}
   Status {text:Core.settingsData.wifiError||"Effective backend values; opening this page does not scan or reconnect."}
  }
 }}
 Component {id:bluetoothPage;Body {
  Section {
   Toggle {title:"Bluetooth";checked:!!((Core.bluetooth.adapters[0]||{}).Powered);enabled:Core.bluetooth.adapters.length>0;description:Core.bluetooth.adapters.length?"Existing EtherBluetooth provider":"No adapter exposed by BlueZ";onRequested:wanted=>workspace.confirm(wanted?"Enable Bluetooth?":"Turn Bluetooth off and disconnect its devices?",function(){Core.bluetooth.power(wanted)})}
   Action {text:(Core.bluetooth.adapters[0]||{}).Discovering?"Stop discovery":"Discover devices";enabled:!!((Core.bluetooth.adapters[0]||{}).Powered);onClicked:Core.bluetooth.scan(!((Core.bluetooth.adapters[0]||{}).Discovering))}
   Status {text:Core.bluetooth.error||"No scan starts automatically. Pairing requests appear here."}
  }
  Section {Title {text:"Devices"}
   Repeater {model:Core.bluetooth.devices;delegate:Row {required property var modelData;title:modelData.name;description:(modelData.Connected?"Connected":modelData.Paired?"Paired":"Available")+(modelData.RSSI!==undefined?" · "+modelData.RSSI+" dBm":"");onClicked:{btDevice.device=modelData;btDevice.open()}}}
   Status {visible:Core.bluetooth.devices.length===0;text:"No devices reported. Start discovery to find nearby devices."}
  }
  Action {text:"Connection diagnostics";onClicked:Core.bluetooth.diagnose()}
  Info {visible:!!Core.bluetooth.diagnosis.status;title:"Bluetooth diagnostics";description:Diagnostics.rows(Core.bluetooth.diagnosis).map(r=>r.label+": "+r.value).join("\n\n")}
 }}
 Component {id:devicesPage;Body {
  Section {
   Row {title:"Bluetooth devices";description:Core.telemetry.bluetoothConnections+" connected";onClicked:workspace.go("bluetooth")}
   Row {title:"USB and mounted devices";description:"Read actual block devices in Storage";onClicked:workspace.go("storage")}
   Row {title:"External displays / AR glasses";description:Pocket.external?"An external display is present":"No external display detected";onClicked:workspace.go("appearance","setting-external")}
   Row {title:"Input devices";description:"Touch, keyboard and mouse";onClicked:workspace.go("input")}
   Row {title:"Audio devices";description:"Outputs, microphones and routing";onClicked:workspace.go("sound")}
  }
  Info {title:"Input devices reported by X11";description:Core.settingsData.inputDevices||"Reading…"}
 }}
 Component {id:appearancePage;Body {
  Section {Title {text:"Display"}
   Slider {objectName:"setting-brightness";title:"Brightness";value:Number(Core.telemetry.brightness||0);from:1;to:100;suffix:"%";enabled:!!Core.telemetry.brightnessWritable;onMoved:value=>Power.setBrightness(Math.round(value))}
   Status {visible:!Core.telemetry.brightnessWritable;text:"This session has no writable panel backlight. Brightness is not simulated."}
   S.SettingsTabs {objectName:"setting-theme";tokens:theme;Layout.fillWidth:true;model:["Light","Dark","Automatic"];currentIndex:["light","dark","auto"].indexOf(Core.preferences.themeMode);onSelected:index=>Core.setting("themeMode",["light","dark","auto"][index])}
   Slider {objectName:"setting-scale";title:"Interface scale";from:.8;to:1.5;stepSize:.1;value:Core.preferences.scale;onMoved:value=>Core.setting("scale",value)}
   Slider {title:"Text size";from:.8;to:1.5;stepSize:.1;value:Core.preferences.fontScale;onMoved:value=>Core.setting("fontScale",value)}
   Slider {title:"Glass opacity";from:.65;to:1;stepSize:.05;value:Core.preferences.transparency;onMoved:value=>Core.setting("transparency",value)}
   Toggle {objectName:"setting-effects";title:"High contrast";checked:Core.preferences.highContrast;onRequested:wanted=>Core.setting("highContrast",wanted)}
   Toggle {title:"Animations";checked:Core.preferences.animations;onRequested:wanted=>Core.setting("animations",wanted)}
   Toggle {title:"Window previews";checked:Core.preferences.previews;onRequested:wanted=>Core.setting("previews",wanted)}
  }
  Section {objectName:"setting-wallpaper";Title {text:"Wallpaper and accent"}
   Input {id:wallpaper;placeholderText:"Local image path";text:Core.preferences.wallpaper;Accessible.name:"Wallpaper image path"}
   Action {text:"Apply wallpaper";onClicked:Core.setting("wallpaper",wallpaper.text)}
   Action {text:"Use gradient";onClicked:Core.setting("wallpaper","")}
   S.SettingsTabs {tokens:theme;Layout.fillWidth:true;model:["Blue","Ocean","Violet","Rose"];onSelected:index=>Core.setting("accent",["#087DFF","#008dba","#6557ce","#a53479"][index])}
  }
  Section {objectName:"setting-external";Title {text:"Displays and orientation"}
   Repeater {model:Core.displays;delegate:Row {required property var modelData;title:modelData.name;description:(modelData.connected?"Connected ":"Disconnected ")+modelData.detail;arrow:false}}
   S.SettingsSelect {tokens:theme;Layout.fillWidth:true;title:"Phone orientation";model:["Normal","Left","Right","Inverted"];onActivated:index=>workspace.confirm("Change phone orientation and its touchscreen mapping?",function(){Core.control("rotate",["normal","left","right","inverted"][index])})}
   Action {text:"Configure resolution / primary display";onClicked:Core.control("display-settings")}
   S.SettingsSelect {tokens:theme;Layout.fillWidth:true;title:"External desktop layout";model:["Extend","Mirror"];enabled:Pocket.external;onActivated:index=>workspace.confirm("Apply the existing EtherAir display layout?",function(){Core.control("display-profile",index===0?"extend":"mirror")})}
   Row {title:"Screen timeout and wake";description:"Managed by the existing power service";onClicked:workspace.go("power")}
  }
 }}
 Component {id:soundPage;Body {
  AudioUi.AudioPage {tokens:theme;Layout.fillWidth:true;onKeyboardRequested:workspace.keyboardRequested()}
  Section {objectName:"setting-notifications";Title {text:"Notifications"}
   Toggle {title:"Bluetooth notifications";checked:Core.bluetooth.notifications;onRequested:wanted=>Core.bluetooth.notifications=wanted}
   NotificationUi.NotificationSettings {Layout.fillWidth:true}
  }
 }}
 Component {id:powerPage;PowerUi.PowerPage {tokens:theme;onKeyboardRequested:workspace.keyboardRequested()}}
 Component {id:storagePage;Body {
  Info {title:"Internal storage";description:Core.settingsData.storage&&Core.settingsData.storage.valid?workspace.bytes(Core.settingsData.storage.available)+" available of "+workspace.bytes(Core.settingsData.storage.total)+" · "+Core.settingsData.storage.type:"Filesystem information unavailable"}
  Section {Title {text:"Block devices"}
   Repeater {model:Core.settingsData.volumes||[];delegate:Row {required property var modelData;title:modelData.name+" · "+workspace.bytes(modelData.size);description:(modelData.fstype||modelData.type)+" · "+((modelData.mountpoints||[]).filter(p=>!!p).join(", ")||"Not mounted");arrow:false}}
   Status {text:"Capacity and volumes are read from the filesystem and lsblk. No formatting, partition write or automatic cleanup is performed."}
   Action {text:"Manage files and removable media";onClicked:Core.control("files")}
  }
 }}
 Component {id:securityPage;Body {
  Section {Row {objectName:"fingerprintsEntry";title:"Fingerprints";glyph:"icon:lock";description:"Fingerprint unlock, enrollment availability and diagnostics";onClicked:workspace.go("fingerprints")}}
  LockUi.LockPage {tokens:theme;Layout.fillWidth:true}
  Section {Title {text:"Permissions & trust"}
   Row {title:"Application permissions";description:"Existing Unix and service permissions";onClicked:workspace.note("Application permissions","No system-wide application sandbox provider is integrated.")}
   Row {title:"Certificates";description:"Existing system trust store";onClicked:workspace.note("Certificates","No reviewed certificate editor is integrated.")}
   Row {title:"Trusted devices";description:"Bluetooth trust management";onClicked:workspace.go("bluetooth")}
  }
 }}
 Component {id:appsPage;Body {
  Section {Row {title:"Camera";description:"Camera hardware, photography, video, privacy and diagnostics";onClicked:workspace.go("camera")}}
  Section {Title {text:"Installed applications"}
   Input {placeholderText:"Filter applications";text:workspace.appSearch;onTextEdited:workspace.appSearch=text}
   Repeater {model:Core.apps.filter(a=>a.name.toLowerCase().indexOf(workspace.appSearch.toLowerCase())>=0).slice(0,workspace.appLimit);delegate:Row {required property var modelData;title:modelData.name;description:modelData.id;onClicked:{appDetails.app=modelData;appDetails.open()}}}
   Action {text:"Show more applications";visible:Core.apps.length>workspace.appLimit;onClicked:workspace.appLimit+=40}
  }
  Section {Title {text:"Defaults, startup and packages"}
   Status {text:"Default browser: "+(Core.settingsData.browser||"Reading…")}
   S.SettingsSelect {tokens:theme;Layout.fillWidth:true;title:"Default web browser";model:Core.apps.filter(a=>a.category.indexOf("WebBrowser")>=0);textRole:"name";currentIndex:Math.max(0,model.findIndex(a=>a.id===Core.settingsData.browser));enabled:model.length>0;onActivated:index=>Core.defaultBrowser(model[index].id)}
   Status {text:"Startup entries: "+(Core.settingsData.startupApps||[]).join(", ")}
   Action {text:"Application Distributor / updates";onClicked:workspace.openStore()}
   Action {text:"Edit startup preferences";enabled:!!Core.settingsData.startupEditorAvailable;onClicked:Core.control("startup-settings")}
   Status {text:"Other default-app and startup policies use established desktop tools. Per-app permission and package writes are not duplicated here."}
  }
 }}
 Component {id:inputPage;Body {
  Section {objectName:"setting-keyboard";Title {text:"EtherKeyboard"}
   Toggle {title:"Automatic touch keyboard";description:Core.physicalKeyboardConnected?"Physical keyboard connected; touch keyboard stays hidden":Core.keyboardFocusAvailable?"Opens in text fields when no physical keyboard is connected":"Opens in system fields; use the keyboard button for unsupported applications";checked:Core.preferences.autoKeyboard;onRequested:wanted=>Core.setting("autoKeyboard",wanted)}
   S.SettingsTabs {objectName:"setting-language";tokens:theme;Layout.fillWidth:true;model:["English","Polski"];currentIndex:Core.preferences.layout==="PL"?1:0;onSelected:index=>Core.setting("layout",index===1?"PL":"EN")}
   Slider {title:"Keyboard size";from:.85;to:1.2;stepSize:.05;value:Core.preferences.keyboardScale;onMoved:value=>Core.setting("keyboardScale",value)}
   Slider {title:"Terminal font";from:9;to:24;value:Core.preferences.terminalFontSize;onMoved:value=>Core.setting("terminalFontSize",Math.round(value))}
   Input {placeholderText:"Try the keyboard here";objectName:"settingsKeyboardTest"}
  }
  Section {objectName:"setting-gestures";Title {text:"Navigation and gestures"}
   Toggle {title:"Pocket Mode";checked:Pocket.enabled;onRequested:wanted=>Pocket.setEnabled(wanted)}
   Toggle {title:"Dock gestures";checked:Core.preferences.gestures;onRequested:wanted=>Core.setting("gestures",wanted)}
   Toggle {title:"Back swipe at dock edge";checked:Core.preferences.edgeBack;onRequested:wanted=>Core.setting("edgeBack",wanted)}
   Toggle {title:"Compact dock in fullscreen";checked:Core.preferences.dockAutoHide;onRequested:wanted=>Core.setting("dockAutoHide",wanted)}
   Toggle {title:"Pin sidebar in landscape";checked:Core.preferences.sidebarPinned;onRequested:wanted=>Core.setting("sidebarPinned",wanted)}
   Action {text:"Rotate dock button order";onClicked:{let a=Core.preferences.dockOrder.slice();a.push(a.shift());Core.setting("dockOrder",a)}}
  }
  Info {title:"Physical input devices";description:Core.settingsData.inputDevices||"Reading devices…"}
  Status {text:"Physical keyboard layouts, mouse tuning and touch sensitivity require a verified device provider; current touch behaviour is preserved."}
 }}
 Component {id:systemPage;Body {
  Section {Row {objectName:"hardwareDriversEntry";title:"Hardware & Drivers";description:"Hardware health, driver evidence and shared capabilities";onClicked:workspace.go("hardware")}}
  Section {Title {text:"About this device"}
   Repeater {model:Object.keys(Core.settingsData.system||{});delegate:Row {required property string modelData;title:modelData;description:String(Core.settingsData.system[modelData]);arrow:false}}
  }
  Section {objectName:"setting-services";Title {text:"Running services"}
   Status {text:Core.settingsData.services||"Reading system service state…"}
   Status {text:"Read-only listing. Service restart, raw logs, user/region administration have no reviewed in-page provider. Existing system configuration remains unchanged."}
   Action {text:"Refresh system information";onClicked:Core.inspectSettings("system")}
   Action {text:"Backup & Restore";onClicked:workspace.go("backup")}
   Action {text:"Software Updates";onClicked:workspace.go("updates")}
   Action {text:"Sensors & Motion";onClicked:workspace.go("sensors")}
   Action {text:"Modem diagnostics";onClicked:workspace.openMobile("Diagnostics")}
   Action {text:"Return to XFCE desktop";onClicked:workspace.confirm("Close EtherShell and return to the existing XFCE desktop?",function(){Core.control("quit")})}
  }
 }}
 Component {id:ethernecoPage;Body {
  Info {title:"EtherShell / EtherPocket";description:"Native Debian Settings. Existing services and configuration remain the source of truth."}
  Section {
   Row {title:"EtherAIR";description:Pocket.external?"External display detected":"No external display detected";onClicked:workspace.go("appearance","setting-external")}
   Repeater {model:["EtherRemote","EtherMCP","EtherTrust","EtherFleet"];delegate:Row {required property string modelData;title:modelData;description:Core.apps.some(a=>a.name.toLowerCase().indexOf(modelData.toLowerCase())>=0)?"Installed application available":"No verified Settings integration";onClicked:{workspace.appSearch=modelData;workspace.go("apps")}}}
   Row {title:"Application Distributor";description:Distributor.status;onClicked:workspace.openStore()}
  }
 }}
 S.SettingsBottomSheet {id:actions;tokens:theme;title:"Settings actions";contentItem:ColumnLayout {
  Action {text:"Settings home";onClicked:{actions.close();workspace.go("home")}}
  Action {text:"Refresh current page";onClicked:{actions.close();Core.discover();Core.refresh();Core.inspectSettings(workspace.route)}}
  Action {text:"Close settings";onClicked:{actions.close();workspace.closed()}}
 }}
 S.SettingsDialog {id:notice;tokens:theme;standardButtons:Dialog.Ok;contentItem:Status {id:noticeText}}
 S.SettingsDialog {id:confirmation;tokens:theme;title:"Confirm change";standardButtons:Dialog.Ok|Dialog.Cancel;property var action:null;contentItem:Status {id:confirmText} onAccepted:{let fn=action;action=null;if(fn)fn()} onRejected:action=null}
 S.SettingsDialog {id:wifiConnect;tokens:theme;property string ssid:"";title:ssid;standardButtons:Dialog.Ok|Dialog.Cancel;contentItem:ColumnLayout {Status {text:"Connect using NetworkManager. The current connection may change."}Input {id:wifiPassword;placeholderText:"Network password (blank for open/saved network)";echoMode:TextInput.Password;inputMethodHints:Qt.ImhSensitiveData|Qt.ImhNoPredictiveText}} onAccepted:{Core.connectWifi(ssid,wifiPassword.text);wifiPassword.text=""} onClosed:wifiPassword.text=""}
 S.SettingsBottomSheet {id:wifiProfile;tokens:theme;property var profile:({});title:profile.name||"Saved network";contentItem:ColumnLayout {
  Action {text:"Connect";onClicked:{let p=wifiProfile.profile;wifiProfile.close();workspace.confirm("Activate this saved Wi-Fi profile?",function(){Core.wifiProfileAction(p.uuid,"up")})}}
  Action {text:"Disconnect";onClicked:{let p=wifiProfile.profile;wifiProfile.close();workspace.confirm("Disconnect this Wi-Fi profile? Remote access may be interrupted.",function(){Core.wifiProfileAction(p.uuid,"down")})}}
  Action {text:"Forget network";destructive:true;onClicked:{let p=wifiProfile.profile;wifiProfile.close();workspace.confirm("Delete this saved network and its credentials?",function(){Core.wifiProfileAction(p.uuid,"delete")})}}
 }}
 S.SettingsBottomSheet {id:btDevice;tokens:theme;property var device:({});title:device.name||"Bluetooth device";contentItem:ColumnLayout {
  Status {text:(btDevice.device.Connected?"Connected":"Disconnected")+" · "+(btDevice.device.Paired?"Paired":"Not paired")}
  Repeater {model:["pair","connect","disconnect","trust","forget"];delegate:Action {required property string modelData;text:modelData==="forget"?"Forget device":modelData;onClicked:{let d=btDevice.device;let action=modelData;btDevice.close();workspace.confirm("Request Bluetooth "+action+" for "+d.name+"?",function(){Core.bluetooth.action(d.path,action,action==="trust"?"on":"")})}}}
 }}
 S.SettingsDialog {id:pairing;tokens:theme;title:"Bluetooth pairing";standardButtons:Dialog.Ok|Dialog.Cancel;contentItem:ColumnLayout {Status {text:Diagnostics.rows(Core.bluetooth.pairing).map(r=>r.label+": "+r.value).join("\n");textFormat:Text.PlainText}Input {id:pairCode;placeholderText:"Pairing code if requested";maximumLength:16}} onAccepted:Core.bluetooth.answer(true,pairCode.text);onRejected:Core.bluetooth.answer(false,"");onClosed:pairCode.text=""}
 Connections {target:Core.bluetooth;function onPairingChanged(){if(Object.keys(Core.bluetooth.pairing).length)pairing.open();else pairing.close()}}
 S.SettingsDialog {id:appDetails;tokens:theme;property var app:({});title:app.name||"Application";standardButtons:Dialog.Close;contentItem:ColumnLayout {Status {text:"Desktop ID: "+(appDetails.app.id||"Unavailable")}Action {text:"Open application";onClicked:{Core.launch(appDetails.app.id);appDetails.close()}}}}
}
