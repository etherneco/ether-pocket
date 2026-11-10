.pragma library

// Shared presentation only. Transport and exported documents keep their schema.
function label(key) {
    var names = {cpu:"CPU", gpu:"GPU", id:"ID", maxKHz:"Maximum frequency (kHz)",
        minKHz:"Minimum frequency (kHz)", currentKHz:"Current frequency (kHz)",
        maxHz:"Maximum frequency (Hz)", cpuC:"CPU temperature (°C)",
        batteryC:"Battery temperature (°C)", capacity:"Battery (%)",
        keepLast:"Latest recovery points", keepDaily:"Daily recovery points",
        keepWeekly:"Weekly recovery points", keepMonthly:"Monthly recovery points"};
    if (names[key]) return names[key];
    var text = String(key).replace(/([a-z0-9])([A-Z])/g, "$1 $2").replace(/[_-]+/g, " ");
    return text.charAt(0).toUpperCase() + text.slice(1);
}

function parsed(value) {
    if (typeof value !== "string") return value;
    var trimmed = value.trim();
    if (trimmed.charAt(0) === "{" || trimmed.charAt(0) === "[") {
        try { return JSON.parse(trimmed); } catch (error) { /* ordinary text */ }
    }
    return value;
}

function scalar(value, key) {
    if (value === null || value === undefined) return "Unavailable";
    if (typeof value === "boolean") return value ? "Yes" : "No";
    if (value === "") return "—";
    if (typeof value === "number" && /Bytes$/.test(key || "")) {
        var units = ["B", "KiB", "MiB", "GiB", "TiB"], index = 0;
        while (Math.abs(value) >= 1024 && index < units.length - 1) { value /= 1024; index++; }
        return value.toLocaleString(undefined, {maximumFractionDigits: 2}) + " " + units[index];
    }
    return String(value);
}

function lines(value, prefix, depth) {
    value = parsed(value);
    if (depth > 12) return [prefix + "Further nested details"];
    if (value === null || typeof value !== "object") return [prefix + scalar(value)];
    var keys = Object.keys(value), result = [];
    if (!keys.length) return [prefix + "None"];
    for (var i = 0; i < keys.length; i++) {
        var key = keys[i], item = parsed(value[key]);
        var title = Array.isArray(value) ? String(i + 1) : label(key);
        if (item !== null && typeof item === "object") {
            result.push(prefix + title);
            result = result.concat(lines(item, prefix + "    ", depth + 1));
        } else {
            result.push(prefix + title + ": " + scalar(item, key));
        }
    }
    return result;
}

function text(value) { return lines(value, "", 0).join("\n"); }

function fields(value, path, depth) {
    path = path || ""; depth = depth || 0;
    value = parsed(value);
    if (depth > 12) return [{title:path, value:"Further nested details"}];
    if (value === null || typeof value !== "object") return [{title:path || "Value", value:scalar(value)}];
    var keys = Object.keys(value), result = [];
    if (!keys.length) return [{title:path || "Details", value:"None"}];
    keys.forEach(function(key) {
        var title = (path ? path + " › " : "") + (Array.isArray(value) ? Number(key) + 1 : label(key));
        var item = parsed(value[key]);
        if (item !== null && typeof item === "object") result = result.concat(fields(item, title, depth + 1));
        else result.push({title:title, value:scalar(item, key)});
    });
    return result;
}
