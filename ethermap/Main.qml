import QtQuick
import QtQuick.Controls
import QtQuick.Controls as C
import QtQuick.Layouts
import QtQuick.Window

ApplicationWindow {
 id:win;visible:true;width:420;height:820;minimumWidth:320;minimumHeight:480;title:"EtherMAP";color:"#101c28"
 palette.window:"#142332";palette.windowText:"#edf6f7";palette.base:"#0d1925";palette.text:"#edf6f7";palette.placeholderText:"#91aab9";palette.button:"#22394b";palette.buttonText:"#edf6f7";palette.highlight:"#61d8be";palette.highlightedText:"#10251f";font.pixelSize:14
 component Button:C.Button {implicitHeight:Math.max(48,implicitContentHeight+24);implicitWidth:Math.max(48,implicitContentWidth+24);padding:12;focusPolicy:Qt.StrongFocus}
 property var s:Maps.state||({})
 property var settings:s.settings||({})
 property var position:s.position||({})
 property var manual:s.manual||({})
 property var region:{let rows=s.regions||[];let wanted=settings.region||"auto";if(wanted==="online")return null;return rows.find(r=>r.id===wanted)||rows.find(r=>r.name.indexOf("OpenStreetMap")>=0)||rows[0]||null}
 property string centredRegionId:""
 property bool online:!!settings.onlineTiles
 property bool follow:false
 property real lastStamp:0
 property real lat:51.5074
 property real lon:-0.1278
 property real bearing:0
 property int zoom:region?Math.max(region.minZoom,Math.min(region.maxZoom,12)):12
 property int selectedTrack:-1
 property real routeLat:0
 property real routeLon:0
 property bool startSet:false
 readonly property real world:256*Math.pow(2,zoom)
 function xOf(lon){return (lon+180)/360*world}
 function yOf(lat){let r=Math.max(-85.0511,Math.min(85.0511,lat))*Math.PI/180;return (1-Math.log(Math.tan(r)+1/Math.cos(r))/Math.PI)/2*world}
 function centre(a,b){lat=a;lon=b;Qt.callLater(reposition)}
 function reposition(){map.contentX=xOf(lon)-map.width/2;map.contentY=yOf(lat)-map.height/2;lines.requestPaint()}
 function pin(a,b){Maps.send("manual",{latitude:a,longitude:b});centre(a,b)}
 function configure(k,v){let a={};a[k]=v;Maps.send("settings",a)}
 function locate(){follow=true;Maps.send("mode",{value:"Follow Me"});if(position.latitude!==undefined)centre(position.latitude,position.longitude)}
 function openSettings(){settingsPanel.open()}
 function syncRegion(){let rows=s.regions||[];let wanted=settings.region||"auto";let index=wanted==="online"?-1:rows.findIndex(r=>r.id===wanted);if(wanted!=="online"&&index<0){index=rows.findIndex(r=>r.name.indexOf("OpenStreetMap")>=0);if(index<0&&rows.length)index=0}if(regionPicker.currentIndex!==index)regionPicker.currentIndex=index}
 onSettingsChanged:Qt.callLater(syncRegion)
 function accuracy(p){return p.accuracy!==undefined&&p.accuracy!==null?"±"+Math.round(p.accuracy)+" m":"accuracy unknown"}
 function source(p){if(p.latitude===undefined)return "No permitted device position";return (p.provider==="ip"?"IP · approximate region":p.kind==="last-known"?"Last-known · "+p.provider:p.provider)+(p.stale?" · stale":"")}
 onActiveChanged:Maps.send("focus",{active:active})
 onZoomChanged:Qt.callLater(reposition)
 onRegionChanged:{let id=region?region.id:"";if(id!==centredRegionId){centredRegionId=id;if(region){let b=(region.bounds||"").split(',').map(Number);zoom=Math.max(region.minZoom,Math.min(region.maxZoom,16));if(b.length===4)centre((b[1]+b[3])/2,(b[0]+b[2])/2)}}}
 onPositionChanged:{if(position.timestamp!==lastStamp&&position.latitude!==undefined){lastStamp=position.timestamp;if(follow)centre(position.latitude,position.longitude)}}
 Connections {target:Maps;function onChanged(){lines.requestPaint()}}
 Component.onCompleted:Qt.callLater(reposition)

 Item {
  anchors.fill:parent;clip:true
  Item {id:mapSurface;anchors.fill:parent;rotation:win.bearing
   Flickable {id:map;objectName:"mapViewport";anchors.fill:parent;contentWidth:win.world;contentHeight:win.world;boundsBehavior:Flickable.StopAtBounds;onMovementStarted:win.follow=false;onContentXChanged:lines.requestPaint();onContentYChanged:lines.requestPaint();onWidthChanged:Qt.callLater(win.reposition);onHeightChanged:Qt.callLater(win.reposition)
    readonly property int startX:Math.max(0,Math.floor(contentX/256))
    readonly property int startY:Math.max(0,Math.floor(contentY/256))
    readonly property int columns:Math.ceil(width/256)+1
    Repeater {model:map.columns*(Math.ceil(map.height/256)+1)
     delegate:Image {required property int index;readonly property int tx:map.startX+index%map.columns;readonly property int ty:map.startY+Math.floor(index/map.columns);x:tx*256;y:ty*256;width:256;height:256;cache:true;asynchronous:false
      source:tx>=Math.pow(2,win.zoom)||ty>=Math.pow(2,win.zoom)?"":win.region?"image://tiles/"+win.region.id+"/"+win.zoom+"/"+tx+"/"+ty:win.online?(win.settings.tileTemplate||"").replace("{z}",win.zoom).replace("{x}",tx).replace("{y}",ty):""
     }
    }
    Rectangle {visible:win.position.latitude!==undefined&&win.position.accuracy!==null&&win.position.accuracy!==undefined;readonly property real pixels:(win.position.accuracy||0)/(156543.03392*Math.max(0.01,Math.cos((win.position.latitude||0)*Math.PI/180))/Math.pow(2,win.zoom));width:Math.min(win.world,pixels*2);height:width;radius:width/2;x:win.xOf(win.position.longitude||0)-width/2;y:win.yOf(win.position.latitude||0)-height/2;color:win.position.provider==="ip"?"#35e1a74b":"#33458fff";border.color:win.position.provider==="ip"?"#d9a44b":"#458fff"}
    Rectangle {visible:win.position.latitude!==undefined&&win.position.provider!=="ip";x:win.xOf(win.position.longitude||0)-8;y:win.yOf(win.position.latitude||0)-8;width:16;height:16;radius:8;color:win.position.kind==="last-known"?"#8e9ea7":"#398aff";border.width:3;border.color:"white"}
    Label {visible:win.position.provider==="ip";x:win.xOf(win.position.longitude||0)-70;y:win.yOf(win.position.latitude||0)-14;width:140;horizontalAlignment:Text.AlignHCenter;text:"≈ approximate region";color:"#502e04";font.bold:true;background:Rectangle {color:"#f6d99b";radius:8}}
    Rectangle {visible:win.manual.latitude!==undefined;x:win.xOf(win.manual.longitude||0)-7;y:win.yOf(win.manual.latitude||0)-7;width:14;height:14;rotation:45;color:"#ec9f5e";border.color:"#fff2df";border.width:2}
    Repeater {model:win.s.places||[];delegate:Rectangle {required property var modelData;x:win.xOf(modelData.longitude)-5;y:win.yOf(modelData.latitude)-5;width:10;height:10;radius:3;color:"#8549a9";border.color:"white"}}
    MouseArea {anchors.fill:parent;onDoubleClicked:mouse=>{let n=win.world;win.follow=false;win.pin(Math.atan(Math.sinh(Math.PI*(1-2*mouse.y/n)))*180/Math.PI,mouse.x/n*360-180)}}
   }
   Canvas {id:lines;anchors.fill:parent;enabled:false
    onPaint:{let c=getContext("2d");c.clearRect(0,0,width,height);c.lineWidth=4;c.lineJoin="round";function draw(rows,color,segments){c.strokeStyle=color;c.beginPath();let last=null;for(let p of rows){let x=win.xOf(p.longitude)-map.contentX,y=win.yOf(p.latitude)-map.contentY;if(!last||(segments&&last.segment!==p.segment)||Math.abs(p.longitude-last.longitude)>180)c.moveTo(x,y);else c.lineTo(x,y);last=p}c.stroke()}draw((win.s.route||{}).line||[],"#8d61ce",false);draw(win.s.trail||[],"#0eaf90",true)}
   }
  }
  Label {visible:!win.region&&!win.online;anchors.centerIn:parent;width:parent.width-60;text:"Your map, your location\n\nEnable online OSM tiles or import a licensed offline region in Maps settings.\n\nDouble-tap the map to select a manual point.";horizontalAlignment:Text.AlignHCenter;wrapMode:Text.Wrap;color:"#a5bac8";font.pixelSize:16}
  Rectangle {anchors.top:parent.top;width:parent.width;height:mapHeader.implicitHeight+28;color:"#e6101c28"}
  ColumnLayout {id:mapHeader;anchors.top:parent.top;anchors.left:parent.left;anchors.right:parent.right;anchors.margins:14;spacing:8
   RowLayout {Layout.fillWidth:true
    Label {text:"ETHER";font.letterSpacing:2;font.pixelSize:18;font.bold:true;color:"#eff8f7"}
    Label {text:"MAP";font.letterSpacing:2;font.pixelSize:18;font.bold:true;color:"#61d8be";Layout.fillWidth:true}
    Label {text:win.region?"OFFLINE":"OSM";color:"#8cacbd";font.pixelSize:11}
    ToolButton {implicitWidth:Math.max(48,implicitContentWidth+24);implicitHeight:48;text:"☰";Accessible.name:"Maps settings";onClicked:settingsPanel.open()}
   }
   RowLayout {Layout.fillWidth:true
    TextField {id:search;implicitHeight:48;Layout.fillWidth:true;placeholderText:"Search places or lat, lon";onAccepted:Maps.send("search",{query:text,online:false})}
    Button {text:"Go";onClicked:Maps.send("search",{query:search.text,online:false})}
   }
   Repeater {model:(win.s.results||[]).slice(0,4);delegate:Button {required property var modelData;Layout.fillWidth:true;text:modelData.name;contentItem:Label {text:parent.text;elide:Text.ElideRight;verticalAlignment:Text.AlignVCenter}onClicked:{win.follow=false;win.pin(modelData.latitude,modelData.longitude)}}}
  }
  Column {anchors.right:parent.right;anchors.verticalCenter:parent.verticalCenter;anchors.margins:14;spacing:7
   Button {text:"+";width:48;enabled:win.zoom<(win.region?win.region.maxZoom:19);onClicked:win.zoom++}
   Button {text:"−";width:48;enabled:win.zoom>(win.region?win.region.minZoom:0);onClicked:win.zoom--}
   Button {text:"↻";width:48;Accessible.name:"Rotate map 30 degrees";onClicked:win.bearing=(win.bearing+30)%360}
   Button {text:"N";width:48;onClicked:win.bearing=0}
   Button {text:"◎";width:48;Accessible.name:"Locate me";onClicked:win.locate()}
  }
  Rectangle {anchors.left:parent.left;anchors.right:parent.right;anchors.bottom:parent.bottom;height:details.implicitHeight+24;color:"#f2101c28";radius:20
   ColumnLayout {id:details;anchors.left:parent.left;anchors.right:parent.right;anchors.bottom:parent.bottom;anchors.margins:12;spacing:5
    RowLayout {Layout.fillWidth:true
     Rectangle {width:8;height:8;radius:4;color:win.s.recording?"#f27169":"#61d8be"}
     Label {text:win.s.recording?(win.s.paused?"Recording paused":win.s.interrupted?"Track interrupted · waiting for real fix":"Recording local track"):win.s.mode||"Off";Layout.fillWidth:true;font.bold:true}
     ToolButton {implicitWidth:Math.max(48,implicitContentWidth+24);implicitHeight:48;text:"Details";onClicked:infoPanel.open()}
    }
    Label {Layout.fillWidth:true;text:win.source(win.position);color:"#9fbccc";wrapMode:Text.Wrap}
    Label {Layout.fillWidth:true;visible:win.position.provider==="ip";text:"City/network exit estimate. VPNs and mobile networks can mislead.";wrapMode:Text.Wrap;color:"#dfb66d";font.pixelSize:11}
    RowLayout {Layout.fillWidth:true;visible:!!win.s.recording
     Label {text:((win.s.summary||{}).distance/1000||0).toFixed(2)+" km";font.pixelSize:22;Layout.fillWidth:true}
     Label {text:Math.floor((win.s.elapsed||0)/60)+" min · "+((win.position.speed||0)*3.6).toFixed(1)+" km/h";color:"#a6c0ce"}
    }
    RowLayout {Layout.fillWidth:true
     Button {text:"Follow";Layout.fillWidth:true;onClicked:win.locate()}
     Button {text:win.s.recording?(win.s.paused?"Resume":"Pause"):"Record";Layout.fillWidth:true;onClicked:{win.follow=true;Maps.send(win.s.recording?(win.s.paused?"resume":"pause"):"mode",win.s.recording?{}:{value:"Track Route"})}}
     Button {text:"Stop";Layout.fillWidth:true;onClicked:{win.follow=false;Maps.send("mode",{value:"Off"})}}
    }
    Label {text:win.s.message||"";visible:text.length>0;Layout.fillWidth:true;wrapMode:Text.Wrap;color:"#efbc87";font.pixelSize:11;maximumLineCount:3;elide:Text.ElideRight}
    Label {Layout.fillWidth:true;text:win.region?win.region.attribution:win.online?win.settings.tileAttribution||"© OpenStreetMap contributors":"No map dataset selected";textFormat:Text.PlainText;color:"#a5bac8";font.pixelSize:10;wrapMode:Text.Wrap}
   }
  }
  Rectangle {visible:!!win.s.locked;anchors.fill:parent;color:"#101c28";z:30;Label {anchors.centerIn:parent;text:"Unlock EtherLock to use EtherMAP";color:"#edf6f7"}MouseArea {anchors.fill:parent}}
 }

 component Sheet:Popup {anchors.centerIn:Overlay.overlay;width:Math.min(win.width-20,520);height:Math.min(win.height-28,760);modal:true;closePolicy:Popup.CloseOnEscape|Popup.CloseOnPressOutside}
 component Heading:Label {font.pixelSize:20;font.bold:true;Layout.fillWidth:true;color:"#61d8be";textFormat:Text.PlainText}
 component Note:Label {Layout.fillWidth:true;wrapMode:Text.Wrap;color:"#a9bfcc";font.pixelSize:12;textFormat:Text.PlainText}
 component Input:TextField {Layout.fillWidth:true;implicitHeight:42}
 component Action:Button {Layout.fillWidth:true}
 Sheet {id:settingsPanel
  ScrollView {anchors.fill:parent;contentWidth:availableWidth;ColumnLayout {width:parent.width;spacing:9
   Heading {text:"Maps settings"}
   Note {text:"Device location, source selection, accuracy and permissions are managed in EtherShell → Settings → Location. This panel controls Maps only."}
   Action {text:"Request location permission";onClicked:Maps.send("permission")}
   CheckBox {text:"Request precise location";checked:!!win.settings.precise;onClicked:win.configure("precise",checked)}
   CheckBox {text:"Enable local track history";checked:!!win.settings.history;onClicked:win.configure("history",checked)}
   Note {text:"Off by default. Record is an explicit start; local tracks are never uploaded. Only fresh, precise fixes with accuracy ≤100 m enter tracks. IP and manual points never enter tracks."}
   CheckBox {text:"Allow screen-off / background tracking";checked:!!win.settings.background;onClicked:win.configure("background",checked)}
   Note {text:"Also requires an explicit background grant in Location settings. Suspend interrupts tracking; kernel wake and continuous background recording are not guaranteed."}
   RowLayout {Label {text:"Retention"}ComboBox {model:[1,7,30,90];currentIndex:Math.max(0,[1,7,30,90].indexOf(win.settings.retention));onActivated:win.configure("retention",Number(currentText))}Label {text:"days"}}
   Heading {text:"Map layers & offline regions"}
   ComboBox {id:regionPicker;Layout.fillWidth:true;model:win.s.regions||[];textRole:"name";displayText:win.region?win.region.name:"Select an offline region";onModelChanged:Qt.callLater(win.syncRegion);onActivated:win.configure("region",model[currentIndex].id)}
   Action {text:"Use online layer";onClicked:win.configure("region","online")}
   CheckBox {text:"Allow online tiles (visible map only)";checked:win.online;onClicked:win.configure("onlineTiles",checked)}
   Note {text:"Online tiles disclose the viewed area to the tile provider. Public OSM has no bulk or offline download. Satellite/terrain/cycle layers require a licensed configured source and its attribution."}
   Input {id:tileTemplate;placeholderText:"HTTPS tile template {z}/{x}/{y}";text:win.settings.tileTemplate||""}
   Input {id:tileCredit;placeholderText:"Required provider attribution";text:win.settings.tileAttribution||""}
   Action {text:"Apply online layer";onClicked:Maps.send("settings",{tileTemplate:tileTemplate.text,tileAttribution:tileCredit.text})}
   Repeater {model:win.s.regions||[];delegate:RowLayout {required property var modelData;Layout.fillWidth:true;Note {text:modelData.name+" · "+(modelData.size/1048576).toFixed(1)+" MiB"}Button {text:"Delete";enabled:!win.s.busy;onClicked:Maps.send("deleteRegion",{id:modelData.id})}}}
   Input {id:mapFile;placeholderText:"Local raster .mbtiles path"}
   CheckBox {id:license;text:"Dataset permits offline use"}
   Action {text:"Import offline region";enabled:license.checked&&!win.s.busy;onClicked:Maps.send("importRegion",{path:mapFile.text,license:license.checked})}
   Input {id:mapUrl;placeholderText:"Direct licensed HTTPS dataset URL"}
   Input {id:mapHash;placeholderText:"Expected SHA256"}
   Action {text:"Download / resume region";enabled:license.checked&&!win.s.busy;onClicked:Maps.send("download",{url:mapUrl.text,sha256:mapHash.text,license:license.checked})}
   Action {text:"Pause download";enabled:!!win.s.busy;onClicked:Maps.send("downloadPause")}
   Note {text:(win.s.progress||{}).state?JSON.stringify(win.s.progress):"Select an area by obtaining a licensed region dataset. Raster PNG/JPEG MBTiles only; vector packages are rejected. 2 GiB per dataset, 8 GiB total."}
   Heading {text:"Optional IP fallback"}
   Note {text:"The configured server learns your public IP. It may identify only a city, carrier or VPN exit. No observations or tracks are uploaded. Requires Location permission. After consent, Locate/Follow/Record can request fallback automatically; Request IP estimate also requests it explicitly."}
   Input {id:ipEndpoint;placeholderText:"HTTPS IP JSON endpoint";text:win.settings.ipEndpoint||""}
   CheckBox {id:ipConsent;text:"I consent to external IP geolocation";checked:!!win.settings.ipConsent;onClicked:Maps.send("settings",{ipEndpoint:ipEndpoint.text,ipConsent:checked})}
   Action {text:"Save IP endpoint";onClicked:win.configure("ipEndpoint",ipEndpoint.text)}
   Action {text:"Request IP estimate";enabled:!!win.settings.ipConsent;onClicked:Maps.send("ip")}
   Heading {text:"Search & routing providers"}
   Note {text:"Queries disclose searched addresses or route endpoints to these servers. Configure permitted services. Search is submit-only with caching; no autocomplete. Routing URLs must each point to a server prepared for that travel profile."}
   CheckBox {text:"I consent to external search / routing";checked:!!win.settings.externalConsent;onClicked:win.configure("externalConsent",checked)}
   Input {id:geocoder;placeholderText:"Nominatim-compatible HTTPS /search URL";text:win.settings.geocoder||""}
   Input {id:driving;placeholderText:"OSRM driving /route/v1/driving URL";text:win.settings.driving||""}
   Input {id:walking;placeholderText:"OSRM walking profile endpoint";text:win.settings.walking||""}
   Input {id:cycling;placeholderText:"OSRM cycling profile endpoint";text:win.settings.cycling||""}
   Action {text:"Save providers";onClicked:Maps.send("settings",{geocoder:geocoder.text,driving:driving.text,walking:walking.text,cycling:cycling.text})}
   Action {text:"Search online for entered query";enabled:!!win.settings.externalConsent&&!win.s.busy;onClicked:{Maps.send("search",{query:search.text,online:true});settingsPanel.close()}}
   Heading {text:"Storage & diagnostics"}
   Note {text:"Map storage: "+(win.s.regions||[]).reduce((a,r)=>a+r.size,0)/1048576+" MiB · "+(win.s.tracks||[]).length+" tracks"}
   Action {text:"Delete local tracks, places and search cache";onClicked:deleteDialog.open()}
   Action {text:"Location diagnostics";onClicked:{Maps.send("diagnostics");infoPanel.open()}}
   Action {text:"Close";onClicked:settingsPanel.close()}
  }}
 }
 Dialog {id:deleteDialog;anchors.centerIn:Overlay.overlay;width:Math.min(win.width-28,420);height:230;title:"Delete Maps history?";modal:true;standardButtons:Dialog.Ok|Dialog.Cancel;contentItem:Label {text:"Delete all local tracks, saved places and cached searches. Offline regions remain available.";wrapMode:Text.Wrap}onAccepted:Maps.send("clear")}
 Sheet {id:infoPanel
  ScrollView {anchors.fill:parent;contentWidth:availableWidth;ColumnLayout {width:parent.width;spacing:8
   Heading {text:"Position & tracking"}
   Note {visible:win.position.provider==="ip";text:[win.position.city,win.position.region,win.position.country,win.position.service].filter(v=>!!v).join(" · ")}
   Note {text:win.source(win.position)+"\n"+(win.position.latitude!==undefined?win.position.latitude.toFixed(5)+", "+win.position.longitude.toFixed(5)+"\n"+win.accuracy(win.position)+" · age "+Math.round(win.position.age||0)+" s":"No permitted position")+"\nAltitude: "+(win.position.altitude===undefined?"unavailable":win.position.altitude+" m")+" · Heading: "+(win.position.heading===undefined?"unavailable":win.position.heading+"°")}
   Note {text:"GNSS: "+((win.s.location||{}).fixStatus||"unavailable")+" · satellites visible: "+((win.s.location||{}).satellitesVisible===null?"unknown":(win.s.location||{}).satellitesVisible||"unknown")+"\nSampling: "+(win.s.interval||10)+" s · background: "+(win.settings.background?"requested":"off")}
   Heading {text:"Manual point & saved places"}
   Input {id:latitude;placeholderText:"Latitude"}
   Input {id:longitude;placeholderText:"Longitude"}
   Action {text:"Select manual coordinates";onClicked:{win.pin(Number(latitude.text),Number(longitude.text));infoPanel.close()}}
   Input {id:placeName;placeholderText:"Place name"}
   Action {text:"Save selected manual point";enabled:win.manual.latitude!==undefined;onClicked:Maps.send("savePlace",{name:placeName.text,latitude:win.manual.latitude,longitude:win.manual.longitude})}
   Repeater {model:win.s.places||[];delegate:RowLayout {required property var modelData;Layout.fillWidth:true;Action {text:modelData.name;onClicked:{win.pin(modelData.latitude,modelData.longitude);infoPanel.close()}}Button {text:"×";onClicked:Maps.send("deletePlace",{id:modelData.id})}}}
   Heading {text:"Local tracks & GPX"}
   Repeater {model:win.s.tracks||[];delegate:RowLayout {required property var modelData;Layout.fillWidth:true;Action {text:modelData.name+(modelData.imported?" · imported":"");onClicked:{win.selectedTrack=modelData.id;Maps.send("viewTrack",{id:modelData.id});infoPanel.close()}}Button {text:"GPX";onClicked:Maps.send("export",{id:modelData.id})}Button {text:"×";onClicked:Maps.send("deleteTrack",{id:modelData.id})}}}
   Input {id:trackName;placeholderText:"New name for selected track"}
   Action {text:"Rename selected track";enabled:win.selectedTrack>=0;onClicked:Maps.send("renameTrack",{id:win.selectedTrack,name:trackName.text})}
   Input {id:gpxPath;placeholderText:"Local /path/to/track.gpx"}
   Action {text:"Import GPX";onClicked:Maps.send("import",{path:gpxPath.text})}
   Heading {text:"Route planning"}
   Note {text:"Select a start point and destination manually. Server routes use the configured profile. ETA has no live traffic. Offline routing and turn-by-turn guidance are unavailable."}
   Action {text:win.startSet?"Start set · change to selected point":"Use selected point as start";enabled:win.manual.latitude!==undefined;onClicked:{win.routeLat=win.manual.latitude;win.routeLon=win.manual.longitude;win.startSet=true}}
   ComboBox {id:travel;model:["walking","cycling","driving"]}
   Action {text:"Route to selected point";enabled:win.startSet&&win.manual.latitude!==undefined&&!win.s.busy;onClicked:Maps.send("route",{profile:travel.currentText,startLatitude:win.routeLat,startLongitude:win.routeLon,endLatitude:win.manual.latitude,endLongitude:win.manual.longitude})}
   Note {text:(win.s.route||{}).distance!==undefined?((win.s.route.distance/1000).toFixed(1)+" km · "+Math.round(win.s.route.duration/60)+" min · no live traffic"):"No calculated route"}
   Repeater {model:(win.s.route||{}).steps||[];delegate:Note {required property var modelData;text:modelData.text+" · "+Math.round(modelData.distance)+" m"}}
   Action {text:"Follow position with route shown";enabled:!!(win.s.route||{}).line;onClicked:{win.follow=true;Maps.send("mode",{value:"Navigation"});infoPanel.close()}}
   Action {text:"Clear route";onClicked:Maps.send("routeClear")}
   Note {text:win.s.message||""}
   Action {text:"Close";onClicked:infoPanel.close()}
  }}
 }
}
