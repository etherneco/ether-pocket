#pragma once
#include <QObject>
#include <QVariantMap>
class FingerprintClient: public QObject {
 Q_OBJECT
 Q_PROPERTY(QVariantMap state READ state NOTIFY changed)
public:
 explicit FingerprintClient(QObject *parent=nullptr);
 QVariantMap state() const { return m_state; }
 Q_INVOKABLE void refresh();
signals:
 void changed();
private:
 QVariantMap m_state{{"ready",false}};
 quint64 m_generation=0;
};
