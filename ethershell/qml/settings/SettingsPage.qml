import QtQuick
import QtQuick.Controls
import QtQuick.Window
ScrollView {id:page;required property var tokens;clip:true;contentWidth:availableWidth;leftPadding:0;rightPadding:0;ScrollBar.horizontal.policy:ScrollBar.AlwaysOff
 onHeightChanged:focusDelay.restart()
 Timer {id:focusDelay;interval:100;onTriggered:{let field=page.Window.window?page.Window.window.activeFocusItem:null;while(field){if(typeof field.ensureEditorVisible==="function"){field.ensureEditorVisible();break}field=field.parent}}}
}

