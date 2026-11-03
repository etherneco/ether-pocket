import QtQuick
Item {
    id: strip
    required property var tokens
    property real unit: 1
    signal navigate(string direction)
    Rectangle {anchors.centerIn:parent;width:64*strip.unit;height:4*strip.unit;radius:2*strip.unit;color:strip.tokens.muted;opacity:.65}
    MouseArea {
        anchors.fill:parent
        property real sx;property real sy;property bool allowed;property bool held
        onPressed: event=>{sx=event.x;sy=event.y;held=false;allowed=Core.preferences.gestures&&event.x/width>=Pocket.gestureStart&&event.x/width<=Pocket.gestureEnd}
        onPressAndHold: {if(allowed){held=true;strip.navigate("menu")}}
        onReleased: event=>{
            if(held)return
            if(!allowed){if(Math.abs(event.x-sx)<8*strip.unit&&Math.abs(event.y-sy)<8*strip.unit)strip.navigate("reveal");return}
            let dx=event.x-sx,dy=event.y-sy,threshold=34*strip.unit
            if(dx>threshold&&Math.abs(dx)>Math.abs(dy)&&Core.preferences.edgeBack&&sx/width<Pocket.gestureStart+.12)strip.navigate("back")
            else if(Math.abs(dx)>threshold&&Math.abs(dx)>Math.abs(dy))strip.navigate(dx<0?"next":"previous")
            else if(Math.abs(dy)>threshold)strip.navigate(dy<0?"overview":"quick")
            else strip.navigate("reveal")
        }
    }
}
