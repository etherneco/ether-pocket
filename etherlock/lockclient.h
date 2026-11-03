#pragma once
#include <QObject>
#include <QVariantMap>
#include <QTimer>
class LockClient:public QObject {
 Q_OBJECT
 Q_PROPERTY(QVariantMap state READ state NOTIFY changed)
 Q_PROPERTY(QString message READ message NOTIFY changed)
public:
 explicit LockClient(QObject *parent=nullptr);
 QVariantMap state()const{return m_state;}
 QString message()const{return m_message;}
 bool privacyRequired()const{return m_state.value("locked",m_required).toBool();}
 bool automatic()const{return m_required;}
 bool beforeBlank();
 Q_INVOKABLE void lock();
 Q_INVOKABLE void configure(const QVariantMap &patch);
public slots:
 void refresh();void update(const QString &document);
signals:
 void changed();
private:
 void call(const QString &method,const QVariantList &args={});
 QVariantMap m_state{{"ready",false}};QString m_message;bool m_required=false;QTimer m_poll;
};
