#pragma once
#include <QObject>
#include <QVariantMap>

// Providers must publish observed state. Transport adapters remain disabled until
// their control AND packet paths have been verified; no synthetic modem exists.
class ModemProvider : public QObject {
    Q_OBJECT
public:
    using QObject::QObject;
    virtual void refresh() = 0;
    virtual QVariantMap snapshot() const = 0;
signals:
    void changed();
};
