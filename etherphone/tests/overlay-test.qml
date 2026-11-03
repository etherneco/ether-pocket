import QtQuick
import QtQuick.Controls
import "../"
ApplicationWindow {
 id:root;visible:true;width:420;height:850
 property bool locked:true
 IncomingOverlay {objectName:"incomingTestOverlay";control:Phone;locked:root.locked}
}
