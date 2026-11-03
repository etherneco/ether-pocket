import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import QtMultimedia

ApplicationWindow {
 id:window;visible:true;width:480;height:900;minimumWidth:320;minimumHeight:480
 title:"EtherCamera Media";color:"#f3f7ff";font.pixelSize:14
 flags:Qt.Window|Qt.FramelessWindowHint
 component BodyLabel:Label {font.pixelSize:14}
 component TouchButton:Button {
  implicitHeight:44;leftPadding:12;rightPadding:12;font.pixelSize:14
  contentItem:Text {text:parent.text;font:parent.font;color:parent.enabled?"#173963":"#8698ab";horizontalAlignment:Text.AlignHCenter;verticalAlignment:Text.AlignVCenter;elide:Text.ElideRight}
  background:Rectangle {radius:12;color:parent.down?"#d7e8ff":"#edf4ff";border.color:"#cddff7"}
 }
 component Field:TextField {implicitHeight:46;padding:12;font.pixelSize:14;color:"#173963";placeholderTextColor:"#7289a2";selectByMouse:true;background:Rectangle {radius:12;color:"white";border.color:parent.activeFocus?"#4b8ce8":"#d6e3f5"}}
 component Select:ComboBox {implicitHeight:46;font.pixelSize:14;background:Rectangle {radius:12;color:"white";border.color:"#d6e3f5"}}
 component Choice:CheckBox {implicitHeight:44;font.pixelSize:14}
 property var pages:[]
 property bool qaPlayVideo:false
 readonly property int qaVideoFrames:Library.videoFrames
 readonly property int mediaPosition:player.position
 readonly property var selected:Library.selectedMedia.metadata||({})
 function query(){pages=[];Library.load(search.text,["","photo","video","document"][filter.currentIndex],album.text)}
 function openMedia(reference){Library.choose(reference);viewer.open()}
 ColumnLayout {
  anchors.fill:parent;anchors.margins:16;spacing:12
  RowLayout {Layout.fillWidth:true
   BodyLabel {text:"EtherCamera Media";font.pixelSize:23;font.bold:true;color:"#173963";Layout.fillWidth:true;wrapMode:Text.WordWrap}
   TouchButton {text:"Close";onClicked:window.close()}
  }
  BodyLabel {text:Library.privateState?"Media locked · start the existing EtherLock coordinator and unlock the session":"Photos, videos and documents saved by EtherCamera";color:"#536d8b";wrapMode:Text.WordWrap;Layout.fillWidth:true}
  Field {id:search;placeholderText:"Search metadata";Layout.fillWidth:true;enabled:!Library.privateState;onAccepted:window.query()}
  RowLayout {Layout.fillWidth:true
   Select {id:filter;model:["All media","Photos","Videos","Documents"];Layout.fillWidth:true;enabled:!Library.privateState;onActivated:window.query()}
   TouchButton {text:"Refresh";enabled:!Library.busy&&!Library.privateState;onClicked:window.query()}
  }
  Field {id:album;placeholderText:"Filter by album (optional)";Layout.fillWidth:true;enabled:!Library.privateState;onAccepted:window.query()}
  ListView {
   id:list;objectName:"mediaList";Layout.fillWidth:true;Layout.fillHeight:true;clip:true;spacing:12;model:Library.items
   ScrollBar.vertical:ScrollBar {}
   delegate:Column {
    id:entry;required property var modelData;width:list.width;spacing:8
    BodyLabel {visible:!!entry.modelData.dayHeader;text:entry.modelData.dayHeader||"";font.bold:true;color:"#45617f"}
    Rectangle {
     width:parent.width;height:140;radius:18;color:"white";border.color:"#d8e6fa"
     RowLayout {anchors.fill:parent;anchors.margins:10;spacing:10
      Rectangle {Layout.preferredWidth:92;Layout.fillHeight:true;radius:10;color:"#eaf2ff"
       BodyLabel {anchors.centerIn:parent;text:entry.modelData.suffix===".mp4"?"VIDEO":entry.modelData.suffix===".pdf"?"PDF":"PHOTO";color:"#55799f"}
       Image {id:thumb;anchors.fill:parent;anchors.margins:4;fillMode:Image.PreserveAspectFit;cache:false;asynchronous:true}
      }
      ColumnLayout {Layout.fillWidth:true
       BodyLabel {text:entry.modelData.kind||"Media";font.bold:true;color:"#173963";Layout.fillWidth:true;wrapMode:Text.WordWrap}
       BodyLabel {text:(entry.modelData.width||"—")+" × "+(entry.modelData.height||"—")+" · "+Math.round(entry.modelData.bytes/1024)+" KB";color:"#536d8b";font.pixelSize:12;wrapMode:Text.WordWrap;Layout.fillWidth:true}
       BodyLabel {visible:!!entry.modelData.album;text:entry.modelData.album||"";color:"#536d8b";Layout.fillWidth:true;elide:Text.ElideRight}
       RowLayout {TouchButton {text:"View";onClicked:window.openMedia(entry.modelData.reference)}
        Choice {visible:entry.modelData.suffix===".jpg"||entry.modelData.suffix===".png";text:"PDF";checked:window.pages.indexOf(entry.modelData.reference)>=0;onToggled:{let p=window.pages.slice();let i=p.indexOf(entry.modelData.reference);if(checked&&i<0&&p.length<20)p.push(entry.modelData.reference);else if(!checked&&i>=0)p.splice(i,1);window.pages=p}}
       }
      }
     }
    }
    Component.onCompleted:if(entry.modelData.suffix!==".pdf")Library.thumbnail(entry.modelData.reference)
    Connections {target:Library;function onThumbnailReady(reference){if(reference===entry.modelData.reference)thumb.source="image://library/"+reference+"?"+Date.now()}}
   }
   footer:TouchButton {width:list.width;visible:Library.nextOffset>=0;text:"Load more";enabled:!Library.busy;onClicked:Library.more()}
   BodyLabel {anchors.centerIn:parent;visible:list.count===0&&!Library.busy;text:Library.privateState?"Private media":"No matching camera media";color:"#617b96"}
  }
  TouchButton {visible:window.pages.length>0;text:"Export "+window.pages.length+" pages as PDF";enabled:!Library.busy;Layout.fillWidth:true;onClicked:{Library.pdf(window.pages);window.pages=[]}}
  BusyIndicator {running:Library.busy;visible:running;Layout.alignment:Qt.AlignHCenter;Layout.preferredHeight:30}
  BodyLabel {text:Library.message;color:"#476b93";wrapMode:Text.WordWrap;Layout.fillWidth:true;visible:!!text}
 }
 Popup {
  id:viewer;parent:Overlay.overlay;anchors.centerIn:parent;width:parent.width;height:parent.height;modal:true;closePolicy:Popup.CloseOnEscape
  background:Rectangle {color:"#0c1829"}
  onClosed:{player.stop();Library.clearSelection()}
  MediaPlayer {id:player;source:window.selected.suffix===".mp4"?(Library.selectedMedia.url||""):"";videoOutput:Library.videoSink;audioOutput:AudioOutput {muted:window.qaPlayVideo} onErrorOccurred:console.warn("Media playback:",errorString);onPositionChanged:function(position){if(window.qaPlayVideo&&position>=700&&playbackState===MediaPlayer.PlayingState)pause()}}
  ColumnLayout {anchors.fill:parent;spacing:10
   RowLayout {Layout.fillWidth:true
    BodyLabel {text:window.selected.kind||"Loading…";color:"white";font.pixelSize:22;Layout.fillWidth:true}
    TouchButton {text:"Back";onClicked:viewer.close()}
   }
   Image {visible:window.selected.suffix!==".mp4";source:Library.imageSource;Layout.fillWidth:true;Layout.fillHeight:true;fillMode:Image.PreserveAspectFit;cache:false;asynchronous:true}
   Image {visible:window.selected.suffix===".mp4";source:Library.videoFrameSource;Layout.fillWidth:true;Layout.fillHeight:true;fillMode:Image.PreserveAspectFit;cache:false;asynchronous:true}
   Slider {visible:window.selected.suffix===".mp4";Layout.fillWidth:true;from:0;to:Math.max(1,player.duration);value:player.position;onMoved:player.setPosition(value)}
   BodyLabel {text:(window.selected.timestamp||"")+" · "+(window.selected.camera||"");color:"#b7cee8";Layout.fillWidth:true;wrapMode:Text.WordWrap}
   Field {id:editAlbum;text:window.selected.album||"";placeholderText:"Album name";Layout.fillWidth:true;maximumLength:80}
   RowLayout {Layout.fillWidth:true
    TouchButton {text:"Save album";Layout.fillWidth:true;enabled:!!window.selected.reference;onClicked:Library.setAlbum(window.selected.reference,editAlbum.text)}
    TouchButton {text:window.selected.suffix===".mp4"?(player.playbackState===MediaPlayer.PlayingState?"Pause":"Play"):"Open";Layout.fillWidth:true;enabled:!!window.selected.reference;onClicked:{if(window.selected.suffix===".mp4"){if(player.playbackState===MediaPlayer.PlayingState)player.pause();else player.play()}else Library.openSelected()}}
   }
   RowLayout {Layout.fillWidth:true
    TouchButton {text:"Copy file";Layout.fillWidth:true;enabled:!!window.selected.reference;onClicked:Library.copyFile()}
    TouchButton {text:"Export";Layout.fillWidth:true;enabled:!!window.selected.reference;onClicked:Library.exportMedia(window.selected.reference)}
   }
   RowLayout {visible:window.selected.suffix===".jpg"||window.selected.suffix===".png";Layout.fillWidth:true
    TouchButton {text:"Scan document";Layout.fillWidth:true;enabled:!Library.busy;onClicked:{Library.process(window.selected.reference,0,true);viewer.close()}}
    TouchButton {text:"Rotate 90°";Layout.fillWidth:true;enabled:!Library.busy;onClicked:{Library.process(window.selected.reference,90,false);viewer.close()}}
   }
   TouchButton {text:"Delete";Layout.fillWidth:true;enabled:!!window.selected.reference;onClicked:confirmDelete.open()}
  }
 }
 Dialog {id:confirmDelete;parent:Overlay.overlay;anchors.centerIn:parent;title:"Delete selected camera media?";modal:true;standardButtons:Dialog.Yes|Dialog.No;onAccepted:{Library.remove(window.selected.reference);viewer.close()}}
 Connections {target:Library;function onChanged(){if(Library.privateState){confirmDelete.close();viewer.close();window.pages=[]}} function onSelected(){if(window.qaPlayVideo&&window.selected.suffix===".mp4")Qt.callLater(function(){player.play()})}}
}
