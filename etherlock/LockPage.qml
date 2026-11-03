import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import "../qml/settings" as S
ColumnLayout {
 id:page;property var tokens
 component Title:Text {color:page.tokens.ink;font.pixelSize:page.tokens.sectionTitle*page.tokens.fontScale;font.bold:true;Layout.fillWidth:true;wrapMode:Text.Wrap}
 S.SettingsSection {tokens:page.tokens
  Title {text:"Screen Lock"}
  S.SettingsInfoCard {tokens:page.tokens;Layout.fillWidth:true;title:LockControl.state.ready?("EtherLock · "+LockControl.state.phase):"EtherLock not running";description:LockControl.state.backend||"Install and manually validate the session coordinator before enabling automatic locking."}
  S.SettingsStatus {tokens:page.tokens;Layout.fillWidth:true;text:LockControl.message||LockControl.state.error||"Automatic locking starts disabled. Administrator authentication, recovery and display acceptance are required."}
  S.SettingsAction {tokens:page.tokens;text:"Lock now";enabled:!!LockControl.state.ready;onClicked:LockControl.lock()}
  S.SettingsToggle {tokens:page.tokens;Layout.fillWidth:true;title:"Automatic locking";description:"Requires acceptance for this exact build and boot";enabled:!!LockControl.state.validated;checked:!!LockControl.state.enabled;onRequested:wanted=>LockControl.configure({enabled:wanted})}
  S.SettingsStatus {tokens:page.tokens;Layout.fillWidth:true;text:"Linux account password via PAM. Numeric input uses the same account credential; a separate device PIN is unavailable."}
  Flow {Layout.fillWidth:true;spacing:6
   Repeater {model:[{label:"Immediately",value:0},{label:"15 seconds",value:15},{label:"30 seconds",value:30},{label:"1 minute",value:60},{label:"5 minutes",value:300}]
    delegate:S.SettingsAction {required property var modelData;tokens:page.tokens;text:modelData.label;enabled:!!LockControl.state.ready;onClicked:LockControl.configure({timeout:modelData.value})}}
  }
  S.SettingsStatus {tokens:page.tokens;text:"Idle timeout: "+((LockControl.state.config||{}).timeout||0)+" seconds"}
  S.SettingsToggle {tokens:page.tokens;Layout.fillWidth:true;title:"Lock before screen off";description:"Display blanking requires an enforcement acknowledgement when enabled";checked:(LockControl.state.config||{}).lockOnScreenOff!==false;enabled:!!LockControl.state.ready;onRequested:wanted=>LockControl.configure({lockOnScreenOff:wanted})}
 }
 S.SettingsSection {tokens:page.tokens
  Title {text:"Privacy & recovery"}
  S.SettingsStatus {tokens:page.tokens;Layout.fillWidth:true;text:"Lock-screen notifications are hidden. Locked call controls, emergency calls and biometrics are unavailable pending backend and hardware validation."}
  S.SettingsStatus {tokens:page.tokens;Layout.fillWidth:true;text:LockControl.state.remote||"Existing SSH sessions remain connected. Screen lock and remote authorization are separate controls."}
  S.SettingsStatus {tokens:page.tokens;Layout.fillWidth:true;text:LockControl.state.encryption||"Offline storage encryption is not supplied by the screen lock."}
  S.SettingsStatus {tokens:page.tokens;Layout.fillWidth:true;text:"X11 trusts clients sharing the session. This development device also grants passwordless sudo. Keep independent SSH recovery available; see /usr/share/doc/etherlock/etherlock.rst."}
  S.SettingsStatus {tokens:page.tokens;Layout.fillWidth:true;text:LockControl.state.suspend||"Suspend/wake acceptance is required before activation."}
 }
}
