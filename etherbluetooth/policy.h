#pragma once
#include <QString>
#include <QStringList>
namespace Policy {
inline int retryDelay(int attempts, bool powered, bool trusted, bool enabled, bool manual) {
    return powered && trusted && enabled && !manual && attempts >= 0 && attempts < 4 ? 2000 * (1 << attempts) : -1;
}
inline QString category(const QString &icon, const QStringList &uuids) {
    if (uuids.contains("00001812-0000-1000-8000-00805f9b34fb")) return "HID / BLE input";
    if (icon.contains("headset") || icon.contains("headphones")) return "Headphones";
    if (icon.contains("audio")) return "Audio";
    if (icon.contains("keyboard")) return "Keyboard";
    if (icon.contains("mouse")) return "Mouse";
    if (icon.contains("gaming")) return "Game controller";
    if (icon.contains("phone")) return "Phone";
    if (icon.contains("computer")) return "Computer";
    return "Bluetooth device";
}
inline QString explain(const QString &error) {
    if(error.contains("NotReady")) return "Controller is not ready. Check power and Driver Doctor.";
    if(error.contains("AuthenticationRejected")) return "The other device rejected pairing. Put it in pairing mode and retry.";
    if(error.contains("AuthenticationCanceled")) return "Pairing was cancelled.";
    if(error.contains("AuthenticationTimeout")) return "Pairing timed out. Keep the device nearby and retry.";
    if(error.contains("NotAuthorized") || error.contains("AccessDenied")) return "System policy denied this operation. Check D-Bus or PolicyKit permissions.";
    if(error.contains("NotAvailable")) return "The requested service or profile is unavailable.";
    return "Bluetooth operation failed. Inspect the technical evidence below.";
}
}
