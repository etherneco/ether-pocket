#pragma once
#include <QObject>
#include <QVariantMap>
class BackupClient:public QObject {
 Q_OBJECT
 Q_PROPERTY(QVariantMap state READ state NOTIFY changed)
 Q_PROPERTY(QVariantMap details READ details NOTIFY changed)
 Q_PROPERTY(QVariantMap preview READ preview NOTIFY changed)
 Q_PROPERTY(QString message READ message NOTIFY changed)
public:
 explicit BackupClient(QObject *parent=nullptr);
 QVariantMap state()const{return m_state;}
 QVariantMap details()const{return m_details;}
 QVariantMap preview()const{return m_preview;}
 QString message()const{return m_message;}
 Q_INVOKABLE void refresh();
 Q_INVOKABLE void inspect();
 Q_INVOKABLE void backup(const QString&,const QString&);
 Q_INVOKABLE void verify(const QString&);
 Q_INVOKABLE void select(const QString&,const QString&);
 Q_INVOKABLE void restore();
 Q_INVOKABLE void protect(const QString&);
 Q_INVOKABLE void recoveryInfo(const QString&);
signals:void changed();
private slots:void update(const QString&);void event(const QString&);void privacy(const QString&);
private:
 void request(const QString&,const QVariantList& args={});
 QVariantMap m_state,m_details,m_preview;QString m_message,m_selected,m_prefix;
 bool m_private=true;quint64 m_epoch=0;
};
