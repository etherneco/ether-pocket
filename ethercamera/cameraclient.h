#pragma once
#include <QObject>
#include <QVariantMap>
class CameraClient:public QObject {
 Q_OBJECT
 Q_PROPERTY(QVariantMap state READ state NOTIFY changed)
 Q_PROPERTY(QString message READ message NOTIFY changed)
public:
 explicit CameraClient(QObject *parent=nullptr);
 QVariantMap state()const{return m_state;}
 QString message()const{return m_message;}
 Q_INVOKABLE void refresh();
 Q_INVOKABLE void configure(const QVariantMap&);
signals:void changed();
private slots:void update(const QString&);
private:void request(const QString&,const QVariantList& args={});QVariantMap m_state;QString m_message;
};
