import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import QtQuick.Window

ApplicationWindow {
 id:window;visible:true;width:420;height:780;title:"EtherLocation Maps"
 property var region:regions.currentIndex>=0?MapStore.regions[regions.currentIndex]:null
 property int zoom:region?Math.max(region.minZoom,Math.min(region.maxZoom,8)):2
 property real latitude:0
 property real longitude:0
 property bool selected:false
 property string selection:"No device location. Choose a dataset or request a real fix."
 function worldX(lon){return (lon+180)/360*Math.pow(2,zoom)*256}
 function worldY(lat){let rad=Math.max(-85.0511,Math.min(85.0511,lat))*Math.PI/180;return (1-Math.log(Math.tan(rad)+1/Math.cos(rad))/Math.PI)/2*Math.pow(2,zoom)*256}
 function centre(lat,lon,label){latitude=lat;longitude=lon;selected=true;selection=label;reposition()}
 function reposition(){map.contentX=worldX(longitude)-map.width/2;map.contentY=worldY(latitude)-map.height/2}
 onZoomChanged:Qt.callLater(reposition)
 onRegionChanged:{if(region){let b=(region.bounds||"").split(',').map(Number);if(b.length===4)centre((b[1]+b[3])/2,(b[0]+b[2])/2,"Dataset centre · user-selected map view");else {selected=false;reposition()}}}
 Connections {target:LocationControl;function onChanged(){let p=LocationControl.position;if(p.latitude!==undefined)window.centre(p.latitude,p.longitude,(p.kind==="live"?"Live":"Last-known")+" · "+p.provider+" · ±"+Math.round(p.accuracy)+" m");else if(window.selection.indexOf("Live")===0)window.selection="Last-known map position · no current fix"}}
 header:ToolBar {RowLayout {anchors.fill:parent;Label {text:"Offline Maps";font.pixelSize:20;Layout.fillWidth:true}ToolButton {text:"Regions";onClicked:manager.open()}}}
 ColumnLayout {anchors.fill:parent;spacing:4
  ComboBox {id:regions;Layout.fillWidth:true;model:MapStore.regions;textRole:"name";onActivated:window.region=MapStore.regions[currentIndex]}
  Label {Layout.fillWidth:true;Layout.margins:8;wrapMode:Text.Wrap;text:window.selection}
  Label {Layout.fillWidth:true;Layout.margins:8;wrapMode:Text.Wrap;text:LocationControl.message;color:"#9c3030";visible:text.length>0}
  RowLayout {Layout.fillWidth:true
   Button {text:"Permission";onClicked:LocationControl.requestPermission(precise.checked)}
   CheckBox {id:precise;text:"Precise";checked:false}
   Button {text:"Locate";enabled:!!LocationControl.state.config&&LocationControl.state.config.enabled;onClicked:LocationControl.startUpdates(precise.checked)}
   Button {text:"Stop";onClicked:LocationControl.stopUpdates()}
  }
  TextField {id:search;Layout.fillWidth:true;placeholderText:"Search optional offline place index";onAccepted:if(window.region)MapStore.search(window.region.id,text)}
  Repeater {model:MapStore.results;delegate:Button {required property var modelData;Layout.fillWidth:true;text:modelData.name;onClicked:window.centre(modelData.latitude,modelData.longitude,"Offline place · "+modelData.name)}}
  Item {Layout.fillWidth:true;Layout.fillHeight:true;clip:true
   Flickable {id:map;anchors.fill:parent;contentWidth:256*Math.pow(2,window.zoom);contentHeight:contentWidth;boundsBehavior:Flickable.StopAtBounds;onWidthChanged:Qt.callLater(window.reposition);onHeightChanged:Qt.callLater(window.reposition)
    readonly property int startX:Math.max(0,Math.floor(contentX/256))
    readonly property int startY:Math.max(0,Math.floor(contentY/256))
    readonly property int columns:Math.ceil(width/256)+2
    Repeater {model:map.columns*(Math.ceil(map.height/256)+2)
     delegate:Image {required property int index;readonly property int tx:map.startX+index%map.columns;readonly property int ty:map.startY+Math.floor(index/map.columns)
      x:tx*256;y:ty*256;width:256;height:256;cache:false;asynchronous:false
      source:window.region&&tx<Math.pow(2,window.zoom)&&ty<Math.pow(2,window.zoom)?"image://tiles/"+window.region.id+"/"+window.zoom+"/"+tx+"/"+ty:""
     }
    }
    Rectangle {visible:LocationControl.position.latitude!==undefined;readonly property var fix:LocationControl.position;readonly property real accuracyPixels:(fix.accuracy||0)/(156543.03392*Math.cos((fix.latitude||0)*Math.PI/180)/Math.pow(2,window.zoom));x:window.worldX(fix.longitude||0)-width/2;y:window.worldY(fix.latitude||0)-height/2;width:Math.min(map.contentWidth,accuracyPixels*2);height:width;radius:width/2;color:"#33448cdd";border.color:"#448cdd"}
    Rectangle {visible:window.selected;x:window.worldX(window.longitude)-7;y:window.worldY(window.latitude)-7;width:14;height:14;radius:7;color:LocationControl.position.latitude!==undefined?"#2873cc":"#a16b28";border.color:"white";border.width:2}
    Repeater {model:LocationControl.management.history||[];delegate:Rectangle {required property var modelData;x:window.worldX(modelData.longitude)-3;y:window.worldY(modelData.latitude)-3;width:6;height:6;radius:3;color:"#af4c89"}}
    MouseArea {anchors.fill:parent;onDoubleClicked:mouse=>{let n=Math.pow(2,window.zoom);let lon=mouse.x/(256*n)*360-180;let lat=Math.atan(Math.sinh(Math.PI*(1-2*mouse.y/(256*n))))*180/Math.PI;window.centre(lat,lon,"User-selected · "+lat.toFixed(5)+", "+lon.toFixed(5)+" · not a device fix")}}
   }
   Label {anchors.centerIn:parent;visible:!window.region;text:"Import a licensed raster MBTiles dataset\nMap viewing works without GNSS or internet";horizontalAlignment:Text.AlignHCenter;wrapMode:Text.Wrap;width:parent.width-40}
   Column {anchors.right:parent.right;anchors.bottom:parent.bottom;anchors.margins:10;Button {text:"+";enabled:!!window.region&&window.zoom<window.region.maxZoom;onClicked:window.zoom++}Button {text:"−";enabled:!!window.region&&window.zoom>window.region.minZoom;onClicked:window.zoom--}}
  }
  Label {Layout.fillWidth:true;Layout.margins:8;wrapMode:Text.Wrap;text:window.region?window.region.attribution:"No map dataset installed";textFormat:Text.PlainText;font.pixelSize:11}
  Label {Layout.fillWidth:true;Layout.margins:8;wrapMode:Text.Wrap;text:"Map viewing and position tracking only. Routing and turn-by-turn navigation unavailable.";font.pixelSize:11}
 }
 Popup {id:manager;anchors.centerIn:parent;width:Math.min(window.width-20,540);height:Math.min(window.height-40,700);modal:true
  ScrollView {anchors.fill:parent;contentWidth:availableWidth;ColumnLayout {width:parent.width
   Label {text:"Offline regions";font.pixelSize:20}
   Label {text:"Saved places and history";font.pixelSize:17}
   TextField {id:placeName;Layout.fillWidth:true;placeholderText:"Name for selected map point"}
   Button {text:"Save selected point";enabled:window.selected;onClicked:MapStore.savePlace(placeName.text,window.latitude,window.longitude)}
   Repeater {model:MapStore.savedPlaces;delegate:RowLayout {required property var modelData;required property int index;Layout.fillWidth:true;Button {text:modelData.name;Layout.fillWidth:true;onClicked:{window.centre(modelData.latitude,modelData.longitude,"Saved place · user-supplied · "+modelData.name);manager.close()}}Button {text:"Delete";onClicked:MapStore.deletePlace(index)}}}
   Button {text:"Load permitted history on map";onClicked:LocationControl.mapHistory(precise.checked)}
   Label {Layout.fillWidth:true;wrapMode:Text.Wrap;text:"History requires a location permission and an unlocked device. Points are purple; approximate grants also reduce history precision."}
   Label {Layout.fillWidth:true;wrapMode:Text.Wrap;text:"Import PNG/JPEG MBTiles. Vector tiles need another renderer. No public tile scraping. Dataset limit 2 GiB; storage quota 8 GiB."}
   Repeater {model:MapStore.regions;delegate:RowLayout {required property var modelData;Layout.fillWidth:true;Label {text:modelData.name+" · "+(modelData.size/1048576).toFixed(1)+" MiB";Layout.fillWidth:true;wrapMode:Text.Wrap}Button {text:"Delete";enabled:!MapStore.busy;onClicked:MapStore.remove(modelData.id)}}}
   TextField {id:file;Layout.fillWidth:true;placeholderText:"Local /path/to/region.mbtiles"}
   CheckBox {id:license;text:"I have permission for offline use"}
   Button {text:"Import region";enabled:!MapStore.busy&&license.checked;onClicked:MapStore.importRegion(file.text,license.checked)}
   TextField {id:url;Layout.fillWidth:true;placeholderText:"Licensed direct HTTPS .mbtiles URL"}
   TextField {id:sha;Layout.fillWidth:true;placeholderText:"Expected SHA256"}
   Button {text:"Estimate download size";enabled:!MapStore.busy;onClicked:MapStore.estimate(url.text)}
   Label {Layout.fillWidth:true;wrapMode:Text.Wrap;text:"Downloads disclose the dataset request to its server. Size is checked before transfer; progress appears below. Resume uses the same URL and checksum."}
   RowLayout {Button {text:"Download / resume";enabled:!MapStore.busy&&license.checked;onClicked:MapStore.download(url.text,sha.text,license.checked)}Button {text:"Pause";enabled:MapStore.busy;onClicked:MapStore.pause()}}
   Label {text:MapStore.message;Layout.fillWidth:true;wrapMode:Text.Wrap}
   Button {text:"Close";onClicked:manager.close()}
  }}
 }
}
