import QtQuick
import QtQuick.Controls
Label {required property var tokens;property string state:"neutral";property bool loading:false;property string error:"";color:error?tokens.danger:state==="success"?tokens.success:state==="warning"?tokens.warning:tokens.muted;font.pixelSize:tokens.caption*tokens.fontScale;wrapMode:Text.WordWrap;textFormat:Text.PlainText;Accessible.name:text}

