#pragma once
#include <QObject>
#include <QVariantMap>
#include <QVariantList>
#include <QTimer>
class Core;class Media;
class PowerClient:public QObject {
 Q_OBJECT
 Q_PROPERTY(QVariantMap state READ state NOTIFY changed)
 Q_PROPERTY(QVariantMap session READ session NOTIFY changed)
 Q_PROPERTY(QVariantList history READ history NOTIFY changed)
 Q_PROPERTY(QVariantList processes READ processes NOTIFY changed)
 Q_PROPERTY(QString message READ message NOTIFY changed)
 Q_PROPERTY(bool busy READ busy NOTIFY changed)
public:
 PowerClient(Core*,Media*,QObject *parent=nullptr);
 QVariantMap state()const{return m_state;}
 QVariantMap session()const{return m_session;}
 QVariantList history()const{return m_history;}
 QVariantList processes()const{return m_processes;}
 QString message()const{return m_message;}
 bool busy()const{return m_pending||m_state.value("busy").toBool();}
 Q_INVOKABLE void refresh();
 Q_INVOKABLE void profile(const QString&,const QString &custom="");
 Q_INVOKABLE void configure(const QVariantMap&);
 Q_INVOKABLE void loadHistory(int hours=24);
 Q_INVOKABLE void inspectProcesses();
 Q_INVOKABLE void restore();
 Q_INVOKABLE void powerAction(const QString&);
 Q_INVOKABLE void setBrightness(int);
 Q_INVOKABLE void screenOff();
 Q_INVOKABLE void wake();
signals:void changed();void notice(const QString&,const QString&);void powerMenuRequested();
private slots:void update(const QString&);void backendNotice(const QString&,const QString&);void backendEvent(const QString&,const QString&);
private:
 void call(const QString&,const QVariantList& args={});void displayPolicy();void reportDisplay();
 Core *m_core;Media *m_media;QVariantMap m_state,m_session;QVariantList m_history,m_processes;
 QString m_message,m_lastProfile;int m_pending=0,m_historyHours=0,m_timeout=-1,m_beforeSaver=-1,m_saverLevel=-1;
 bool m_external=false,m_firstDisplay=true;QTimer m_reportTimer;
};
