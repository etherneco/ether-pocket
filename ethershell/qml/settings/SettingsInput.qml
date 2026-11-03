import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import QtQuick.Window
TextField {
 id:field;required property var tokens;property string error:"";signal keyboardRequested()
 Layout.minimumWidth:0
 implicitHeight:tokens.target;font.pixelSize:tokens.body*tokens.fontScale;color:tokens.ink;placeholderTextColor:tokens.muted
 leftPadding:12;rightPadding:12;selectByMouse:true;inputMethodHints:Qt.ImhNoPredictiveText
 Accessible.name:placeholderText;Accessible.description:error
 function ensureEditorVisible(){if(!activeFocus)return;let p=field.parent;while(p){if(p.contentY!==undefined&&p.contentHeight!==undefined){let point=field.mapToItem(p.contentItem,0,0);p.contentY=Math.max(0,Math.min(p.contentHeight-p.height,point.y-p.height+field.height+18));break}p=p.parent}}
 onActiveFocusChanged:if(activeFocus&&!readOnly){keyboardRequested();visibilityDelay.restart()}
 TapHandler {onTapped:if(!field.readOnly)field.keyboardRequested()}
 Timer {id:visibilityDelay;interval:80;onTriggered:field.ensureEditorVisible()}
 Connections {target:field.Window.window;function onHeightChanged(){if(field.activeFocus)visibilityDelay.restart()}}
 background:Rectangle {radius:field.tokens.controlRadius;color:field.tokens.soft;border.color:field.error?field.tokens.danger:field.activeFocus?field.tokens.accent:field.tokens.line;border.width:field.activeFocus?2:1}
}

