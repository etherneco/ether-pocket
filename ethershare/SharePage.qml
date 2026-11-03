import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import "../qml/settings" as S

ColumnLayout {
 id:page
 required property var tokens
 signal keyboardRequested()
 readonly property var snapshot:Share.state
 readonly property var config:snapshot.config||({})
 readonly property var active:snapshot.active||[]
 readonly property var interfaces:snapshot.interfaces||[]
 property bool editorLoaded:false
 spacing:tokens.sectionGap
 function candidates(kind){return interfaces.filter(x=>x.kind===kind)}
 function activeMethod(method){return active.find(x=>x.method===method)}
 function first(kind){let x=candidates(kind);return x.length?x[0].interface:""}
 function bytes(v){return v>1048576?(v/1048576).toFixed(1)+" MB":(v/1024).toFixed(1)+" KB"}
 function begin(method,iface){
  if(method==="hotspot"&&(interfaces.find(x=>x.interface===iface)||{}).addresses?.length){confirm.method=method;confirm.iface=iface;confirm.open()}
  else Share.start(method,iface,false)
 }
 function loadEditor(){
  if(editorLoaded||!snapshot.config)return
  networkName.text=config.ssid||"EtherPocket";channelBox.currentIndex=Math.max(0,(config.channel||6)-1)
  subnet.text=config.subnet||"auto";dns.text=(config.dns||[]).join(", ")
  failover.checked=!!config.failover;autostart.checked=!!config.autostart
  hidden.checked=!!config.hidden;timeout.text=String(config.timeoutMinutes||0)
  dhcpStart.text=String(config.dhcpStart||20);dhcpEnd.text=String(config.dhcpEnd||200);lease.text=String(config.leaseMinutes||60)
  priority.currentIndex=(config.priority||[])[0]==="cellular"?2:(config.priority||[])[0]==="wifi"?1:0
  vpn.currentIndex=config.vpnPolicy==="vpn"?2:config.vpnPolicy==="normal"?1:0
  editorLoaded=true
 }
 Component.onCompleted:loadEditor()
 Connections {target:Share;function onChanged(){page.loadEditor()}}
 component Section:S.SettingsSection {tokens:page.tokens;Layout.fillWidth:true}
 component Info:S.SettingsInfoCard {tokens:page.tokens;Layout.fillWidth:true}
 component Action:S.SettingsAction {tokens:page.tokens;Layout.fillWidth:true;enabled:!Share.busy&&!!page.snapshot.ready}
 component Row:S.SettingsRow {tokens:page.tokens;arrow:false}
 component Input:S.SettingsInput {tokens:page.tokens;Layout.fillWidth:true;onKeyboardRequested:page.keyboardRequested()}
 component Label:Text {color:page.tokens.ink;font.pixelSize:page.tokens.body;wrapMode:Text.WrapAnywhere;Layout.fillWidth:true;textFormat:Text.PlainText}
 Info {objectName:"sharingStatus";title:page.active.length?"Internet sharing active":"Internet sharing off";description:page.snapshot.message||(page.snapshot.ready?"Choose a sharing method":"Reading network state…")}
 GridLayout {
  Layout.fillWidth:true;columns:width>=760?2:1;columnSpacing:tokens.gap;rowSpacing:tokens.sectionGap
  Section {
   Row {title:"USB tethering";description:page.snapshot.usbProtocol||"Checking existing gadget";value:page.activeMethod("usb")?"On":"Off"}
   Label {text:page.snapshot.usbReady?"Recovery USB link ready. Windows may need a DHCP renewal after enabling sharing.":"Recovery DHCP integration required. Existing USB access is preserved."}
   Label {text:"USB: "+(page.snapshot.usbControllers||[]).map(x=>x.state).join(", ")+" · "+(page.snapshot.usbHostDetected?"host enumerated":"host not enumerated")}
   Action {objectName:"usbSharingAction";text:page.activeMethod("usb")?"Stop USB sharing":"Start USB sharing";enabled:!Share.busy&&!!page.snapshot.ready&&!!page.snapshot.usbReady;onClicked:page.activeMethod("usb")?Share.stop("usb"):page.begin("usb",page.first("usb"))}
  }
  Section {
   Row {title:"Wi-Fi hotspot";description:page.snapshot.radioWarning||"WPA2 · 2.4 GHz · protected network";value:page.activeMethod("hotspot")?"On":"Off"}
   Label {text:page.config.passwordSet?"Password stored securely. Starting replaces the selected Wi-Fi connection.":"Set and save a password below before starting."}
   Action {text:"Show password for 30 seconds";visible:!!page.config.passwordSet;onClicked:Share.revealPassword()}
   Label {visible:!!Share.hotspotPassword;text:Share.hotspotPassword;Accessible.name:"Hotspot password"}
   Action {objectName:"hotspotSharingAction";text:page.activeMethod("hotspot")?"Stop hotspot":"Start hotspot";enabled:!Share.busy&&!!page.snapshot.ready&&(!!page.activeMethod("hotspot")||(!!page.config.passwordSet&&page.snapshot.hotspotAvailable!==false))&&!!page.first("wifi");onClicked:page.activeMethod("hotspot")?Share.stop("hotspot"):page.begin("hotspot",page.first("wifi"))}
   Action {text:"Try hotspot alongside Wi-Fi";visible:!page.activeMethod("hotspot");enabled:!Share.busy&&!!page.snapshot.ready&&!!page.config.passwordSet&&page.snapshot.hotspotAvailable!==false;onClicked:Share.startConcurrentHotspot(page.first("wifi"))}
  }
  Section {
   Row {title:"Internet source";description:"Connectivity is checked before sharing"}
   ComboBox {id:upstream;Layout.fillWidth:true;Layout.minimumWidth:0;model:["Automatic"].concat(page.interfaces.filter(x=>!x.downstream&&x.addresses.length).map(x=>x.interface));currentIndex:Math.max(0,model.indexOf(page.config.upstream==="auto"?"Automatic":page.config.upstream));enabled:!page.active.length&&!Share.busy;Accessible.name:"Internet source"}
   ComboBox {id:priority;Layout.fillWidth:true;Layout.minimumWidth:0;model:["Ethernet, Wi-Fi, LTE","Wi-Fi, Ethernet, LTE","LTE, Ethernet, Wi-Fi"];enabled:!page.active.length;Accessible.name:"Upstream priority";Component.onCompleted:currentIndex=(page.config.priority||[])[0]==="cellular"?2:(page.config.priority||[])[0]==="wifi"?1:0}
   ComboBox {id:vpn;Layout.fillWidth:true;Layout.minimumWidth:0;model:["Stop for VPN policy choice","Share normal internet (bypass VPN)","Share VPN only, block on loss"];enabled:!page.active.length;Accessible.name:"VPN policy";Component.onCompleted:currentIndex=page.config.vpnPolicy==="vpn"?2:page.config.vpnPolicy==="normal"?1:0}
   Label {text:"Failover uses active sources only. It never enables mobile data or roaming. Existing TCP connections may reconnect."}
   CheckBox {id:failover;text:"Allow upstream failover";enabled:!page.active.length;Layout.fillWidth:true}
   Action {text:"Check internet sources";onClicked:Share.checkInternet()}
  }
  Section {
   Row {title:"Ethernet sharing";description:"Select an unused downstream adapter"}
   ComboBox {id:ethernet;Layout.fillWidth:true;Layout.minimumWidth:0;model:page.candidates("ethernet").map(x=>x.interface);Accessible.name:"Downstream Ethernet adapter"}
   Action {text:page.activeMethod("ethernet")?"Stop Ethernet sharing":"Start Ethernet sharing";enabled:!Share.busy&&!!page.snapshot.ready&&(!!page.activeMethod("ethernet")||ethernet.currentIndex>=0);onClicked:page.activeMethod("ethernet")?Share.stop("ethernet"):page.begin("ethernet",ethernet.currentText)}
   Label {text:"Bluetooth PAN: "+(page.snapshot.bluetooth||"Not verified")+". IPv6 sharing is disabled."}
  }
 }
 Section {
  Row {title:"Active connections";description:page.snapshot.countersScope||"Interface traffic since sharing started"}
  Repeater {model:page.active;delegate:Row {required property var modelData;title:modelData.method+" · "+modelData.interface;description:modelData.upstream+" → "+modelData.gateway+"\n"+modelData.health+"\n↑ "+page.bytes(modelData.upload)+"   ↓ "+page.bytes(modelData.download)+"\nUp "+page.bytes(modelData.uploadBps||0)+"/s   Down "+page.bytes(modelData.downloadBps||0)+"/s"}}
  Label {visible:!page.active.length;text:"No sharing methods active"}
  Action {text:"Stop all sharing";enabled:!Share.busy&&!!page.active.length;destructive:true;onClicked:Share.stop("all")}
 }
 Section {
  Row {title:"Connected devices";description:"Station presence where available; DHCP leases can outlive a connection"}
  Repeater {model:page.snapshot.clients||[];delegate:Row {required property var modelData;title:modelData.name==="*"?modelData.address:modelData.name;description:modelData.address+" · "+modelData.mac+" · "+modelData.method+"\n"+modelData.evidence+(modelData.upload!==undefined?"\nUp "+page.bytes(modelData.upload||0)+" / Down "+page.bytes(modelData.download||0):"");arrow:true;onClicked:{rename.mac=modelData.mac;deviceName.text=modelData.name==="*"?"":modelData.name;rename.open()}}}
  Action {text:"Clear local device names";onClicked:Share.renameClient("*","")}
  Label {visible:!(page.snapshot.clients||[]).length;text:"No DHCP clients reported"}
 }
 Section {
  Row {title:"Configuration";description:"Stop sharing before editing. Settings are saved separately from effective state."}
  Input {id:networkName;placeholderText:"Hotspot name";enabled:!page.active.length}
  Input {id:password;placeholderText:page.config.passwordSet?"New password (blank keeps saved)":"WPA2 password";echoMode:TextInput.Password;inputMethodHints:Qt.ImhSensitiveData|Qt.ImhNoPredictiveText;enabled:!page.active.length}
  Row {title:"2.4 GHz channel";description:"Channels 1–11; radio regulatory rules still apply"}
  ComboBox {id:channelBox;Layout.fillWidth:true;Layout.minimumWidth:0;model:[1,2,3,4,5,6,7,8,9,10,11];enabled:!page.active.length;Accessible.name:"Hotspot channel"}
  CheckBox {id:hidden;text:"Hidden network name";enabled:!page.active.length}
  Input {id:subnet;placeholderText:"Subnet: auto or private /24";enabled:!page.active.length}
  Input {id:dns;placeholderText:"DNS: blank uses upstream";enabled:!page.active.length}
  Input {id:timeout;placeholderText:"Time limit in minutes (0 = off)";inputMethodHints:Qt.ImhDigitsOnly;enabled:!page.active.length}
  Row {title:"DHCP range and lease";description:"Last octets 2–253 for hotspot/Ethernet. USB preserves its single recovery host."}
  Input {id:dhcpStart;placeholderText:"First client octet";inputMethodHints:Qt.ImhDigitsOnly;enabled:!page.active.length}
  Input {id:dhcpEnd;placeholderText:"Last client octet";inputMethodHints:Qt.ImhDigitsOnly;enabled:!page.active.length}
  Input {id:lease;placeholderText:"Lease duration in minutes";inputMethodHints:Qt.ImhDigitsOnly;enabled:!page.active.length}
  CheckBox {id:autostart;text:"Start USB sharing after reboot";enabled:!page.active.length}
  Action {objectName:"saveSharingConfiguration";text:"Save configuration";enabled:!Share.busy&&!!page.snapshot.ready&&!page.active.length;onClicked:{
   let values={upstream:upstream.currentIndex===0?"auto":upstream.currentText,priority:priority.currentIndex===2?["cellular","ethernet","wifi"]:priority.currentIndex===1?["wifi","ethernet","cellular"]:["ethernet","wifi","cellular"],vpnPolicy:vpn.currentIndex===2?"vpn":vpn.currentIndex===1?"normal":"ask",failover:failover.checked,autostart:autostart.checked,ssid:networkName.text,channel:channelBox.currentIndex+1,hidden:hidden.checked,subnet:subnet.text.trim()||"auto",dns:dns.text.trim()?dns.text.split(",").map(x=>x.trim()):[],timeoutMinutes:Number(timeout.text)}
   values.dhcpStart=Number(dhcpStart.text);values.dhcpEnd=Number(dhcpEnd.text);values.leaseMinutes=Number(lease.text)
   if(password.text)values.password=password.text
   Share.configure(values);password.text=""
  }}
 }
 Section {
  Row {title:"Interfaces and diagnostics";description:page.snapshot.security||"Read-only inventory"}
  Repeater {model:page.interfaces;delegate:Row {required property var modelData;title:modelData.interface+" · "+modelData.kind;description:modelData.state+" · "+modelData.addresses.join(", ")+"\nGateway: "+(modelData.gateway||"none")+" · Internet: "+(modelData.internet===true?"verified":modelData.internet===false?"unavailable":"not checked")+"\nDNS: "+(modelData.dns||[]).join(", ")}}
  Label {text:"USB RNDIS is reused without unbinding the gadget. Host compatibility, DHCP and internet are separate checks. Wi-Fi station counters are reported when supplied by the driver. Client blocking/disconnect are not certified."}
 }
 S.SettingsDialog {id:confirm;tokens:page.tokens;property string method:"";property string iface:"";title:"Replace Wi-Fi with hotspot?";standardButtons:Dialog.Ok|Dialog.Cancel;contentItem:ColumnLayout {Label {text:"This disconnects the current Wi-Fi network on "+confirm.iface+". Keep USB recovery connected. Only an already active alternate internet source can be shared."}} onAccepted:Share.start(method,iface,true)}
 S.SettingsDialog {id:rename;tokens:page.tokens;property string mac:"";title:"Local device name";standardButtons:Dialog.Ok|Dialog.Cancel;contentItem:ColumnLayout {Label {text:rename.mac} Input {id:deviceName;placeholderText:"Device name";maximumLength:64}} onAccepted:Share.renameClient(mac,deviceName.text.trim())}
}
