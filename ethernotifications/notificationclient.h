#pragma once
#include <QObject>
#include <QVariantMap>
#include <QTimer>
class NotificationClient: public QObject {
 Q_OBJECT
 Q_PROPERTY(QVariantMap state READ state NOTIFY changed)
 Q_PROPERTY(QString message READ message NOTIFY changed)
 Q_PROPERTY(QVariantMap banner READ banner NOTIFY changed)
public:
 explicit NotificationClient(QObject *parent=nullptr);
 QVariantMap state()const{return m_state;}
 QVariantMap banner()const{return m_banner;}
 QString message()const{return m_message;}
 Q_INVOKABLE void refresh();
 Q_INVOKABLE void command(const QString&,uint id=0,const QVariantMap& data={});
 Q_INVOKABLE void configure(const QVariantMap&);
 Q_INVOKABLE void appPolicy(const QString&,const QVariantMap&);
 Q_INVOKABLE void session(bool locked,bool callActive,bool screenOff);
 Q_INVOKABLE void nextBanner();
signals:
 void changed();
private slots:
 void scheduleRefresh();void incoming(uint);
private:
 void call(const QString&,const QVariantList&);
 void accept(const QString&);
 QVariantMap m_state{{"ready",false}},m_banner,m_session;
 QString m_message;
 QList<uint> m_queue;
 QTimer m_refresh,m_bannerTimer,m_lease;
 bool m_loading=false,m_again=false;
};
