import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import "../qml/settings" as S

ColumnLayout {
 id:page;objectName:"etherBackupPage";required property var tokens;signal keyboardRequested()
 readonly property var state:BackupControl.state||({})
 readonly property var details:BackupControl.details||({})
 readonly property var destinations:details.destinations||[]
 readonly property var profiles:details.profiles||[]
 readonly property var preview:BackupControl.preview||({})
 spacing:tokens.sectionGap
 component Card:S.SettingsSection {tokens:page.tokens;Layout.fillWidth:true}
 component Row:S.SettingsRow {tokens:page.tokens;Layout.fillWidth:true;arrow:false}
 component Action:S.SettingsAction {tokens:page.tokens;Layout.fillWidth:true;enabled:!page.state.busy}
 component Status:S.SettingsStatus {tokens:page.tokens;Layout.fillWidth:true}
 Status {text:page.state.ready?(page.state.status||"Recovery not tested"):"EtherBackup service unavailable";state:"warning"}
 Status {visible:!!BackupControl.message;text:BackupControl.message}
 Card {
  Row {title:"Backup & Restore";description:"Encrypted backups with a verified sample restore. Complete operating-system recovery has not been tested."}
  Action {text:"Unlock private backup details";onClicked:BackupControl.inspect()}
  Row {visible:!!page.details.ready;title:"Protection overview";description:"Last backup: "+(page.details.lastSuccessfulBackup||"None")+"\nLast sample verification: "+(page.details.lastVerifiedBackup||"None")+"\nSchedule: "+(page.details.schedule&&page.details.schedule.enabled?"Enabled; systemd timer":"Disabled")+"\nProtected data estimate: "+Number(page.details.estimatedProtectedBytes||0).toLocaleString()+" bytes"}
 }
 Card {
  Row {title:"Backup now";description:"Choose a commissioned encrypted destination and profile. Recovery passwords must be retained independently."}
  ComboBox {id:destination;Layout.fillWidth:true;model:page.destinations;textRole:"id";Accessible.name:"Backup destination"}
  ComboBox {id:profile;Layout.fillWidth:true;model:page.profiles;Accessible.name:"Backup profile"}
  Action {text:"Create and verify backup";enabled:!page.state.busy&&destination.currentIndex>=0&&profile.currentIndex>=0;onClicked:BackupControl.backup(page.profiles[profile.currentIndex],page.destinations[destination.currentIndex].id)}
  Status {visible:page.destinations.length===0;text:"No commissioned destination. An administrator must configure repository access and an independently retained password using etherbackup."}
 }
 Card {
  Row {title:"Destinations";description:"Local, USB, pinned SFTP and mounted NAS are configured in the protected administrator policy. USB/NAS mounts use existing Linux mount tools; drives are never formatted."}
  Repeater {model:page.destinations;delegate:Row {required property var modelData;title:modelData.id+" · "+modelData.kind;description:(modelData.available?"Configured and locally available":"Unavailable")+"\n"+modelData.warning}}
 }
 Card {
  Row {title:"History & restore";description:"Restore files, contacts, photographs or application data to a private review directory. Original files remain intact."}
  Repeater {model:page.details.history||[];delegate:ColumnLayout {
   required property var modelData;Layout.fillWidth:true
   Row {title:modelData.created+" · "+modelData.profile;description:modelData.destination+" · "+Number(modelData.bytes).toLocaleString()+" bytes\n"+(modelData.sampleVerified?"Sample restore verified":"Verification required")+(modelData.protected?" · Protected":"")}
   Action {text:"Verify repository and sample restore";onClicked:BackupControl.verify(modelData.id)}
   Action {text:"Browse restore files";onClicked:{selection.text="";BackupControl.select(modelData.id,"")}}
   Action {text:"Protect this recovery point";onClicked:BackupControl.protect(modelData.id)}
   Action {text:"Recovery manifest and instructions";onClicked:BackupControl.recoveryInfo(modelData.id)}
  }}
 }
 Card {
  visible:!!page.preview.point
  Row {title:"Restore preview";description:Object.keys(page.preview.files||{}).length+" files · "+Number(page.preview.totalBytes||0).toLocaleString()+" bytes\n"+(page.preview.mode||"")}
  S.SettingsInput {id:selection;tokens:page.tokens;Layout.fillWidth:true;placeholderText:"Optional path or directory from this restore point";onKeyboardRequested:page.keyboardRequested()}
  Action {text:"Preview selected path";onClicked:BackupControl.select(page.preview.point,selection.text)}
  Repeater {model:Object.keys(page.preview.files||{}).slice(0,100);delegate:Row {required property string modelData;title:modelData;description:"Checksum validated on restore"}}
  Action {text:"Restore to private review directory";onClicked:confirmation.open()}
 }
 Card {
  Row {title:"Advanced";description:"Engine: Restic · Repository encryption required\nRetention: "+JSON.stringify(page.details.retention||{})+"\nLost passwords cannot be recovered. A same-device backup does not protect against storage failure.\nSystem configuration and databases need an administrator-reviewed offline apply and schema compatibility checks."}
 }
 Dialog {id:confirmation;modal:true;width:Math.min(page.width-24,440);contentWidth:width-40;contentHeight:160;title:"Confirm isolated restore";standardButtons:Dialog.Ok|Dialog.Cancel;onAccepted:BackupControl.restore();contentItem:Text {text:"Restore the selected files into an administrator-only review directory? Checksums and SQLite integrity will be validated.";wrapMode:Text.WordWrap;color:page.tokens.ink}}
}
