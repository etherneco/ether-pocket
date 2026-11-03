import QtQuick
import QtQuick.Layouts
Item {
    id: header
    required property var tokens
    property var application: ({})
    property bool browser: application.profile==="Firefox"
    property bool terminal: application.profile==="Terminal"
    property bool desktopMode: false
    signal menuRequested()
    signal closeRequested(string id)
    signal keyboardRequested()
    signal backRequested()
    RowLayout {
        anchors.fill: parent;spacing: 8
        GlassPanel {tokens:header.tokens;Layout.fillWidth:true;Layout.preferredHeight:54;radius:24
            Row {anchors.fill:parent;anchors.margins:8;spacing:9
                Image {width:36;height:36;anchors.verticalCenter:parent.verticalCenter;source:"image://icons/"+(header.application.icon||"application-x-executable");sourceSize:Qt.size(72,72)}
                Column {anchors.verticalCenter:parent.verticalCenter;width:parent.width-52;spacing:2
                    Text {text:header.application.name||"EtherSurface";width:parent.width;elide:Text.ElideRight;color:tokens.ink;font.pixelSize:14*tokens.fontScale;font.weight:Font.DemiBold}
                    Text {text:header.application.profile==="Generic X11 Application"?"Native X11 application":header.application.profile||"Your Debian. Your way.";color:tokens.muted;font.pixelSize:10*tokens.fontScale}
                }
            }
            MouseArea {anchors.fill:parent;property point previous;property bool dragged:false;onPressed: e=>{dragged=false;previous=mapToGlobal(e.x,e.y);if(header.application.id)Pocket.action("activate",header.application.id)};onPressAndHold:if(!dragged)header.menuRequested();onDoubleClicked:Pocket.action("maximize",header.application.id||"");onPositionChanged:e=>{if(pressed&&header.desktopMode){let current=mapToGlobal(e.x,e.y);if(Math.abs(current.x-previous.x)+Math.abs(current.y-previous.y)>3)dragged=true;Pocket.moveBy(header.application.id,Math.round(current.x-previous.x),Math.round(current.y-previous.y));previous=current}}}
        }
        TouchAction {tokens:header.tokens;glyph:"keyboard";compact:true;onClicked:header.keyboardRequested()}
        TouchAction {tokens:header.tokens;glyph:"more";compact:true;onClicked:header.menuRequested()}
        TouchAction {tokens:header.tokens;glyph:"chevron";compact:true;selected:true;onClicked:Pocket.action("minimize",header.application.id||"")}
    }
}
