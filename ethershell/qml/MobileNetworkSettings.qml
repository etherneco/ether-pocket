import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import "settings" as S
import "../diagnostics.js" as Diagnostics

ColumnLayout {
    id: panel
    objectName: "mobileNetworkSettings"
    S.SettingsTheme {id:mobileTheme;uiScale:panel.width>0?panel.mapToItem(null,1,0).x-panel.mapToItem(null,0,0).x:1}
    property var tokens:mobileTheme
    Layout.leftMargin:16;Layout.rightMargin:16;Layout.topMargin:14;Layout.bottomMargin:12
    signal backRequested()
    signal keyboardRequested()
    property string section: "Mobile Data"
    property string selectedUuid: Core.preferences.mobileProfileUuid || ""
    property var selected: Mobile.profiles.find(p => p.uuid === selectedUuid) || Mobile.profiles.find(p => p.active) || Mobile.profiles[0] || ({})
    property bool editorIntent: false
    property bool dirty: false
    property bool populating: false
    property var draft: ({})
    property var confirmationAction: null
    property string simOperation: "pin"
    property string pendingPolicy: ""
    property bool dataDetails: false
    property double statusClock: Date.now()/1000
    readonly property bool connectionOperationError: ["Błąd połączenia","Nieobsługiwany profil","Permission denied","Verification failed"].indexOf(Mobile.operation.state)>=0
    Timer {interval:1000;running:!!Mobile.status.dataPending;repeat:true;onTriggered:panel.statusClock=Date.now()/1000}
    spacing: tokens.gap

    function confirm(text, action) { confirmationText.text = text; confirmationAction = action; confirmation.open() }
    function navigate(destination) { section = destination; Core.setting("mobileSettingsSection", destination); if(destination === "Data Usage")Mobile.sampleUsage() }
    function edit(path, duplicate) { editorIntent = true; Mobile.editConfiguration(path || "", !!duplicate) }
    function toggleData() {
        let chosen=Object.assign({},selected)
        if(Mobile.status.canDisconnect) confirm("Disconnect the selected modem's mobile data? Wi-Fi will remain enabled.", function(){Mobile.disconnectData()})
        else if(!selected.path) navigate("Access Point Names")
        else confirm("Activate the selected saved APN? Mobile data charges may apply. Roaming is " + (chosen.roaming ? "allowed by this profile." : "blocked by this profile."), function(){Mobile.connectProfile(chosen.path)})
    }
    function bytes(value) { let n=Number(value || 0); return n >= 1e9 ? (n/1e9).toFixed(2)+" GB" : n >= 1e6 ? (n/1e6).toFixed(2)+" MB" : n >= 1e3 ? (n/1e3).toFixed(1)+" kB" : n+" B" }
    function activeApn() { if(Mobile.status.dataProvider==="downstream-ipa"&&Mobile.status.dataActive)return Mobile.status.dataApn;let p=Mobile.profiles.find(p => p.path===Mobile.status.activeProfile);return p ? p.apn : "No active APN" }
    function ipSummary(family,key){let ip=(Mobile.status.network||{})[family]||{};return Diagnostics.text(ip[key])}
    function loadEditor() {
        if(!editorIntent)return
        editorIntent=false;populating=true;draft=Object.assign({},Mobile.editor)
        name.text=draft.name || "";apn.text=draft.apn || "";username.text=draft.username || "";password.text="";replacePassword.checked=false
        auth.currentIndex=Math.max(0,auth.model.indexOf(draft.auth));family.currentIndex=Math.max(0,family.model.indexOf(draft.ipType))
        autoConnect.checked=!!draft.autoconnect;allowRoam.checked=!!draft.roaming;internetRoute.checked=!!draft.internetRoute
        priority.value=Number(draft.priority || 0);metric.text=String(draft.metric===undefined ? 900 : draft.metric)
        manualDns.checked=!!draft.manualDns;dns4.text=draft.dns4 || "";dns6.text=draft.dns6 || ""
        dirty=false;populating=false;editor.open()
    }
    function saveDraft() {
        let fields=Object.assign({},draft,{name:name.text,apn:apn.text,username:username.text,password:password.text,
            changePassword:replacePassword.checked,auth:auth.currentText,ipType:family.currentText,autoconnect:autoConnect.checked,
            roaming:allowRoam.checked,internetRoute:internetRoute.checked,priority:priority.value,metric:Number(metric.text),
            manualDns:manualDns.checked,dns4:dns4.text,dns6:dns6.text})
        Mobile.saveConfiguration(fields)
        password.text="";fields.password=""
    }
    function markDirty(){if(!populating)dirty=true}
    Connections {
        target: Mobile
        function onEditorChanged(){ panel.loadEditor() }
        function onOperationChanged(){
            if(Mobile.operation.state === "Saved" && editor.visible){panel.populating=true;panel.draft=Object.assign({},Mobile.editor);replacePassword.checked=false;panel.dirty=false;panel.populating=false}
            if(Mobile.operation.state !== "Applying" && Mobile.operation.state !== "Ready")panel.editorIntent=false
        }
    }
    Component.onCompleted: { let s=Core.preferences.mobileSettingsSection;if(s) section=s }
    component TextLine: Label { color: panel.tokens.ink; font.pixelSize:panel.tokens.body*panel.tokens.fontScale;wrapMode: Text.WordWrap; textFormat: Text.PlainText; Layout.fillWidth: true }
    component Hint: TextLine { color: panel.tokens.muted; font.pixelSize: 12*panel.tokens.fontScale }
    component Card:S.SettingsSection {tokens:panel.tokens}
    component Button:S.SettingsAction {tokens:panel.tokens}
    component Sheet:S.SettingsDialog {tokens:panel.tokens}
    component Selector:S.SettingsSelect {tokens:panel.tokens}
    component Toggle:S.SettingsToggle {tokens:panel.tokens;title:text}
    component Check:S.SettingsToggle {tokens:panel.tokens;title:text;Layout.minimumWidth:0;onRequested:wanted=>checked=wanted;onCheckedChanged:panel.markDirty()}
    component Field:S.SettingsInput {
        tokens:panel.tokens;Layout.fillWidth:true
        onTextEdited: panel.markDirty()
        onKeyboardRequested:panel.keyboardRequested()
    }
    S.SettingsHeader {tokens:panel.tokens;title:"Mobile Network";subtitle:"Settings";onBack:panel.backRequested();onMore:mobileActions.open()}
    S.SettingsTabs {objectName:"mobileSectionSelector";tokens:panel.tokens;Layout.fillWidth:true;model:["Data","SIM","APN","Networks","Advanced"];currentIndex:panel.section==="SIM Cards"?1:panel.section==="Access Point Names"?2:panel.section==="Network Selection"||panel.section==="Preferred Network Type"?3:panel.section==="Advanced Modem Settings"||panel.section==="Diagnostics"?4:0;onSelected:index=>panel.navigate(["Mobile Data","SIM Cards","Access Point Names","Network Selection","Advanced Modem Settings"][index])}
    ScrollView {
        id: scroll;Layout.fillWidth:true;Layout.fillHeight:true;clip:true;contentWidth:availableWidth
        ColumnLayout {width:scroll.availableWidth;spacing:panel.tokens.sectionGap
            Card {
                TextLine {text:Mobile.status.operator || "Operator unavailable";font.pixelSize:panel.tokens.sectionTitle*panel.tokens.fontScale;font.bold:true}
                S.SettingsStatus {tokens:panel.tokens;text:Mobile.status.state||"Modem unavailable";state:Mobile.status.dataActive?"success":"warning";font.pixelSize:16*panel.tokens.fontScale}
                Hint {text:Mobile.status.technology||"Network technology unavailable"}
                GridLayout {columns:width<320?2:4;Layout.fillWidth:true;columnSpacing:6
                    Repeater {model:[{label:"Signal",value:Mobile.status.signal||"Unavailable",icon:"▥"},{label:"Internet",value:Mobile.status.internet||"Not verified",icon:"↕"},{label:"Roaming",value:Mobile.status.roaming?"Yes":"No",icon:"◎"},{label:"SIM",value:Mobile.status.simReady?"Ready":Mobile.status.sim||"Unavailable",icon:"▣"}];delegate:Rectangle {required property var modelData;Layout.fillWidth:true;implicitHeight:80;radius:14;color:panel.tokens.soft
                        Column {anchors.fill:parent;anchors.margins:8;spacing:4
                            Text {text:modelData.icon;color:panel.tokens.accent;font.pixelSize:20}
                            Text {text:modelData.label;color:panel.tokens.ink;font.pixelSize:12*panel.tokens.fontScale;font.bold:true}
                            Text {text:modelData.value;color:panel.tokens.muted;font.pixelSize:11*panel.tokens.fontScale;width:parent.width;wrapMode:Text.WordWrap}
                        }
                    }}
                }
                Hint {visible:!Mobile.status.available;text:Mobile.status.explanation || "ModemManager unavailable. Saved profiles remain accessible."}
                Selector {visible:Mobile.modems.length>1;Layout.fillWidth:true;implicitHeight:48;model:Mobile.modems;textRole:"label";valueRole:"path";onActivated:Mobile.selectModem(currentValue)}
            }
            Card {
                objectName:"mobileDataProgress"
                visible:panel.section==="Mobile Data"
                TextLine {text:Mobile.status.dataError||panel.connectionOperationError?"Błąd połączenia":Mobile.status.dataStopping?"Rozłączanie…":Mobile.status.dataPending?"Próbuję połączyć…":Mobile.status.dataActive?"Dane komórkowe połączone":"Stan transmisji danych";font.bold:true}
                BusyIndicator {running:!!Mobile.status.dataPending||!!Mobile.status.dataStopping;visible:running;Layout.preferredWidth:32;Layout.preferredHeight:32}
                TextLine {objectName:"mobileDataStage";text:panel.connectionOperationError?Mobile.operation.message:Mobile.status.dataMessage || Mobile.message || "Gotowy do połączenia.";color:Mobile.status.dataError||panel.connectionOperationError?panel.tokens.danger:panel.tokens.ink}
                Hint {visible:!!Mobile.status.dataPending&&Number(Mobile.status.dataStarted)>0;text:"Czas próby: "+Math.max(0,Math.floor(panel.statusClock-Number(Mobile.status.dataStarted)))+" s"}
                TextLine {objectName:"mobileDataError";visible:!!Mobile.status.dataErrorDetail;text:(Mobile.status.dataErrorCode?"Kod: "+Mobile.status.dataErrorCode+"\n":"")+(Mobile.status.dataErrorDetail||"");color:Mobile.status.dataError?panel.tokens.danger:panel.tokens.muted}
                Hint {visible:Mobile.status.dataProvider==="downstream-ipa";text:"Sterowanie przez adapter IPA. Standardowy ModemManager zgłasza dla tego modemu błąd „Unsupported QMI kernel driver”."}
                Button {text:panel.dataDetails?"Ukryj etapy połączenia":"Pokaż etapy połączenia";visible:(Mobile.status.dataHistory||[]).length>0;onClicked:panel.dataDetails=!panel.dataDetails}
                Repeater {model:panel.dataDetails?(Mobile.status.dataHistory||[]):[];delegate:Hint {required property var modelData;text:new Date(Number(modelData.time)*1000).toLocaleTimeString()+" · "+modelData.message}}
            }
            Card {
                visible:panel.section==="Mobile Data" || panel.section==="Data Roaming"
                S.SettingsToggle {tokens:panel.tokens;visible:panel.section==="Mobile Data";title:"Mobile data";description:Mobile.status.dataPending?"Łączenie…":Mobile.status.dataActive?"Połączono z siecią komórkową":"Użyj sieci komórkowej do transmisji danych";checked:!!Mobile.status.dataActive;enabled:!Mobile.busy&&(Mobile.status.canDisconnect||Mobile.status.canConnect);onRequested:panel.toggleData()}
                TextLine {visible:panel.section!=="Mobile Data";text:"Saved connection profile";font.bold:true}
                Selector {objectName:"mobileProfileSelector";visible:Mobile.profiles.length>1||panel.section!=="Mobile Data";Layout.fillWidth:true;implicitHeight:48;model:Mobile.profiles;textRole:"name";valueRole:"uuid";currentIndex:Mobile.profiles.findIndex(p=>p.uuid===panel.selected.uuid);onActivated:{panel.selectedUuid=currentValue;Core.setting("mobileProfileUuid",currentValue)}}
                Hint {text:panel.selected.path ? "APN: "+panel.selected.apn+" · "+panel.selected.ipType+" · "+panel.selected.auth : "No accessible GSM profiles. Add an APN using your carrier's settings."}
                Hint {visible:panel.section!=="Mobile Data";text:"Saved autoconnect: "+(panel.selected.autoconnect?"on":"off")+" · Saved roaming permission: "+(panel.selected.roaming?"allowed":"blocked")}
                Toggle {
                    id:autoPolicy;visible:panel.section==="Mobile Data"&&Mobile.status.dataProvider!=="downstream-ipa";text:"Automatic connection";checked:!!panel.selected.autoconnect;enabled:!!panel.selected.path&&!Mobile.busy
                    onRequested:wanted=>{let selected=Object.assign({},panel.selected);panel.confirm(wanted?"Save automatic connection ON? NetworkManager may activate mobile data and incur charges when service becomes available.":"Save automatic connection OFF? This changes the saved profile; an active session is not disconnected.",function(){Mobile.changeProfilePreferences(selected.path,selected.version,wanted,!!selected.roaming)})}
                }
                Hint {visible:Mobile.status.dataProvider==="downstream-ipa";text:"Automatyczne łączenie przy starcie obsługuje usługa danych IPA. Ten adapter używa APN giffgaff.com i IPv4; roaming jest zablokowany."}
                Toggle {
                    id:roamPolicy;text:"Allow data roaming";checked:Mobile.status.dataProvider==="downstream-ipa"?false:!!panel.selected.roaming;enabled:Mobile.status.dataProvider!=="downstream-ipa"&&!!panel.selected.path&&!Mobile.busy
                    onRequested:wanted=>{let selected=Object.assign({},panel.selected);panel.confirm(wanted?"Allow data roaming for this saved APN? Additional carrier charges may apply. The saved policy is verified separately from the active session.":"Block roaming in this saved APN? The updated policy is used when the profile is activated; current roaming state is shown separately.",function(){Mobile.changeProfilePreferences(selected.path,selected.version,!!selected.autoconnect,wanted)})}
                }
                Hint {visible:panel.section==="Data Roaming";text:"Currently roaming and permission to use roaming data are separate states. Enabling permission can incur additional charges."}
                S.SettingsRow {tokens:panel.tokens;title:"Preferred network type";description:(Mobile.modes.find(m=>m.id===Mobile.status.currentMode)||{}).label||"Unavailable";visible:panel.section==="Mobile Data";onClicked:panel.navigate("Preferred Network Type")}
                Button {visible:panel.section!=="Mobile Data";text:"Configure roaming permission";Layout.fillWidth:true;enabled:!!panel.selected.path&&!Mobile.busy;onClicked:panel.edit(panel.selected.path,false)}
                RowLayout {visible:panel.section==="Data Roaming";Layout.fillWidth:true
                    Button {text:Mobile.status.canDisconnect?"Mobile data off":"Mobile data on";Layout.fillWidth:true;enabled:!Mobile.busy&&(Mobile.status.canDisconnect||Mobile.status.canConnect);onClicked:panel.toggleData()}
                    Button {text:"Reconnect";Layout.fillWidth:true;enabled:!!panel.selected.path&&!!Mobile.status.canDisconnect&&!Mobile.busy;onClicked:panel.confirm("Disconnect current mobile data and activate this saved APN? This interrupts cellular service and may incur charges.",function(){Mobile.reconnectProfile(panel.selected.path)})}
                }
                Hint {visible:!Mobile.status.canConnect&&!Mobile.status.canDisconnect;text:"A registered network and packet interface are required."}
                Button {text:"Reconnect previous APN";visible:!!Mobile.status.connectionRollbackAvailable;Layout.fillWidth:true;enabled:!!Mobile.status.connectionRollbackAvailable&&!Mobile.busy;onClicked:panel.confirm("Reconnect the previously active APN? This requires an unchanged saved revision and no new active cellular session. Data charges may apply.",function(){Mobile.rollbackConnection()})}
                Hint {visible:panel.section!=="Mobile Data";text:"Wi-Fi is never disabled. A saved profile is distinct from the configuration of an active session."}
            }
            Card {
                visible:panel.section==="Mobile Data"
                TextLine {text:"Current connection";font.bold:true;font.pixelSize:panel.tokens.sectionTitle}
                S.SettingsStatus {tokens:panel.tokens;text:Mobile.status.dataError?"Błąd połączenia":Mobile.status.dataActive?"Połączono":Mobile.status.dataPending?"Łączenie…":"Rozłączono";error:Mobile.status.dataError?"Błąd połączenia":"";state:Mobile.status.dataActive?"success":"neutral"}
                Repeater {model:[{label:"Active APN",value:panel.activeApn()},{label:"IPv4",value:panel.ipSummary("ipv4","addresses")},{label:"IPv6",value:panel.ipSummary("ipv6","addresses")},{label:"DNS",value:panel.ipSummary("ipv4","dns")},{label:"Gateway",value:panel.ipSummary("ipv4","gateway")},{label:"Connection duration",value:"Not exposed by this provider"},{label:"Uploaded",value:Mobile.usage.available?panel.bytes(Mobile.usage.sessionTx):"Unavailable"},{label:"Downloaded",value:Mobile.usage.available?panel.bytes(Mobile.usage.sessionRx):"Unavailable"}];delegate:S.SettingsRow {required property var modelData;tokens:panel.tokens;title:modelData.label;value:modelData.value;arrow:false;dense:true}}
            }
            Card {
                visible:panel.section==="Mobile Data"
                S.SettingsRow {tokens:panel.tokens;title:"Data usage";description:Mobile.usage.hasHistory?panel.bytes(Number(Mobile.usage.monthlyRx)+Number(Mobile.usage.monthlyTx))+" · cycle from "+Mobile.usage.cycleStart:"No measured cellular traffic";onClicked:panel.navigate("Data Usage")}
                Hint {text:"Local interface estimates. Carrier billing and internet connectivity are separate."}
            }
            Card {
                visible:panel.section==="Access Point Names"
                TextLine {text:"Saved APN profiles";font.bold:true}
                Button {text:"Add APN";Layout.fillWidth:true;enabled:!Mobile.busy;onClicked:panel.edit("",false)}
                Repeater {model:Mobile.profiles
                    delegate:ColumnLayout {required property var modelData;Layout.fillWidth:true;spacing:8
                        TextLine {text:modelData.name+(modelData.active?" · ACTIVE":"");font.bold:true}
                        Hint {text:modelData.apn+" · "+modelData.auth+" · "+modelData.ipType+"\nAutoconnect "+(modelData.autoconnect?"on":"off")+" · Roaming "+(modelData.roaming?"allowed":"blocked")+" · Priority "+modelData.priority}
                        Hint {visible:!!modelData.operatorCode;text:"Saved operator association: "+modelData.operatorCode}
                        Flow {Layout.fillWidth:true;spacing:8
                            Button {text:"Edit";enabled:!Mobile.busy;onClicked:panel.edit(modelData.path,false)}
                            Button {text:"Duplicate";enabled:!Mobile.busy;onClicked:panel.confirm("Create a new draft from this profile? Saving the copy preserves its credentials through NetworkManager.",function(){panel.edit(modelData.path,true)})}
                            Button {text:"Use APN";enabled:!Mobile.busy&&(Mobile.status.canConnect||Mobile.status.canDisconnect);onClicked:panel.confirm("Activate this APN? An existing cellular session must be explicitly reconnected. Data charges may apply.",function(){Mobile.status.canDisconnect?Mobile.reconnectProfile(modelData.path):Mobile.connectProfile(modelData.path)})}
                            Button {text:"Delete";destructive:true;enabled:!Mobile.busy&&!modelData.active;onClicked:panel.confirm("Delete this saved profile permanently? Active profiles must first be disconnected.",function(){Mobile.deleteConfiguration(modelData.path,modelData.version)})}
                        }
                        Rectangle {Layout.fillWidth:true;implicitHeight:1;color:panel.tokens.line}
                    }
                }
                Hint {visible:Mobile.profiles.length===0;text:"No saved cellular profiles are accessible to this user."}
                Button {text:"Provider defaults";Layout.fillWidth:true;enabled:false}
                Hint {text:"A verified provider database adapter is not installed. Existing profiles are preserved; no carrier settings are invented."}
                Button {text:"Restore previous saved configuration";Layout.fillWidth:true;enabled:!!Mobile.operation.rollbackAvailable&&!Mobile.busy;onClicked:panel.confirm("Restore the previous profile configuration? Rollback will be refused if it changed externally. Active sessions are not silently reconfigured.",function(){Mobile.rollbackConfiguration()})}
            }
            Card {
                visible:panel.section==="SIM Cards"
                TextLine {text:"SIM "+(Mobile.status.simSlot || "—")+" · "+(Mobile.status.sim || "Unavailable");font.bold:true}
                Hint {text:"SIM operator: "+(Mobile.status.simOperator || "Unavailable")+" · Home network: "+(Mobile.status.simHomeNetwork || "Unavailable")}
                Hint {text:Mobile.status.simReady?"SIM is ready for ordinary network use.":Mobile.status.pinRequired?"SIM PIN required.":"SIM readiness is unavailable or locked; inspect diagnostics."}
                Hint {text:"IMSI, ICCID and phone numbers are masked and are never displayed here."}
                Hint {text:Mobile.status.remainingAttempts===null||Mobile.status.remainingAttempts===undefined?"Remaining attempts: not reliably available for the required lock.":"Remaining attempts for the requested lock: "+Mobile.status.remainingAttempts}
                Flow {Layout.fillWidth:true;spacing:8
                    Button {text:"Enter PIN";enabled:!!Mobile.status.pinRequired&&!Mobile.busy;onClicked:{panel.simOperation="pin";simDialog.open()}}
                    Button {text:"Unlock PUK";enabled:Mobile.status.unlockRequired===4&&!Mobile.busy;onClicked:{panel.simOperation="puk";simDialog.open()}}
                    Button {text:"Enable PIN lock";enabled:!!Mobile.status.simReady&&!Mobile.busy;onClicked:{panel.simOperation="enable";simDialog.open()}}
                    Button {text:"Disable PIN lock";enabled:!!Mobile.status.simReady&&!Mobile.busy;onClicked:{panel.simOperation="disable";simDialog.open()}}
                    Button {text:"Change PIN";enabled:!!Mobile.status.simReady&&!Mobile.busy;onClicked:{panel.simOperation="change";simDialog.open()}}
                }
                Hint {text:"Incorrect PIN/PUK attempts can permanently lock the SIM. No code is guessed, stored in preferences or retried automatically. PIN2 is separate from the ordinary SIM PIN."}
                RowLayout {Layout.fillWidth:true
                    SpinBox {id:slot;from:1;to:Math.max(1,Mobile.status.slots || 1);implicitHeight:48;value:Mobile.status.simSlot || 1;enabled:!!Mobile.status.canSelectSlot}
                    Button {text:"Select SIM slot";enabled:!!Mobile.status.canSelectSlot&&!Mobile.busy;onClicked:panel.confirm("Switch active SIM slot? Cellular service may be interrupted while the modem is reprobed.",function(){Mobile.selectSimSlot(slot.value)})}
                }
                Hint {visible:!Mobile.status.canSelectSlot;text:"Multiple usable SIM slots have not been exposed by this Linux backend. eSIM is not verified."}
            }
            Card {
                visible:panel.section==="Network Selection"
                Hint {text:"Current operator: "+(Mobile.status.operator || "Unavailable")+" · "+(Mobile.status.operatorCode || "Unavailable")}
                Hint {text:"Effective selection mode: "+(Mobile.status.selectionMode || "Unavailable")}
                Hint {text:"Last saved request: "+(Core.preferences.mobileOperatorRequest || "None")+". This request is not proof of registration."}
                Button {text:"Automatic registration";Layout.fillWidth:true;enabled:!!Mobile.status.canScan&&!Mobile.busy;onClicked:panel.confirm("Request automatic/home-network registration? Cellular connectivity may change.",function(){Core.setting("mobileOperatorRequest","automatic");Mobile.registerOperator("")})}
                Button {text:"Scan available operators";Layout.fillWidth:true;enabled:!!Mobile.status.canScan&&!Mobile.busy;onClicked:panel.confirm("Scanning can interrupt cellular connectivity and take up to two minutes. Continue?",function(){Mobile.scanOperators()})}
                Repeater {model:Mobile.operators;delegate:ColumnLayout {required property var modelData;Layout.fillWidth:true
                    TextLine {text:modelData.name+" · "+modelData.code+" · "+modelData.technology}
                    Hint {text:["Unknown","Available","Current","Forbidden"][Number(modelData.availability)] || "Unknown"}
                    Button {text:"Register";enabled:modelData.availability!==3&&!Mobile.busy;onClicked:panel.confirm("Register with this operator? Registration can interrupt service; data roaming remains governed by the APN profile.",function(){Core.setting("mobileOperatorRequest",modelData.code);Mobile.registerOperator(modelData.code)})}
                }}
            }
            Card {
                visible:panel.section==="Preferred Network Type"
                Hint {text:"Effective mode (backend masks): "+(Mobile.status.enabledModes || "Unavailable")}
                Hint {text:"Saved request: "+(Core.preferences.mobileModeRequested || "None")+". Saved requests are not automatically reapplied on launch."}
                Selector {id:mode;Layout.fillWidth:true;implicitHeight:48;model:Mobile.modes;textRole:"label";valueRole:"id"}
                Button {text:"Save request and apply mode";Layout.fillWidth:true;enabled:Mobile.modes.length>0&&!Mobile.busy;onClicked:panel.confirm("Change the modem's radio preference? Registration and active cellular service can be interrupted. The effective mode will be read back.",function(){Core.setting("mobileModeRequested",mode.currentValue);Mobile.applyMode(mode.currentValue)})}
                Button {text:"Restore previous effective mode";Layout.fillWidth:true;enabled:!!Mobile.operation.modeRollbackAvailable&&!Mobile.busy;onClicked:panel.confirm("Restore the previously observed mode? This is refused if the current mode changed externally.",function(){Mobile.rollbackMode()})}
                Hint {text:"Only backend-reported mode pairs are offered. No functional 5G selector is exposed. Mode retention across reboot needs hardware acceptance; a saved request and an effective modem setting are separate."}
            }
            Card {
                visible:panel.section==="Data Usage"
                Hint {text:Mobile.usage.note || "Read the current interface counters when a cellular session becomes available."}
                Hint {visible:!Mobile.usage.available;text:"No active cellular interface can currently be sampled."}
                TextLine {visible:!!Mobile.usage.available;text:"Observed session ↓ "+panel.bytes(Mobile.usage.sessionRx)+"  ↑ "+panel.bytes(Mobile.usage.sessionTx)}
                TextLine {visible:!!Mobile.usage.hasHistory;text:"Today ↓ "+panel.bytes(Mobile.usage.dailyRx)+"  ↑ "+panel.bytes(Mobile.usage.dailyTx)+"\nBilling cycle ↓ "+panel.bytes(Mobile.usage.monthlyRx)+"  ↑ "+panel.bytes(Mobile.usage.monthlyTx)}
                Hint {text:"Billing cycle begins: "+(Mobile.usage.cycleStart || "No samples")}
                Hint {text:"Billing day (1–31)"}
                SpinBox {id:billing;from:1;to:31;value:Mobile.usage.billingDay || 1;implicitHeight:48}
                Hint {text:"Warning threshold in MB; 0 disables warnings"}
                Field {id:threshold;text:String(Mobile.usage.warningMB || 0);inputMethodHints:Qt.ImhFormattedNumbersOnly}
                Button {text:"Save usage preferences";Layout.fillWidth:true;onClicked:Mobile.setUsageOptions(billing.value,Number(threshold.text))}
                TextLine {visible:!!Mobile.usage.warning;text:"Usage warning threshold reached. The connection has not been disconnected.";color:panel.tokens.danger}
                Button {text:"Refresh measured usage";Layout.fillWidth:true;onClicked:Mobile.sampleUsage()}
                Hint {text:"Automatic hard limits are not enabled. Usage history only counts observed deltas; it cannot reconstruct traffic while the application is stopped."}
            }
            Card {
                visible:panel.section==="Advanced Modem Settings"
                TextLine {text:"Read-only modem and packet-path details";font.bold:true}
                Hint {text:"Modem path: "+(Mobile.status.selected || "Unavailable")+"\nManufacturer: "+(Mobile.status.manufacturer || "Unavailable")+"\nModel: "+(Mobile.status.model || "Unavailable")+"\nFirmware: "+(Mobile.status.firmware || "Unavailable")}
                Repeater {model:Diagnostics.rows({transport:Mobile.status.transport,drivers:Mobile.status.drivers,interface:Mobile.status.interface,ports:Mobile.status.ports,network:Mobile.status.network,signalMetrics:Mobile.status.signalMetrics});delegate:ColumnLayout {required property var modelData;Layout.fillWidth:true;TextLine {text:modelData.label;font.bold:true}Hint {text:modelData.value;textFormat:Text.PlainText}}}
                Hint {text:"Radio power: "+Diagnostics.power(Mobile.status.powerState)+"\nCurrent network mode: "+Diagnostics.mode(Mobile.status,Mobile.modes)+"\nAvailable network modes:\n"+Diagnostics.text(Mobile.modes)}
                Hint {text:"QMI/QRTR/MBIM is shown only when exposed by the current provider. No arbitrary modem command console or root shell is available. Firmware and calibration partitions are never modified here."}
                Button {text:"Refresh backend state";Layout.fillWidth:true;enabled:!Mobile.busy;onClicked:Mobile.refresh()}
            }
            Card {
                visible:panel.section==="Diagnostics"
                Button {text:"Run EtherModem Doctor";Layout.fillWidth:true;enabled:!Mobile.busy;onClicked:Mobile.diagnose()}
                Hint {text:"Read-only queries. No daemon restart, radio reset, registration request or data activation."}
                Repeater {model:Mobile.stages;delegate:ColumnLayout {objectName:"diagnosticStage";required property var modelData;property bool expanded:false;Layout.fillWidth:true
                    TextLine {text:modelData.stage+" · "+Diagnostics.status(modelData.status);font.bold:true}
                    Hint {text:Diagnostics.summary(modelData)}
                    Button {text:parent.expanded?"Hide details":"Show details";onClicked:parent.expanded=!parent.expanded}
                    Repeater {model:parent.expanded?Diagnostics.rows(modelData.evidence):[];delegate:ColumnLayout {required property var modelData;Layout.fillWidth:true;TextLine {text:modelData.label;font.bold:true}Hint {text:modelData.value;textFormat:Text.PlainText}}}
                }}
            }
            Card {
                visible:!!Mobile.message
                TextLine {text:Mobile.operation.state || "Status";font.bold:true}
                Hint {text:Mobile.message}
            }
            Item {implicitHeight:12}
        }
    }
    S.SettingsBottomSheet {id:mobileActions;tokens:panel.tokens;title:"Mobile Network";contentItem:ListView {implicitWidth:280;implicitHeight:Math.min(contentHeight,400);clip:true;model:["Mobile Data","SIM Cards","Access Point Names","Network Selection","Preferred Network Type","Data Roaming","Data Usage","Advanced Modem Settings","Diagnostics"];delegate:S.SettingsRow {required property string modelData;tokens:panel.tokens;width:ListView.view.width;title:modelData;onClicked:{panel.navigate(modelData);mobileActions.close()}}}}
    GridLayout {Layout.fillWidth:true;columns:4;columnSpacing:4
        Button {text:"Details";Layout.fillWidth:true;onClicked:panel.navigate("Advanced Modem Settings")}
        Button {text:Mobile.status.canDisconnect?"Disconnect":"Connect";Layout.fillWidth:true;enabled:!Mobile.busy&&(Mobile.status.canDisconnect||Mobile.status.canConnect);onClicked:panel.toggleData()}
        Button {text:"Diagnose";Layout.fillWidth:true;enabled:!Mobile.busy;onClicked:{panel.navigate("Diagnostics");Mobile.diagnose()}}
        Button {text:"Refresh";Layout.fillWidth:true;enabled:!Mobile.busy;onClicked:Mobile.refresh()}
    }
    Sheet {
        id:confirmation;parent:Overlay.overlay;modal:true;width:Math.min(parent.width/scale-32,480);title:"Confirm change";standardButtons:Dialog.Ok|Dialog.Cancel
        contentItem:TextLine {id:confirmationText;width:confirmation.availableWidth}
        onAccepted:{let action=panel.confirmationAction;panel.confirmationAction=null;if(action)action()}
        onRejected:panel.confirmationAction=null
    }
    Sheet {
        id:editor;objectName:"mobileApnEditor";parent:Overlay.overlay;modal:true
        closePolicy:Popup.NoAutoClose;width:Math.min(parent.width/scale-24,570);height:Math.min(parent.height/scale-24,820)
        title:panel.draft.path?"Edit saved APN":"New APN profile"
        contentItem:ColumnLayout {spacing:10
            ScrollView {id:formScroll;Layout.fillWidth:true;Layout.fillHeight:true;clip:true;contentWidth:availableWidth
                ColumnLayout {width:formScroll.availableWidth;spacing:10
                    Hint {text:"Saving changes the stored profile. Applying it to a live session is a separate confirmed operation. Hidden credentials are preserved unless replaced."}
                    Hint {text:"Profile name"} Field {id:name;objectName:"mobileApnName";maximumLength:80}
                    Hint {text:"Carrier APN"} Field {id:apn;objectName:"mobileApnValue";maximumLength:100}
                    Hint {text:"Username"} Field {id:username;maximumLength:256}
                    Check {id:replacePassword;text:"Replace stored password";onToggled:panel.markDirty();implicitHeight:48}
                    Field {id:password;enabled:replacePassword.checked;echoMode:TextInput.Password;maximumLength:1024;placeholderText:"Hidden; unchanged unless replaced";inputMethodHints:Qt.ImhSensitiveData|Qt.ImhNoPredictiveText}
                    Button {text:"Clear stored secrets";visible:!!panel.draft.path;enabled:!Mobile.busy&&!panel.dirty&&!panel.draft.active;Layout.fillWidth:true;onClicked:{let chosen=Object.assign({},panel.draft);panel.confirm("Clear ALL stored credentials for this disconnected profile, including any cached password or SIM PIN? This does not change the PIN on the SIM. Re-enter credentials before connecting.",function(){Mobile.clearConfigurationSecrets(chosen.path,chosen.version)})}}
                    Hint {text:"Authentication"}
                    Selector {id:auth;Layout.fillWidth:true;implicitHeight:48;model:["Automatic","PAP","CHAP","PAP or CHAP"];onActivated:panel.markDirty()}
                    Hint {text:"IP family"}
                    Selector {id:family;Layout.fillWidth:true;implicitHeight:48;model:["IPv4","IPv6","IPv4 + IPv6"];onActivated:panel.markDirty()}
                    Check {id:autoConnect;text:"Connect automatically";implicitHeight:48;onToggled:panel.markDirty()}
                    Check {id:allowRoam;text:"Allow data roaming (additional charges)";implicitHeight:48;onToggled:panel.markDirty()}
                    Check {id:internetRoute;text:"Allow a cellular default internet route";implicitHeight:48;onToggled:panel.markDirty()}
                    Hint {text:"Autoconnect priority (-999 to 999)"}
                    SpinBox {id:priority;from:-999;to:999;implicitHeight:48;onValueModified:panel.markDirty()}
                    Hint {text:"Route metric (-1 uses NetworkManager default). Review Wi-Fi priorities before allowing a cellular default route."}
                    Field {id:metric;inputMethodHints:Qt.ImhDigitsOnly}
                    Check {id:manualDns;text:"Use only manually entered DNS servers";implicitHeight:48;onToggled:panel.markDirty()}
                    Hint {text:"IPv4 DNS addresses, separated by commas"} Field {id:dns4;placeholderText:"Blank keeps automatic DNS unless manual-only is selected"}
                    Hint {text:"IPv6 DNS addresses, separated by commas"} Field {id:dns6}
                    Hint {text:(Mobile.operation.state || "Ready")+" · "+(Mobile.operation.message || "")}
                }
            }
            RowLayout {Layout.fillWidth:true
                Button {objectName:"mobileApnCancel";text:"Cancel / close";Layout.fillWidth:true;enabled:!Mobile.busy;onClicked:{if(panel.dirty)discard.open();else editor.close()}}
                Button {objectName:"mobileApnSave";text:"Save and verify";Layout.fillWidth:true;enabled:!Mobile.busy&&name.text.trim().length>0&&apn.text.trim().length>0;onClicked:{if(autoConnect.checked||allowRoam.checked||internetRoute.checked)panel.confirm("Save these settings? Automatic connection, roaming or a default route may change connectivity or incur charges. Wi-Fi will not be disabled.",function(){panel.saveDraft()});else panel.saveDraft()}}
            }
        }
        onClosed: {password.text="";panel.dirty=false}
    }
    Sheet {id:discard;parent:Overlay.overlay;modal:true;width:Math.min(parent.width/scale-32,440);title:"Discard unsaved changes?";standardButtons:Dialog.Yes|Dialog.No;onAccepted:editor.close()}
    Sheet {
        id:simDialog;parent:Overlay.overlay;modal:true;width:Math.min(parent.width/scale-32,450);title:"SIM operation: "+panel.simOperation;standardButtons:Dialog.Ok|Dialog.Cancel
        contentItem:ColumnLayout {spacing:12
            TextLine {text:"One attempt will be sent. Wrong codes can permanently lock your SIM. Use only your known codes; no automatic retries."}
            Field {id:simFirst;placeholderText:panel.simOperation==="puk"?"PUK (8 digits)":"Current SIM PIN";echoMode:TextInput.Password;maximumLength:8;inputMethodHints:Qt.ImhDigitsOnly|Qt.ImhSensitiveData|Qt.ImhNoPredictiveText}
            Field {id:simSecond;visible:panel.simOperation==="change"||panel.simOperation==="puk";placeholderText:"New PIN (4–8 digits)";echoMode:TextInput.Password;maximumLength:8;inputMethodHints:Qt.ImhDigitsOnly|Qt.ImhSensitiveData|Qt.ImhNoPredictiveText}
        }
        onAccepted:{Mobile.simAction(panel.simOperation,simFirst.text,simSecond.text);simFirst.text="";simSecond.text=""}
        onClosed:{simFirst.text="";simSecond.text=""}
    }
}
