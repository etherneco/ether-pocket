#pragma once
#include <QObject>
#include <QVariantMap>
#include <QVariantList>
class HardwareClient : public QObject {
 Q_OBJECT
 Q_PROPERTY(QVariantMap state READ state NOTIFY changed)
 Q_PROPERTY(QVariantMap session READ session NOTIFY changed)
 Q_PROPERTY(QVariantList history READ history NOTIFY changed)
 Q_PROPERTY(QVariantMap repairPlan READ repairPlan NOTIFY changed)
 Q_PROPERTY(QString message READ message NOTIFY changed)
 Q_PROPERTY(bool busy READ busy NOTIFY changed)
public:
 explicit HardwareClient(QObject *parent=nullptr);
 QVariantMap state()const{return m_state;}
 QVariantMap session()const{return m_session;}
 QVariantMap repairPlan()const{return m_plan;}
 QVariantList history()const{return m_history;}
 QString message()const{return m_message;}
 bool busy()const{return m_pending>0||m_state.value("busy").toBool();}
 Q_INVOKABLE void refresh(const QString &category="all");
 Q_INVOKABLE void diagnose(const QString &category="all");
 Q_INVOKABLE void loadHistory(const QString &query="",const QString &component="");
 Q_INVOKABLE void clearHistory();
 Q_INVOKABLE void exportReport(const QString &format);
 Q_INVOKABLE void inspectSession();
 Q_INVOKABLE void mediaTest(const QString &kind);
 Q_INVOKABLE void planRepair(const QString &package);
 Q_INVOKABLE void installReviewedTool();
signals:void changed();
private slots:void update(const QString &json);
private:
 void fetch();
 void call(const QString &method,const QVariantList &args={},const QString &format="");
 QVariantMap m_state,m_session,m_plan;QVariantList m_history;QString m_message;int m_pending=0;
 bool m_mediaRunning=false;
};
