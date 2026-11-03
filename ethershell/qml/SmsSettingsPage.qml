import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import "settings" as S
ColumnLayout {
 id:page
 required property var tokens
 property var prefs:SmsSettings.values
 property var capabilities:SmsTransport.capabilities
 signal keyboardRequested()
 spacing:tokens.sectionGap
 component Section:S.SettingsSection {tokens:page.tokens}
 component Title:Text {Layout.fillWidth:true;color:page.tokens.ink;font.pixelSize:page.tokens.sectionTitle;font.bold:true;wrapMode:Text.WordWrap}
 component Info:S.SettingsStatus {wrapMode:Text.WrapAnywhere;tokens:page.tokens;Layout.fillWidth:true}
 component Toggle:S.SettingsToggle {tokens:page.tokens}
 component Input:S.SettingsInput {objectName:"sms-field-1";tokens:page.tokens;Layout.fillWidth:true;onKeyboardRequested:page.keyboardRequested()}
 component Action:S.SettingsAction {tokens:page.tokens;Layout.fillWidth:true}
 Section {
  Title {objectName:"sms-field-2";text:"SMS & Messaging"}
  Info {objectName:"sms-field-3";text:(page.capabilities.backend||"EtherMobile")+"\nSIM: "+(page.capabilities.simReady?"Ready":"Unavailable / locked")+" · Network: "+(page.capabilities.network||"Reading…")+"\nSMS interface: "+(page.capabilities.available?"Available; live send/receive requires testing":"Unavailable")}
  Action {text:"Open EtherSMS";onClicked:SmsSettings.launch()}
  Toggle {title:"Message notifications";checked:!!page.prefs.notifications;onRequested:w=>SmsSettings.set("notifications",w)}
  S.SettingsSelect {tokens:page.tokens;Layout.fillWidth:true;title:"Notification privacy";model:["Sender only","Full preview","Hidden content"];currentIndex:["sender","full","hidden"].indexOf(page.prefs.preview);onActivated:i=>SmsSettings.set("preview",["sender","full","hidden"][i])}
  Toggle {title:"Request delivery reports";description:"Delivered is shown only for a matched confirmation";checked:!!page.prefs.deliveryReports;onRequested:w=>SmsSettings.set("deliveryReports",w)}
  Toggle {title:"Confirm before sending";checked:!!page.prefs.confirmSend;onRequested:w=>SmsSettings.set("confirmSend",w)}
  Info {objectName:"sms-field-4";text:"Drafts are saved locally. History and contacts are stored in a private SQLite database. Backup and message deletion are available inside EtherSMS. SMSC and operator storage settings are preserved."}
 }
 Section {
  Title {objectName:"sms-field-5";text:"Offline voice dictation"}
  Toggle {title:"Enable dictation";checked:!!page.prefs.dictation;onRequested:w=>SmsSettings.set("dictation",w)}
  Info {objectName:"sms-field-6";text:"Engine: "+SmsSettings.diagnostics.speechEngine+"\n"+(SmsSettings.diagnostics.microphones||"")}
  S.SettingsSelect {tokens:page.tokens;Layout.fillWidth:true;title:"Dictation language";model:["Polski","English","Automatic"];currentIndex:["pl","en","auto"].indexOf(page.prefs.language);onActivated:i=>SmsSettings.set("language",["pl","en","auto"][i])}
  Input {objectName:"sms-field-7";placeholderText:"Microphone source (optional)";text:page.prefs.microphone||"";onEditingFinished:SmsSettings.set("microphone",text)}
  Input {objectName:"sms-field-8";placeholderText:"Multilingual model filename";text:page.prefs.speechModel;onEditingFinished:SmsSettings.set("speechModel",text)}
  Info {objectName:"sms-field-9";text:"Install whisper-cli separately. Supported model choices: multilingual tiny (~75 MB), base (~142 MB), small (~466 MB). No models are downloaded automatically. Use a trusted publisher SHA-256 checksum."}
  S.SettingsSelect {id:availableModel;tokens:page.tokens;Layout.fillWidth:true;title:"Available multilingual models";model:["base (~142 MB)","tiny (~75 MB)","small (~466 MB)"]}
  Action {text:"Download and verify selected model…";onClicked:downloadConsent.open()}
  Input {objectName:"sms-field-10";id:modelSource;placeholderText:"Local model path"}
  Input {objectName:"sms-field-11";id:modelChecksum;placeholderText:"Publisher SHA-256"}
  Action {text:"Verify and install local model";onClicked:SmsSettings.installModel(modelSource.text,modelChecksum.text)}
  Info {objectName:"sms-field-12";text:"Installed models: "+(SmsSettings.diagnostics.models||"None")+"\n"+(SmsSettings.diagnostics.modelOperation||"")}
  Action {text:"Remove selected model";onClicked:removeConfirm.open()}
 }
 Section {
  Title {objectName:"sms-field-13";text:"Local AI assistant"}
  Toggle {title:"Enable local Ollama correction";description:"Suggestions require review; messages remain unsent";checked:!!page.prefs.aiEnabled;onRequested:w=>SmsSettings.set("aiEnabled",w)}
  Info {objectName:"sms-field-14";text:SmsSettings.diagnostics.aiEndpoint||""}
  Input {objectName:"sms-field-15";placeholderText:"Installed Ollama model name";text:page.prefs.aiModel||"";onEditingFinished:SmsSettings.set("aiModel",text)}
 }
 Section {
  Title {objectName:"sms-field-16";text:"Read messages aloud"}
  Toggle {title:"Enable text-to-speech";description:"Playback starts only from a selected message";checked:!!page.prefs.ttsEnabled;onRequested:w=>SmsSettings.set("ttsEnabled",w)}
  Info {objectName:"sms-field-17";text:"Engine: "+SmsSettings.diagnostics.tts}
  S.SettingsSelect {tokens:page.tokens;Layout.fillWidth:true;model:["Polski","English"];currentIndex:page.prefs.ttsVoice==="en"?1:0;onActivated:i=>SmsSettings.set("ttsVoice",i===0?"pl":"en")}
  Input {objectName:"sms-field-18";placeholderText:"Speed (80–300 words/min)";text:String(page.prefs.ttsRate);inputMethodHints:Qt.ImhDigitsOnly;onEditingFinished:SmsSettings.set("ttsRate",Number(text))}
  Input {objectName:"sms-field-19";placeholderText:"Audio output (optional)";text:page.prefs.outputDevice||"";onEditingFinished:SmsSettings.set("outputDevice",text)}
 }
 Section {
  Title {objectName:"sms-field-20";text:"Diagnostics"}
  Info {objectName:"sms-field-21";text:"SMS send: "+(page.capabilities.canSend?"Backend ready; unverified end-to-end":"Blocked")+"\nSMS receive: "+(page.capabilities.canReceive?"Interface available; unverified end-to-end":"Blocked")+"\n"+(page.capabilities.deliveryReports||"")+"\nAudio: "+SmsSettings.diagnostics.audioCapture}
  Action {text:"Refresh capabilities";onClicked:SmsSettings.refresh()}
 }
 S.SettingsDialog {id:downloadConsent;tokens:page.tokens;title:"Approve speech model download?";standardButtons:Dialog.Ok|Dialog.Cancel;contentItem:Info {objectName:"sms-field-22";text:"Download "+availableModel.currentText+" from the official Whisper model repository using the current connection. This may use mobile data. Enter the trusted publisher SHA-256 before approving. Basic SMS works without a model."}onAccepted:SmsSettings.downloadModel(["base","tiny","small"][availableModel.currentIndex],modelChecksum.text)}
 S.SettingsDialog {id:removeConfirm;tokens:page.tokens;title:"Remove installed speech model?";standardButtons:Dialog.Ok|Dialog.Cancel;onAccepted:SmsSettings.removeModel(page.prefs.speechModel)}
}
