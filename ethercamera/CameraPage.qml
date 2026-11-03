import QtQuick
import QtQuick.Layouts
import "../qml/settings" as S

ColumnLayout {
 id:page;objectName:"etherCameraPage";required property var tokens
 readonly property var state:CameraControl.state||({})
 spacing:tokens.sectionGap
 component Card:S.SettingsSection {tokens:page.tokens;Layout.fillWidth:true}
 component Row:S.SettingsRow {tokens:page.tokens;Layout.fillWidth:true;arrow:false}
 component Status:S.SettingsStatus {tokens:page.tokens;Layout.fillWidth:true}
 Status {visible:!page.state.ready;state:"warning";text:"EtherCamera service unavailable. Camera capture has not been verified."}
 Status {visible:!!CameraControl.message;text:CameraControl.message}
 Status {visible:!!page.state.active;state:"warning";text:"Camera in use · "+(page.state.purpose||"Managed capture")}
 Card {
  Row {title:"Camera devices";description:page.state.internalCamera||"Waiting for hardware diagnostics"}
  Repeater {model:page.state.devices||[];delegate:ColumnLayout {required property var modelData;Layout.fillWidth:true
   Row {title:modelData.name||modelData.id;description:modelData.id+" · "+(modelData.driver||"No standard V4L2 driver")+" · "+modelData.role}
   Status {text:modelData.error||((modelData.supportedProvider?"Physical camera provider available. ":"Capture unavailable. ")+"Real sensor frame: "+(((page.state.verified||{})[modelData.id]||{}).previewVerified?"verified in this service session":"not verified"))}
   Status {visible:!!modelData.formats;text:modelData.formats||""}
   Status {visible:!!modelData.controls;text:modelData.controls||""}
  }}
  S.SettingsAction {tokens:page.tokens;Layout.fillWidth:true;text:"Refresh device diagnostics";enabled:!!page.state.ready&&!page.state.busy;onClicked:CameraControl.refresh()}
 }
 Card {
  Row {title:"Photography";description:"JPEG or PNG · camera-owned Pictures/EtherCamera folder · location excluded. Output sizes may use software scaling; native formats appear in device diagnostics. Capture UI awaits a verified physical camera path."}
  S.SettingsSelect {tokens:page.tokens;Layout.fillWidth:true;title:"Image format";model:["JPEG","PNG"];currentIndex:((page.state.config||{}).format||"JPEG")==="PNG"?1:0;enabled:!!page.state.permissionCoordinatorAvailable;onActivated:index=>CameraControl.configure({format:index===1?"PNG":"JPEG"})}
  S.SettingsSelect {tokens:page.tokens;Layout.fillWidth:true;title:"Default output resolution";model:["640 × 480","1280 × 720","1920 × 1080"];currentIndex:[640,1280,1920].indexOf((page.state.config||{}).width||640);enabled:!!page.state.permissionCoordinatorAvailable;onActivated:index=>CameraControl.configure({width:[640,1280,1920][index],height:[480,720,1080][index]})}
  Row {title:"Video";description:"Experimental H.264/MP4, limited to 640 × 480 at 15 fps and 60 seconds pending performance acceptance. Microphone audio is obtained only through EtherAudio after separate consent."}
  S.SettingsSelect {tokens:page.tokens;Layout.fillWidth:true;title:"Video resolution";model:["640 × 480","320 × 240"];currentIndex:((page.state.config||{}).videoWidth||640)===320?1:0;enabled:!!page.state.permissionCoordinatorAvailable;onActivated:index=>CameraControl.configure({videoWidth:index===1?320:640,videoHeight:index===1?240:480})}
  S.SettingsSelect {tokens:page.tokens;Layout.fillWidth:true;title:"Video frame rate";model:["15 fps","10 fps","5 fps"];currentIndex:[15,10,5].indexOf((page.state.config||{}).videoFps||15);enabled:!!page.state.permissionCoordinatorAvailable;onActivated:index=>CameraControl.configure({videoFps:[15,10,5][index]})}
  Row {title:"Microphone";description:page.state.microphone||"Disabled"}
  S.SettingsToggle {tokens:page.tokens;Layout.fillWidth:true;title:"Default video audio preference";description:"Every recording still requires separate microphone consent.";checked:!!((page.state.config||{}).videoAudio);enabled:!!page.state.permissionCoordinatorAvailable;onRequested:wanted=>CameraControl.configure({videoAudio:wanted})}
 }
 Card {
  Row {title:"Privacy";description:page.state.privacy||"Per-session consent, owner-bound API and fail-closed EtherLock checks. Direct device access follows Linux permissions."}
  S.SettingsToggle {tokens:page.tokens;Layout.fillWidth:true;title:"Block managed camera access";checked:((page.state.config||{}).cameraPolicy||"ask-each-time")==="deny";enabled:!!page.state.ready;onRequested:wanted=>CameraControl.configure({cameraPolicy:wanted?"deny":"ask-each-time"})}
  Status {visible:!!page.state.configurationError;state:"warning";text:page.state.configurationError||""}
  Row {title:"Lock-screen policy";description:"Capture denied while locked or EtherLock unavailable; active sessions close on lock, owner exit and suspend."}
  Row {title:"Recent usage";description:(page.state.history||[]).map(e=>new Date(e.timestamp*1000).toLocaleTimeString()+" · "+e.event).join("\n")||"No managed camera activity in this service session"}
 }
 Card {
  Row {title:"Advanced diagnostics";description:"Qualcomm Spectra request manager and synchronization nodes are not image sources. Vendor Camera HAL/provider paths checked by the audit are absent. Pop-up motor disabled pending safe control verification."}
  Row {title:"Acceleration";description:page.state.hardwareAcceleration||"Not verified"}
  Row {title:"Diagnostic export";description:"Run ethercamera report. The allowlisted report excludes photos, video, scan payloads and capture purposes."}
  Status {visible:!!page.state.lastError;state:"warning";text:page.state.lastError||""}
 }
}
