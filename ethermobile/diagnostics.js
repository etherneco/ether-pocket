.pragma library

function label(key) {
    var names = {ipv4:"IPv4",ipv6:"IPv6",dns:"DNS servers",addresses:"IP addresses",
        routes:"Routes",gateway:"Gateway",interface:"Network interface",drivers:"Drivers",
        kernel:"Kernel",architecture:"Architecture",machine:"Device",soc_id:"Chipset",
        device_tree_model:"Hardware model",cmdline:"Boot configuration",read_only:"Read-only check",
        output:"System report",note:"What this means",exit:"Exit code",status:"Check result",
        revision:"Firmware version",ipa_files:"Packet firmware files",capabilities:"Capabilities",
        session:"Data session",registration:"Network registration",system_info:"Network details",
        interfaces:"Network interfaces",links:"Interface state",addresses4:"IPv4 addresses",
        transport:"Control connection",name:"Name",protocol:"Protocol",state:"State",
        selected:"Selected modem",manufacturer:"Manufacturer",model:"Model",firmware:"Firmware",
        signalMetrics:"Signal measurements",powerState:"Radio power",signal:"Signal strength",
        selectedAdapter:"Adapter",message:"Message",error:"Problem",connected:"Connected",
        powered:"Radio enabled",available:"Available",address:"Address",prefix:"Prefix length",
        metric:"Route priority",destination:"Destination",method:"Configuration method",
        rsrp:"Reference signal power (dBm)",rsrq:"Reference signal quality (dB)",rssi:"Received signal (dBm)",
        snr:"Signal-to-noise ratio (dB)",sinr:"Signal-to-interference ratio (dB)"};
    return names[key] || String(key).replace(/([a-z])([A-Z])/g,"$1 $2").replace(/[_-]/g," ").replace(/^./,function(c){return c.toUpperCase()});
}

function text(value) {
    if (value === undefined || value === null || value === "") return "Not reported";
    if (typeof value === "boolean") return value ? "Yes" : "No";
    if (Array.isArray(value)) return value.length ? value.map(text).join("\n") : "None reported";
    if (typeof value === "object") {
        if (value.label) return String(value.label);
        if (value.name && value.protocol) return value.name + " — " + value.protocol;
        if (value.address) return value.address + (value.prefix !== undefined ? "/" + value.prefix : "");
        if (value.uri) return String(value.uri);
        var keys = Object.keys(value);
        return keys.length ? keys.map(function(k){return label(k) + ": " + text(value[k]);}).join("\n") : "None reported";
    }
    return String(value);
}

// Separate labelled fields, never object/array syntax. Preserve unknown evidence
// instead of silently inventing success or dropping a provider's new fields.
function rows(value, prefix) {
    var result = [];
    if (value && typeof value === "object" && !Array.isArray(value)) {
        Object.keys(value).forEach(function(key){
            if (key === "exit" || (key === "status" && value.output !== undefined)) return;
            var title = prefix ? prefix + " · " + label(key) : label(key);
            var child = value[key];
            if (child && typeof child === "object" && !Array.isArray(child))
                result = result.concat(rows(child, title));
            else result.push({label:title,value:text(child)});
        });
    } else result.push({label:prefix || "Details",value:text(value)});
    return result.length ? result : [{label:prefix || "Details",value:"No additional information reported"}];
}

function status(value) {
    return {Working:"Working",Blocked:"Needs attention",Unknown:"Not verified",
        Missing:"Not installed","Partially working":"Partly available"}[value] || value || "Not verified";
}

function summary(stage) {
    var working = stage.status === "Working";
    var messages = {
        "Modem hardware discovery": ["The modem responds to system queries.","The modem has not been confirmed. Check its power and control connection."],
        "Kernel support": ["The system exposes the modem control and network interfaces.","Some required kernel interfaces are missing or have not been confirmed."],
        "Firmware verification": ["The modem reports its firmware version.","Firmware information is incomplete. A file on disk alone does not prove that it loaded."],
        "Modem subsystem boot": ["The modem subsystem is online.","The modem subsystem is not confirmed online."],
        "Control transport": ["The system can communicate with the modem.","Communication with the modem could not be confirmed."],
        "SIM detection": ["The modem reports that the SIM card is present.","The SIM could not be read reliably. This does not prove that the slot is empty."],
        "Radio power state": ["The cellular radio is on.","The cellular radio is off or its power state is unavailable."],
        "Network registration": ["The modem is registered with a mobile network.","The modem has not registered with a mobile network. Details may include the network's rejection reason."],
        "Packet data capability": ["The modem reports data support.","Data capabilities are reported separately from a working internet connection."],
        "IP interface availability": ["A cellular network interface is available.","Check the interface details below. An interface alone does not prove that it has an address or can reach the internet."],
        "Cellular DNS configuration": ["Cellular DNS has been verified.","This check has not tested DNS through the cellular connection."],
        "End-to-end cellular connectivity": ["Cellular internet was verified by this check.","This read-only check does not send an internet test. This result does not mean that your connection is broken."]
    };
    return messages[stage.stage] ? messages[stage.stage][working ? 0 : 1] : "See the reported observations below. Unavailable information is not treated as success.";
}

function mode(status, modes) {
    var match = (modes || []).find(function(m){return m.id === status.currentMode;});
    return match ? match.label : "Not reported";
}

function power(value) {
    return {0:"Not reported",1:"Off",2:"Low power",3:"On"}[value] || "Not reported";
}
