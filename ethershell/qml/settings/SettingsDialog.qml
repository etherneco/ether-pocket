import QtQuick
import QtQuick.Controls
Dialog {
 id:dialog;required property var tokens
 property bool compact:parent.height/scale<300
 parent:Overlay.overlay;modal:true;transformOrigin:Popup.TopLeft
 scale:Math.min(tokens.uiScale,Math.max(1,(parent.height-24)/220))
 implicitWidth:Math.max(120,Math.min(parent.width/scale-24,480));width:implicitWidth;padding:compact?8:16
 x:(parent.width-width*scale)/2;y:(parent.height-height*scale)/2
 palette.windowText:tokens.ink;palette.text:tokens.ink;palette.buttonText:tokens.ink;palette.base:tokens.soft;palette.highlight:tokens.accent
 header:Text {text:dialog.title;padding:dialog.compact?8:16;color:dialog.tokens.ink;font.pixelSize:(dialog.compact?dialog.tokens.body:dialog.tokens.sectionTitle)*dialog.tokens.fontScale;wrapMode:Text.WordWrap;font.bold:true}
 background:Rectangle {radius:dialog.tokens.radius;color:dialog.tokens.surface;border.color:dialog.tokens.line}
}

