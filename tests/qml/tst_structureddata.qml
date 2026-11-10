import QtQuick
import QtTest
import "../../qml" as UI
import "../../qml/StructuredData.js" as Data

TestCase {
    name: "StructuredData"
    width: 360
    height: 640
    when: windowShown
    UI.DataView {
        id: view
        width: 336
        tokens: ({soft:"#eef3fa", line:"#dce3ec", muted:"#606f80", ink:"#102a4a", caption:12})
        value: ({capacity:2, connected:false, memory:{totalBytes:2147483648}, modes:["Balanced", "Power saver"]})
    }
    function test_values() {
        compare(Data.text(false), "No");
        compare(Data.text(0), "0");
        compare(Data.text(null), "Unavailable");
        compare(Data.text([]), "None");
        compare(Data.text("ordinary {text}"), "ordinary {text}");
        compare(Data.text('{"online":true}'), "Online: Yes");
        verify(Data.text({totalBytes:2147483648}).indexOf("2 GiB") >= 0);
        compare(Data.fields({cpuC:82.5})[0].title, "CPU temperature (°C)");
        compare(Data.fields({value:0})[0].value, "0");
        compare(Data.fields({value:false})[0].value, "No");
        compare(Data.fields({nested:{enabled:true}})[0].title, "Nested › Enabled");
    }
    function test_phone_layout() {
        waitForRendering(view);
        verify(view.implicitHeight > 0);
        verify(view.implicitHeight < height);
        for (var i=0; i<view.children.length; i++) {
            var child = view.children[i];
            if (child.width > 0) verify(child.width <= view.width);
        }
    }
}
